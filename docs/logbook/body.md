# The body, and what it costs

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

Oldest entry first. A new entry goes at the bottom.

## The biomechanical body, and what it costs

`bench/gate_msk_step.py`, `bench/compare_bodies.py`. MS-Human-700, Apache-2.0, subtreed at
`thirdparty/ms-human-700`.

| model | bodies | joints | actuators | us/body/frame at scale |
| --- | --- | --- | --- | --- |
| MS-Human-700 full | 85 | 85 | 700 | 4075 |
| MS-Human-700 Locomotion | 81 | 36 | 100 | 421 |
| tracked avatar | 14 | 27 | 26 | 48 |

The tracked avatar has nearly the same degrees of freedom as the locomotion model, 32
against 36, and costs a ninth as much. So degrees of freedom were never the cost.

## Where the cost actually was

`bench/profile_stages.py`, MuJoCo's own timers, batch of 28.

| stage | us | share |
| --- | --- | --- |
| POSITION | 169.1 | 81% |
| ... POS_KINEMATICS | 76.4 | 37% |
| ... POS_COLLISION | 79.6 | 38% |
| CONSTRAINT | 22.0 | 11% |
| ACTUATION | 4.3 | 2% |

`bench/ablate_msk.py` disagreed with this and was wrong. Disabling actuation saved 3
percent, which suggested muscles were cheap. They are not. `mjDSBL_ACTUATION` skips the
actuator force and not the tendon geometry, and the model threads 100 tendons through 430
wrap points across 2856 sites, all transformed every position stage. The ablation measured
a flag rather than a cost.

## Levers that did not work

| lever | outcome |
| --- | --- |
| solver iterations, 100 to 5 | no change, within 1 percent |
| thread pool, 1 to 16 threads | no change, within 4 percent |
| MJX on CPU, batch of 64 | 2177 us/body/step against 217. Ten times slower |
| collision meshes disabled | 1 percent |
| all contact disabled | 8 percent |
| contact and actuation disabled | 11 percent |

MJX also refuses the model until every mesh margin is zeroed, and compiles for about 25
seconds for each batch shape. It is built for thousands of environments on a GPU.

## Timestep, which was the only tuning lever that moved

Single locomotion body, one 60 Hz frame.

| timestep | substeps | us/frame |
| --- | --- | --- |
| 2 ms | 8 | 981 |
| 4 ms | 4 | 498 |
| 8 ms | 2 | 255 |

Driven at full muscle load for 10 simulated seconds, every one stayed stable and warned
about nothing.

## Solver iterations, measured again with a penetration check

`bench/solver_iterations.py`, tracked avatar, 16.7 ms timestep, 1200 driven frames at 60
newton-metres on every actuator.

| iterations | us/body/step | deepest penetration |
| --- | --- | --- |
| 10 | 26.09 | 90 mm |
| 4 | 25.82 | 133 mm |
| 2 | 24.13 | 130 m |
| 1 | 17.36 | 960 m |

The earlier entry that said iterations were free is not retracted. It was true of the
musculoskeletal body, which barely touches anything and so has nothing to solve. A crowd
pressing together does. Below four the solve stops converging and bodies pass through the
floor, and nothing is reported: `qpos` stays finite and the run completes. Only the
penetration check finds it.

The driving here is violent and puts 90 mm on the safe setting too, so this ranks the
settings and certifies none of them.
