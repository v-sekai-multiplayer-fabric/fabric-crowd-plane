# Where the crowd plane stands

## What was broken, and was not what it looked like

The teleporting was never the timestep. `PUSH` applied a constant 1200 N for as long as a
stick was held, and a constant force has no speed it settles at, so a held stick accelerated a
body until the solver failed. The earlier fix, halving the step and running two substeps, cost
twice the compute and also diverged, only slower: 3765 m/s instead of 7539. The drive now
targets a speed. One 16.7 ms step per frame. Native plane holds 60.0 Hz at 40 bodies.

**The body was not a person.** Measured against Anny and MS-Human-700: legs 9 per cent short,
joint ranges 1.2 to 1.3 times wider than anatomy, hip flexion sign-inverted, and one flat
300 N m on every joint, which is 5.5 times a human elbow and 10 times a neck. A controller on
that frame finds strategies that are not balance. `protomotions/robot_configs/soma23.py` had
already split arms at half of legs; the prior art was installed the whole time.

## The corpus, after five sweeps

One clause explains the field. SMPL's licence bans training a network for commercial use, and
AMASS repeats it, so HumanML3D and every model trained on it inherits the ban. Meta's HumEnv
is CC BY-NC because its body is SMPL, not by Meta's choice. LAFAN1 is CC BY-NC-ND and most of
the motion matching ecosystem is MIT code over it.

| clean | why |
| --- | --- |
| O3DE, 28 min | an engine that had to clear its own demo assets |
| Quaternius, CC0 | game art, public domain, 8-direction and sitting |
| 100STYLE, CC BY | 4M frames, sidestep and idling, downloading |
| VR Balance, CC BY | falls and perturbation, downloading |
| Kimodo, Anny, SOMA, GEM-X | NVIDIA and NAVER, deliberately commercial-clean |

`bench/corpus.py` blocks 11 sources with reasons and refuses unknown provenance by default.
It also refuses things whose licence is fine and whose category is not: a Blueprint is not
motion, and neither is a bench.

## The gap, measured

The unit is the seven O3DE turning clips, 450 s, the weakest behaviour that corpus still does
well. Missing was 32 minutes. After the downloads land it is **15 minutes, and only two
behaviours: sitting and getting up.** Nothing found in five sweeps holds either. Generation
closes it in about nine minutes of compute.

## The plan

NVIDIA shipped this architecture: **ARDY plans, SONIC tracks.** Both Apache-2.0, both forked.

1. **Test the pretrained tracker first.** Load `motion_tracker/soma-bones` against a 100STYLE
   clip and see whether it stands. One day, and it decides whether anything below is needed.
2. **Teacher generates a command-labelled corpus.** Kimodo with root velocity constraints
   swept over a distribution: the constraint *is* the gamepad command, so labels are exact and
   free. `KimodoLocoMoGen`'s orchestrator does this already, for G1.
3. **Distil to a real-time student**, because 100 DDIM steps is not 60 Hz. Unnecessary if
   ARDY's SOMA checkpoint lands. Distillation does not reset a licence.
4. **Close the loop on contact.** When a neighbour shoves you the tracker leaves the
   reference, and the planner must re-plan from where the body actually is. Nobody has done
   this for a crowd. It is the product.

## State

Repos forked into the org and cloned under `/opt`: `weft-locomotion`, `weft-mdm`,
`weft-ardy`, `weft-wbc`, plus `weft-crowd-plane` and 93 GB of corpora in `weft-motion`.
Downloads: 3.3 of 22.9 GB, about two hours left.

**Three deployed apps still run the old build.** `weft-room` and `weft-plane` carry the
substep code and the unbounded drive.
