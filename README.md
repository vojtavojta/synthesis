# Abstract for the artifact submission.

This artifact includes an implementation of the novel method for synthesis of probabilistic systems proposed in the TACAS 2021 submission #87 (Inductive Synthesis for Probabilistic Programs Reaches New Horizons). The artifact further includes an implementation of state-of-the-art methods for synthesis of probabilistic systems that are used in the experimental part of the paper to evaluate the performance of the proposed methods, and the benchmarks used in the evaluation. The artifact allows users to replicate all the experiments presented in the paper, in particular, the results presented in Tables 1-3. It further suggests additional experiments that allow to explore the discussed methods beyond the presented experiment suit.

This artifact is publicly available at TBD () for the currently developed branch of the dynasty (https://github.com/moves-rwth/dynasty) tool for synthesis of probabilistic systems.
 
# Artifact for submission 87

This is an artifact supplemented with the TACAS 2021 submission __Roman Andriushchenko, Milan Češka, Sebastian Junges, and Joost-Pieter Katoen:__ **Inductive Synthesis for Probabilistic ProgramsReaches New Horizons**. The tool represents a branch of the [dynasty](https://github.com/moves-rwth/dynasty) tool for probabilistic synthesis and contains the dynasty code as well as its adaptations for [storm](https://github.com/moves-rwth/storm) and [stormpy](https://github.com/moves-rwth/stormpy) (prerequisites for dynasty).

**Disclaimer.** Since the initial submission of the paper manuscript, the implementation of the tool has been subject to multiple improvements and optimizations, with the most drastic changes concerning the CEGAR method and the CEGAR loop of the integrated method. As a consequence of this, the experimental evaluation of the synthesis methods has been very slightly reworked in the revised manuscript to better highlight the differences between the synthesis approaches. The conclusions drawn from the presented experiments remain the same, although in multiple cases the novel integrated method has demonstrated even more distinguished results.

## Installation of the artifact

Installation is performed automatically by running the installation script `install.sh`:

```sh
sudo ./install.sh
```

Compilation of the tool and of all of its prerequisites will take about an hour. To accelerate compilation, we recommend enabling multiple CPU cores on your VM. Such multi-core compilation is quite memory-intensive, therefore, we recommend allocating a significant amount of RAM on your VM as well. As a rule of thumb, we recommend allocating at least 1.5 GB RAM per core. For instance, for a VM with 4 CPU cores and at least 6 GB of RAM, the compilation should take around 20 minutes. Any errors you encounter during the compilation are most likely caused by the lack of memory: try to allocate more RAM for your VM or disable multi-core compilation (see exported variable COMPILE_JOBS in the script install.sh).

## Initial testing of the artifact

Having installed the tool, you can test it by running the dynasty tool to evaluate a simple synthesis problem:

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid
```

The syntax of the command is explained in the last chapter of this README. For now, we can see that we investigate the __Grid__ benchmark discussed in the TACAS'21 paper and synthesize it wrt. the easy property using the hybrid approach. The tool will print a series of log messages and, in the end, a short summary of the synthesis process, similar to the one below:

```
formula 1: P>=931/1000 [F ("goal" & (c < 40))]

method: Hybrid, synthesis time: 3.03 s
number of holes: 8, family size: 65536
super MDP size: 11535, average MDP size: 11490, MPD checks: 5, iterations: 5
average DTMC size: 1232, DTMC checks: 215, iterations: 215

feasible: no
```

## Reproducing presented experiments

All of the experiments discussed in the paper can be evaluated by running the `experiment.sh` script:

```sh
./experiment.sh
```

The script executes all 63 experiments and creates a separate log for each experiment (see `experiments/logs/` folder). Afterwards, these logs are parsed to generate Tables 1, 2 and 3 reported in the paper. These automatically generated tables are stored in experiments/summary.txt file and are printed to the standard output as well.

Due to the fact that reproducing _all_ of the experiments discussed in the paper would take hundreds of hours, we provide two timeout values defined right at the beginning of the `experiment.sh` script: `TIMEOUT_SMALL_MODELS` and `TIMEOUT_LARGE_MODELS`. While the former value is applied when evaluating smaller benchmarks (Grid, Maze, DPM, Pole, Herman and the smaller variant of Herman-2), the latter is applied only to the larger variant of Herman-2 (see the right part of Table 3). The timeout value is applied to each individual experiment. If the experiment hits the timeout, the corresponding log file will be terminated by "TO" line and the corresponding entry in the auto-generated table will contain a dash '-'. However, if the CEGAR execution will hit a timeout, its performance will be estimated based on the number of rejected members, and the corresponding table entry will contain this estimate with a star '\*', mirroring the notation adapted in the paper.

Choosing concrete values for the timeouts will define how many experiments you will be able to replicate. The following are some possible values for the smaller `TIMEOUT_SMALL_MODELS` to help you decide:

- `2m` -- two minutes is the 'minimum' value that will allow you to replicate 36/48 experiments that consider smaller benchmarks -- this execution will take roughly 40 minutes.
- `20m` (recommended value) -- this setting will result in a computation that lasts approximately 5 hours and will replicate 44/48 experiments
- `2h` -- this setting (used during our preparation of the paper) will occupy your CPU for 23 hours and will successfully replicate all 48/48 experiments

Regarding the `TIMEOUT_LARGE_MODELS` value, choosing `0s` will allow you to ignore these experiments completely. Option `TIMEOUT_LARGE_MODELS=30m` is the minimum value that will safely allow the integrated method to finish. Experiments on large models with this timeout will amount to three hours. For the CEGAR method, you will obtain very rough estimates of their performance.  Unfortunately, these estimates will be very poor: obtaining good estimates requires running CEGAR for at least five hours (recommended value), resulting in the overall runtime of 21 hours. In our evaluation, we used `TIMEOUT_LARGE_MODELS=24h`.

Finally, note that the `./experiment.sh` script evaluates experiments concurrently based on the number `nproc` of CPU cores available on your VM. Therefore, supplying your VM with multiple cores will greatly reduce computation time. For instance, having a VM with 4 CPU cores and choosing recommended settings `TIMEOUT_SMALL_MODELS=20m` and `TIMEOUT_LARGE_MODELS=5h` will allow you to reproduce almost all experiments and obtain relatively good estimates of the CEGAR behaviour in only about 6 hours of uptime.

**Please note** that all of the discussed synthesis methods -- CEGIS, CEGAR and the novel integrated method -- are subject to some nondeterminism during their execution, and therefore during your particular evaluation you might obtain slightly different numbers of iterations as well as execution times. Furthermore, the switching nature of the integrated method heavily depends on the timing, which can again result in fluctutations in the observed measurements. However, the qualitative conclusions -- e.g. overall performance of hybrid vs CEGAR or overall quality of MaxSat counterexamples vs those obtained by a novel approach -- should be preserved.

## How to run synthesis manually

The remainder of this README explains how to run dynasty tool manually to help you set up your own experiments. First, recall the dynasty call mentioned above:

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid
```

The first option `--project` specifies the path to the benchmark folder. Inspect the contents of this folder: it contains the template description (`sketch.templ`) in the PRISM guarded command language, a file (`sketch.allowed`) containing possible values for all parameters and two files (`easy.properties` and `hard.properties`) containing specifications. To select a specification to synthesize agains, we use option `--properties`. Finally, the last argument specifies the synthesis method: `hybrid`, `cegar`, `cegis` or `onebyone`. For instance, to evaluate this benchmark using CEGIS, simply run

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties cegis
```

The summary printed in the end contains some info abount the synthesis process: benchmark statistics, synthesis time, number of iterations, whether the synthesis problem is feasible etc. We can see that this particular Grid benchmark contains 8 holes (parameters) and 65k members, each having 1.2k states on average -- you can check that these data correspond to the ones reported in Table 1. We can also see that the problem was unfeasible and that on our machine it took CEGIS 613 iterations and 30 seconds to prove this -- you can cross-reference these data with the ones reported in the first row of Table 2. Notice that, contrary to the summary provided by running the hybrid method, this summary does not contain MDP-related information (average MDP size, number of MDP model checks etc.) since CEGIS never deals with MDPs. Similarly, summary provided by running CEGAR (this evaluation will run for about eight minutes):

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties cegar
```

will not contain information about DTMC size. Furthermore, when evaluating benchmark using the hybrid approach, you can specify an additional `--ce-quality` option that evaluates the counterexample quality:

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid --ce-quality
```

In this case, the summary will contain two additional rows with information about the quality as well as the construction times of the counterexamples, as discussed in the left-hand side of Table 2. You will notice that the quality of the MaxSat method will be reported as 0, since this value was not computed at all -- we do not compute the MaxSat quality implicitly since this computation is often very time-demanding and would complicate collecting data about the novel approach for CE construction. To enable evaluation of the MaxSat approach, you can specify an additional option `--ce-maxsat`:

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid --ce-quality --ce-maxsat
```

You can cross-reference the obtained summaries with the values reported in the first row of Table 2. 

## Exploring synthesis problems beyond the presented experiment suit

In order to further investigate the performance of the synthesis methods, we suggest to perform some additional experiments that focus on three different aspects having the essential impact on the runtime of the synthesis process. These experiments will be based on experimenting with the provided tacas21-benchmark, therefore, before proceeding with the suggestions below, make sure to make a copy of this directory if haven't evaluated the experiment suit presented in the paper via the `experiment.sh` suit.

#### Modifying the family size
Changing the family size of particular models can require nontrivial changes in the model definition and thus a certain level of understanding of the models. However, there are some models where the family size can be easily changed. For example, the size of the larger variant of the model can be modified in the following way:
Go to 
herman2_larger/sketch.allowed
and reduce the domains of the selected options (holes), e.g., modify the file in the following way:

```
M0LFAIR;0;1;2
M0HFAIR;0;1;2
M1LFAIR;0;1;2
M1HFAIR;0;1;2
MxxA;0;1
MxxB;0;1
MxxC;0;1
```

This reduces the number of randomization strategies of the protocol and thus the family size. You can now run

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/herman2_smaller --properties feasibility.properties hybrid
python3 dynasty/dynasty.py --project tacas21-benchmark/herman2_smaller --properties feasibility.properties cegar
```

Notice that this family contains roughly six hundred members (as opposed to 5k members in the original model. Instead of deciding feasibility, you can also compute the optimal value for this model:

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/herman2_smaller --properties none.properties --optimality 0.optimal hybrid
```

You can see that the optimal value is 35.6 (expected) steps and that the summary also contains the parameter assignment for this optimal member. If we enlarge this family to its original size:

```
M0LFAIR;0;1;2;3;4
M0HFAIR;0;1;2;3;4
M1LFAIR;0;1;2;3;4
M1HFAIR;0;1;2;3;4
MxxA;0;1
MxxB;0;1
MxxC;0;1
```

computing the optimal value now takes some more time, but the obtained value is now around 18.1, meaning that we have found a member that can stabilize almost twice as fast. What happened here is that we have added some strategies for our protocol and, fortunately, some of these strategies were better (wrt. the specification) than existing ones.

#### Modifying the (average) size of the family members
Most of our models (i.e. DPM, Grid, Herman, and Maze) include the parameter CMAX allowing users to change size of the particular family members (i.e. the underlying DTMCs) -- increasing this parameter increases the average size of the members. Please note that some properties are linked with this parameter and thus changing the parameter can change feasibility outcome and can even make some properties invalid. For example, you can try to run 

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties cegis
```
and then modify the parameter CMAX in file tacas21-benchmark/grid/sketch.templ:

```
const int CMAX = 100;
```

and rerun the two commands above. You can inspect that the size of underlying DTMCs as well as the size of quotient MDPs has increased and that the synthesis now takes more time.

#### Modifying threshold of the given property

The property thresholds for the synthesis problems can be changed in files .properties that are stored in particular benchmark folders. For example, you can try to run 

```sh
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties hybrid
python3 dynasty/dynasty.py --project tacas21-benchmark/grid --properties easy.properties cegis
```

and then modify the property threshold in the file `tacas21-benchmark/grid/easy.properties`:

```
P>=0.927 [ F "goal" & c<CMAX ]
```

and rerun the command above. You can see that this specification is much harder to synthesize, yet overall the problem is still unfeasible. If we decrease the threshold even further:

```
P>=0.926 [ F "goal" & c<CMAX ]
```

then the synthesizer will be able to provide a satisfying parameter assignment. Also note that assignments provided by individual synthesis methods may differ since in this case the family contains multiple feasible solutions.




