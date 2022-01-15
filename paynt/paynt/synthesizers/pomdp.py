import stormpy

from .statistic import Statistic
from .models import MarkovChain, DTMC, MDP
from .quotient import POMDPQuotientContainer
from .synthesizer import SynthesizerAR

from ..profiler import Timer,Profiler

from ..sketch.holes import Holes,DesignSpace

import logging
logger = logging.getLogger(__name__)

# TODO make SynthesizerPOMDP a subclass of Synthesizer?

class SynthesizerPOMDP():

    def __init__(self, sketch):
        assert sketch.is_pomdp

        MarkovChain.initialize(sketch.properties, sketch.optimality_property)

        self.sketch = sketch
        self.quotient_container = POMDPQuotientContainer(sketch)
        self.total_iters = 0

        Profiler.initialize()

    def print_stats(self):
        pass

    def synthesize(self, family = None):
        Profiler.start("synthesis")
        if family is None:
            family = self.sketch.design_space
        synthesizer = SynthesizerAR(self.sketch, self.quotient_container)
        assignment = synthesizer.synthesize(family)
        synthesizer.print_stats()
        Profiler.stop()
        self.total_iters += synthesizer.stat.iterations_mdp
        return assignment

    def mdp_scheduler(self, property, design_space):
        mdp = self.quotient_container.build(design_space)
        result = mdp.model_check_property(property)
        selection = self.quotient_container.scheduler_selection(mdp, result.scheduler)
        return selection

    def choose_consistent(self, full_space, restriction):
        design_space = full_space.copy()
        for obs,choices in restriction.items():
            hole_index = self.quotient_container.pomdp_manager.action_holes[obs][0]
            design_space = design_space.assume_suboptions(hole_index, choices)
        # print("full design space", self.sketch.design_space)                
        # print("restricted design space: ", design_space)
        print("reduced design space from {} to {}".format(full_space.size, design_space.size))
        return design_space

    def choose_consistent_and_break_symmetry(self, full_space, observation_choices):
        design_space = full_space.copy()
        for obs,choices in observation_choices.items():
            hole_indices = self.quotient_container.pomdp_manager.action_holes[obs]
            if len(hole_indices) == 1:
                if len(choices) == 1:
                    # consistent observation
                    hole_index = hole_indices[0]
                    design_space = design_space.assume_suboptions(hole_index, choices)
            else:
                # have multiple holes for this observation
                for index,hole_index in enumerate(hole_indices):
                    options = full_space[hole_index].options.copy()
                    options.remove(choices[index])
                    design_space = design_space.assume_suboptions(hole_index, options)
        # print("full design space", self.sketch.design_space)                
        # print("restricted design space: ", design_space)
        print("reduced design space from {} to {}".format(full_space.size, design_space.size))
        return design_space

    def strategy_1(self):
        self.quotient_container.pomdp_manager.set_memory_size(1)
        self.quotient_container.unfold_partial_memory()
        self.synthesize()
        Profiler.print()

    def strategy_2(self):
        # analyze POMDP
        assert len(self.sketch.properties) == 0
        self.quotient_container.unfold_partial_memory()

        selection = self.mdp_scheduler(self.sketch.optimality_property, self.sketch.design_space)
        print("scheduler selected: ", selection)

        # associate observations with respective choices
        observation_choices = {}
        pm = self.quotient_container.pomdp_manager
        for obs in range(self.quotient_container.pomdp.nr_observations):
            hole_indices = pm.action_holes[obs]
            if len(hole_indices) == 0:
                continue
            hole_index = hole_indices[0]
            assert len(selection[hole_index]) >= 1
            observation_choices[obs] = selection[hole_index]
        print("observation choices: ", observation_choices)

        # map consistent observations to corresponding choices
        consistent_restriction = {obs:choices for obs,choices in observation_choices.items() if len(choices) == 1}
        print("consistent restriction" , consistent_restriction)

        # synthesize optimal solution for k=1 (full, restricted)
        # restrict options of consistent holes to a scheduler selection
        design_space = self.choose_consistent(self.sketch.design_space, consistent_restriction)
        self.synthesize(design_space)

        # synthesize optimal solution for k=2 (partial, restricted)
        # gradually inject memory to inconsistent observations
        for obs in range(self.quotient_container.pomdp.nr_observations):
            if pm.action_holes[obs] and obs not in consistent_restriction:
                print("injecting memory to observation ", obs)
                print("scheduler chose actions ", observation_choices[obs])
                self.quotient_container.pomdp_manager.inject_memory(obs)
                self.quotient_container.unfold_partial_memory()
                # design_space = self.choose_consistent(self.sketch.design_space, consistent_restriction)
                design_space = self.choose_consistent_and_break_symmetry(self.sketch.design_space, observation_choices)
                self.synthesize(design_space)

        # synthesize optimal solution for k=2 (partial, unrestricted)
        # print("synthesizing solution for k=2 (partial, unrestricted)")
        # self.synthesize()

        # total stats
        print("total iters: ", self.total_iters)
        Profiler.print()

    def suggest_injection_splitter_frequency(self):
        pomdp = self.quotient_container.pomdp
        action_holes = self.quotient_container.pomdp_manager.action_holes

        observation_split = [0] * pomdp.nr_observations
        for obs in range(pomdp.nr_observations):
            for action_hole in action_holes[obs]:
                observation_split[obs] += self.quotient_container.splitter_frequency[action_hole]

        observation_split = {obs : splits for obs,splits in enumerate(observation_split) if splits > 0}
        if len(observation_split) == 0:
            selection = self.mdp_scheduler(self.sketch.optimality_property,self.sketch.design_space)
            assert False
        print("observation_split = ", observation_split)

        observation_memory_size = self.quotient_container.pomdp_manager.observation_memory_size
        print("obs_mem_size: ", observation_memory_size)
        max_memory_size = max(observation_memory_size)

        candidate_obs = {obs:splits for obs,splits in observation_split.items() if observation_memory_size[obs] < max_memory_size}
        if len(candidate_obs) == 0:
            candidate_obs = observation_split

        max_splits_obs = max(candidate_obs, key=candidate_obs.get)
        return max_splits_obs    

    def collect_action_holes_to_fix(self, obs_injected):
        # collect action holes of the injected observation
        interesting_action_holes = self.quotient_container.pomdp_manager.action_holes[obs_injected]

        # in the constructed quotient mdp, identify states having interesting action holes
        qmdp = self.quotient_container.quotient_mdp
        tm = qmdp.transition_matrix
        state_affected = []
        for state in range(qmdp.nr_states):
            affected = False
            for choice in range(tm.get_row_group_start(state),tm.get_row_group_end(state)):
                hole_options = self.quotient_container.action_to_hole_options[choice]
                for hole_index in hole_options.keys():
                    if hole_index in interesting_action_holes:
                        affected = True
                        break
                if affected:
                    break
            state_affected.append(affected)

        # mark states that have affected successors
        successor_affected = []
        for state in range(qmdp.nr_states):
            # affected states are automatically marked
            if state_affected[state]:
                successor_affected.append(True)
                continue

            # explore successors 
            affected = False
            for choice in range(tm.get_row_group_start(state),tm.get_row_group_end(state)):
                for entry in tm.get_row(choice):
                    successor = entry.column
                    if state_affected[successor]:
                        affected = True
                        break
                if affected:
                    break
            successor_affected.append(affected)

        # mark (action) holes associated with marked states
        hole_marked = [False] * self.sketch.design_space.num_holes
        for state in range(qmdp.nr_states):
            if not successor_affected[state]:
                continue
            for choice in range(tm.get_row_group_start(state),tm.get_row_group_end(state)):
                hole_options = self.quotient_container.action_to_hole_options[choice]
                for hole_index in hole_options.keys():
                    hole_marked[hole_index] = True

        # filter action holes that were not marked
        action_hole_not_marked = []
        for action_holes in self.quotient_container.pomdp_manager.action_holes:
            for action_hole in action_holes:
                if not hole_marked[action_hole]:
                    action_hole_not_marked.append(action_hole)
        
        return action_hole_not_marked

    def sum_inconsistencies(self, obs):
        print("splitter inconsistencies:", self.quotient_container.splitter_inconsistencies)
        inconsistencies_sum = {}
        for action_hole in self.quotient_container.pomdp_manager.action_holes[obs]:
            inconsistencies = self.quotient_container.splitter_inconsistencies[action_hole]
            for inconsistency,frequency in inconsistencies.items():
                frequency_sum = inconsistencies_sum.get(inconsistency,0)
                frequency_sum += frequency
                inconsistencies_sum[inconsistency] = frequency_sum
        print("inconsistency frequencies:", inconsistencies_sum)
        inconsistency = max(inconsistencies_sum, key=inconsistencies_sum.get)
        inconsistency = list(inconsistency)
        print("selected inconsistency {} to break the symmetry in observation {}".format(inconsistency,obs))
        return inconsistency

    def map_new_action_holes(self, old_action_holes, obs_injected):
        new_action_holes = self.quotient_container.pomdp_manager.action_holes
        new_to_old_action_holes = {}
        for obs in range(self.quotient_container.pomdp.nr_observations):
            if obs == obs_injected:
                continue
            assert len(old_action_holes[obs]) == len(new_action_holes[obs])
            for index,new_action_hole in enumerate(new_action_holes[obs]):
                new_to_old_action_holes[new_action_hole] = old_action_holes[obs][index]
        return new_to_old_action_holes

    def extend_observation(self, obs):
        print("injecting memory into observation", obs)
        self.quotient_container.pomdp_manager.inject_memory(obs)
        self.quotient_container.unfold_partial_memory()

    def fix_assignment(self, design_space):
        print("WARNING: fixing None assignment")
        selection = self.mdp_scheduler(self.sketch.optimality_property, design_space)
        selection = [options if len(options) > 0 else design_space[hole_index].options for hole_index,options in enumerate(selection)]
        selection = [[options[0]] for options in selection]
        assignment = design_space.copy()
        assignment.assume_options(selection)
        return assignment



    def strategy_3(self):
        
        assert len(self.sketch.properties) == 0     # FIXME

        # synthesize optimum for k = 1
        print("")
        print("synthesizing optimum for k = 1")
        self.quotient_container.pomdp_manager.set_memory_size(1)
        self.quotient_container.unfold_partial_memory()

        assignment = self.synthesize()
        if assignment is None:
            assignment = self.fix_assignment(self.sketch.design_space)
            
        for synthesis_iteration in range(2):

            # select observation
            obs_injected = self.suggest_injection_splitter_frequency()
            old_action_holes = self.quotient_container.pomdp_manager.action_holes
            inconsistency = self.sum_inconsistencies(obs_injected)
            
            # inject
            self.extend_observation(obs_injected)
            new_to_old_action_holes = self.map_new_action_holes(old_action_holes,obs_injected)

            # break symmetry in the action holes for the injected observation
            design_space = self.sketch.design_space.copy()
            index = 0
            for hole_index in self.quotient_container.pomdp_manager.action_holes[obs_injected]:
                design_space[hole_index].options.remove(inconsistency[index])
                index = (index + 1) % len(inconsistency)
            print("asymmetric design space:", design_space)

            # suggest action holes to fix
            fixed_action_holes = self.collect_action_holes_to_fix(obs_injected)

            # fix these holes using the latest assignment
            for hole_index in fixed_action_holes:
                old_hole = new_to_old_action_holes[hole_index]
                print("restricting hole {} to {}".format(hole_index,assignment[old_hole]))
                design_space.assume_hole_options(hole_index,assignment[old_hole].options)
            print("reduced design space from {} to {}".format(self.sketch.design_space.size,design_space.size))

            # synthesize within the restricted design space
            print("synthesizing within the restricted design space")
            print("", flush=True)
            assignment = self.synthesize(design_space)
            if assignment is None:
                assignment = self.fix_assignment(design_space)

        Profiler.print()

    def strategy_4(self):
        
        assert len(self.sketch.properties) == 0     # FIXME

        # start with k = 1
        self.quotient_container.pomdp_manager.set_memory_size(1)
        for i in range(1):

            # construct quotient
            self.quotient_container.unfold_partial_memory()

            # compute scheduler for the quotient
            mdp = self.quotient_container.build()
            mdp_result = mdp.model_check_property(self.sketch.optimality_property)
            scheduler_selection = self.quotient_container.scheduler_selection(mdp, mdp_result.scheduler)
            inconsistent_selection = {hole_index:options for hole_index,options in enumerate(scheduler_selection) if len(options) > 1}

            # synthesize optimum
            optimal_assignment = self.synthesize()
            assert optimal_assignment is not None # FIXME

            # get numerical values associated with optimum
            dtmc = self.quotient_container.build_dtmc(optimal_assignment)
            print(dtmc.quotient_choice_map)
            dtmc_result = dtmc.model_check_property(self.sketch.optimality_property).get_values()

            # map to MDP
            # dtmc_result = [dtmc.quo]

            print(dtmc_result)
            exit()



            print(inconsistent_selection)

            # choose observation to inject memory into

            # inject observation
            exit()
            self.quotient_container.pomdp_manager.inject_memory(target_obs)



            exit()
        

            # synthesize optimum for k = 1
            print("")
            print("synthesizing optimum for k = 1")

            assignment = self.synthesize()
            if assignment is None:
                assignment = self.fix_assignment(self.sketch.design_space)
                
            for synthesis_iteration in range(2):

                # select observation
                obs_injected = self.suggest_injection_splitter_frequency()
                old_action_holes = self.quotient_container.pomdp_manager.action_holes
                inconsistency = self.sum_inconsistencies(obs_injected)
                
                # inject
                self.extend_observation(obs_injected)
                new_to_old_action_holes = self.map_new_action_holes(old_action_holes,obs_injected)

                # break symmetry in the action holes for the injected observation
                design_space = self.sketch.design_space.copy()
                index = 0
                for hole_index in self.quotient_container.pomdp_manager.action_holes[obs_injected]:
                    design_space[hole_index].options.remove(inconsistency[index])
                    index = (index + 1) % len(inconsistency)
                print("asymmetric design space:", design_space)

                # suggest action holes to fix
                fixed_action_holes = self.collect_action_holes_to_fix(obs_injected)

                # fix these holes using the latest assignment
                for hole_index in fixed_action_holes:
                    old_hole = new_to_old_action_holes[hole_index]
                    print("restricting hole {} to {}".format(hole_index,assignment[old_hole]))
                    design_space.assume_hole_options(hole_index,assignment[old_hole].options)
                print("reduced design space from {} to {}".format(self.sketch.design_space.size,design_space.size))

                # synthesize within the restricted design space
                print("synthesizing within the restricted design space")
                print("", flush=True)
                assignment = self.synthesize(design_space)
                if assignment is None:
                    assignment = self.fix_assignment(design_space)


        Profiler.print()

    def strategy_counter(self):
        self.quotient_container.pomdp_manager.set_memory_size(3) # try 1,2,3,4
        self.quotient_container.unfold_partial_memory()
        # TODO restrict memory
        self.synthesize()

    def run(self):  
        # self.strategy_1()
        # self.strategy_2()
        # self.strategy_3()
        # self.strategy_4()
        self.strategy_counter()




