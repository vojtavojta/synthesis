import stormpy
from .statistic import Statistic
from .models import MarkovChain, DTMC, MDP
from .quotient import QuotientContainer,POMDPQuotientContainer
from .synthesizer import SynthesizerAR, SynthesizerHybrid

from ..profiler import Timer,Profiler

from ..sketch.holes import Holes,DesignSpace

import math
from collections import defaultdict

import logging
logger = logging.getLogger(__name__)


class SynthesizerPOMDP():

    # whether action holes will be restricted before synthesis
    # break_action_symmetry = False
    break_action_symmetry = True

    def __init__(self, sketch, method):
        assert sketch.is_pomdp
        self.sketch = sketch
        self.synthesizer = None
        if method == "ar":
            self.synthesizer = SynthesizerAR
        elif method == "hybrid":
            self.synthesizer = SynthesizerHybrid
        self.total_iters = 0
        Profiler.initialize()

    def print_stats(self):
        pass
    
    def synthesize(self, family, print_stats = True):
        self.sketch.quotient.discarded = 0
        synthesizer = self.synthesizer(self.sketch)
        family.property_indices = self.sketch.design_space.property_indices
        assignment = synthesizer.synthesize(family)
        if print_stats:
            synthesizer.print_stats()
        self.total_iters += synthesizer.stat.iterations_mdp
        return assignment


    def solve_mdp(self, family):

        # solve quotient MDP
        self.sketch.quotient.build(family)
        mdp = family.mdp
        spec = mdp.check_specification(self.sketch.specification)

        selection = spec.optimality_result.primary_selection
        choice_values = spec.optimality_result.primary_choice_values
        expected_visits = spec.optimality_result.primary_expected_visits
        scores = spec.optimality_result.primary_scores
        
        return mdp, spec, selection, choice_values, expected_visits, scores


    
    def strategy_expected(self):

        # assuming optimality
        assert self.sketch.specification.optimality is not None

        # for each observation will contain a set of observed action inconsistencies
        action_inconsistencies = [set() for obs in range(self.sketch.quotient.observations)]
        # for each observation (that doesn't have action inconsistencies) will
        # contain a set of observed memory inconsistencies
        memory_inconsistencies = [set() for obs in range(self.sketch.quotient.observations)]

        # start with k=1
        self.sketch.quotient.pomdp_manager.set_memory_size(1)

        for iteration in range(10):
            
            print("\n------------------------------------------------------------\n")

            # construct the quotient
            self.sketch.quotient.unfold_memory()
            
            # use inconsistencies to break symmetry
            family = self.sketch.quotient.break_symmetry_3(self.sketch.design_space, action_inconsistencies, memory_inconsistencies)

            # solve MDP that corresponds to this restricted family
            mdp,spec,selection,choice_values,expected_visits,hole_scores = self.solve_mdp(family)
            
            # ? assuming that primary direction was not enough ?
            assert spec.optimality_result.feasibility is None
            
            # synthesize optimal assignment
            synthesized_assignment = self.synthesize(family)
           
            # identify hole that we want to improve
            selected_hole = None
            selected_options = None
            if synthesized_assignment is None:
                # no new assignment: the hole of interest is the one with the
                # maximum score in the symmetry-free MDP
                pass
                

            else:
                # synthesized solution exists: hole of interest is the one where
                # the fully-observable improves upon the synthesized action
                # the most

                # for each state of the sub-MDP, compute potential state improvement
                state_improvement = [None] * mdp.states
                scheduler = spec.optimality_result.primary.result.scheduler
                # print(family)
                # print(synthesized_assignment)
                for state in range(mdp.states):
                    # nothing to do if the state is not labeled by any hole
                    quotient_state = mdp.quotient_state_map[state]
                    holes = self.sketch.quotient.state_to_holes[quotient_state]
                    if not holes:
                        continue
                    hole = list(holes)[0]
                    # print("state {} [{}], hole = {}".format(state,quotient_state,hole))
                    
                    # get choice obtained by the MDP model checker
                    choice_0 = mdp.model.transition_matrix.get_row_group_start(state)
                    mdp_choice = scheduler.get_choice(state).get_deterministic_choice()
                    mdp_choice = choice_0 + mdp_choice
                    # mdp_choice_global = mdp.quotient_choice_map[mdp_choice]
                    # mdp_choice_label = self.sketch.quotient.action_to_hole_options[mdp_choice_global]

                    # get choice implied by the synthesizer
                    syn_option = synthesized_assignment[hole].options[0]
                    nci = mdp.model.nondeterministic_choice_indices
                    for choice in range(nci[state],nci[state+1]):
                        choice_global = mdp.quotient_choice_map[choice]
                        choice_color = self.sketch.quotient.action_to_hole_options[choice_global]
                        if choice_color == {hole:syn_option}:
                            syn_choice = choice
                            break
                    
                    # syn_choice_global = mdp.quotient_choice_map[syn_choice]
                    # syn_choice_label = self.sketch.quotient.action_to_hole_options[syn_choice_global]

                    # estimate improvement
                    mdp_value = choice_values[mdp_choice]
                    syn_value = choice_values[syn_choice]
                    improvement = abs(syn_value - mdp_value)
                    
                    state_improvement[state] = improvement

                    # print("{} -> {} = {} -> {}".format(syn_choice,mdp_choice, syn_value,mdp_value))
                    # print("({} -> {}".format(syn_choice_label,mdp_choice_label))

                # map improvements in states of this sub-MDP to states of the quotient
                quotient_state_improvement = [None] * self.sketch.quotient.quotient_mdp.nr_states
                for state in range(mdp.states):
                    quotient_state_improvement[mdp.quotient_state_map[state]] = state_improvement[state]

                # extract DTMC corresponding to the synthesized solution
                dtmc = self.sketch.quotient.build_chain(synthesized_assignment)

                # compute expected visits for this dtmc
                dtmc_visits = stormpy.synthesis.compute_expected_number_of_visits(MarkovChain.environment, dtmc.model).get_values()
                dtmc_visits = list(dtmc_visits)

                # handle infinity- and zero-visits
                if self.sketch.specification.optimality.minimizing:
                    dtmc_visits = QuotientContainer.make_vector_defined(dtmc_visits)
                else:
                    dtmc_visits = [ value if value != math.inf else 0 for value in dtmc_visits]

                # weight state improvements with expected visits
                # aggregate these weighted improvements by holes
                hole_differences = [0] * family.num_holes
                hole_states_affected = [0] * family.num_holes
                for state in range(dtmc.states):
                    quotient_state = dtmc.quotient_state_map[state]
                    improvement = quotient_state_improvement[quotient_state]
                    # if quotient_state == 15:
                    # print("syn visits = ", dtmc_visits[state])
                    
                    if improvement is None:
                        continue

                    # print("state {}, we = {} * {}".format(quotient_state, dtmc_visits[state], improvement))

                    weighted_improvement = improvement * dtmc_visits[state]
                    assert not math.isnan(weighted_improvement), "{}*{} = nan".format(improvement,dtmc_visits[state])
                    hole = list(self.sketch.quotient.state_to_holes[quotient_state])[0]
                    hole_differences[hole] += weighted_improvement
                    hole_states_affected[hole] += 1

                print(hole_differences)
                hole_differences_avg = [0] * family.num_holes
                for hole in family.hole_indices:
                    if hole_states_affected[hole] != 0:
                        hole_differences_avg[hole] = hole_differences[hole] / hole_states_affected[hole]

                hole_scores = {hole:hole_differences_avg[hole] for hole in family.hole_indices if hole_differences_avg[hole]>0}
                print(hole_differences_avg)
                    
            
            print()
            print("hole scores: ", hole_scores)

            max_score = max(hole_scores.values())
            with_max_score = [hole for hole in hole_scores if hole_scores[hole] == max_score]
            selected_hole = with_max_score[0]
            selected_options = selection[selected_hole]
            
            print("selected hole: ", selected_hole)
            print("hole has options: ", selected_options)

            # identify observation having this hole
            for obs in range(self.sketch.quotient.observations):
                if selected_hole in self.sketch.quotient.obs_to_holes[obs]:
                    selected_observation = obs
                    break
            print("selected observation: ", selected_observation)

            # identify whether this hole is inconsistent in actions or updates
            assert len(selected_options) > 1
            actions,updates = self.sketch.quotient.sift_actions_and_updates(selected_hole, selected_options)
            print("actions & updates: ", actions, updates)
            if len(actions) > 1:
                # action inconsistency
                action_inconsistencies[obs] |= actions
            else:
                memory_inconsistencies[obs] |= updates


            # inject memory and continue
            self.sketch.quotient.pomdp_manager.inject_memory(selected_observation)
        


    def strategy_full(self):
        self.sketch.quotient.pomdp_manager.set_memory_size(3)
        self.sketch.quotient.unfold_memory()
        self.synthesize()

    def run(self):
        # self.strategy_full()
        self.strategy_expected()





