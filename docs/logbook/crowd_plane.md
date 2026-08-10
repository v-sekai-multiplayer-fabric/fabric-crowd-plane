# Crowd plane logbook

Every measurement of the crowd plane, with the conditions it ran under.

A number without its conditions is not a result. The same body costs 258 microseconds
measured alone and 433 measured inside a full plane, and 46 on the machine that will
actually run it. So each entry names the apparatus, the method, and the outcome. An entry
that turned out to be invalid stays here, and it says why.

The oldest entry is at the top, and a new entry goes at the bottom. This is the order of a
laboratory notebook. An entry records what happened at a time, and a later entry refers to
an earlier one. So the order must not change after the fact.

`../../spec/CrowdBudget.lean` holds the budget these feed. It holds the arithmetic and this
holds the measurements.

## Apparatus

Unless an entry says otherwise:

- **Desk**: Ryzen 7 3800X, 8 cores, Linux. Every entry before "On the platform" ran here.
- **Platform**: Fly `performance-2x`, 2 vCPU, 4 GB, region `sjc`, host reports "AMD EPYC".
- MuJoCo 3.11.0 through the Python bindings. The physics is C; the loop is Python.
- The benches are in `../../bench/`.

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

## The wire

`bench/wire_muscle.py`, `bench/wire_cheap_vs_nasty.py`, `bench/wire_dict.py`. Bytes for one
body for one frame.

| form | bytes |
| --- | --- |
| position and rotation for each joint, 100 B an entity | 3600 |
| rotations only, 12 bit, packed | 174 |
| cheap CBOR JSON-LD, zstd with the last frame | 884 |
| 49 muscles at their own bit depth, packed | 76 |
| packed then zstd | 83 |
| delta then zstd | 69 |
| static trained dictionary, 110 KiB | 72 |
| keyframe every 20 or 60 frames | 75 |
| streaming, full session history | 69 |
| order-0 entropy floor, delta | 53 |

Muscle space is V-Sekai's `godot-humanoid-project`, Apache-2.0, Lyuma and lox9973. A pose
is 95 scalars, each one axis of one joint normalised over an anatomical range the file
states. 49 of them are a body without fingers, eyes, or jaw.

Two rows are worth reading twice. Compressing the packed stream makes it **bigger**, and no
dictionary scheme reaches the entropy coder. A dictionary feeds LZ and LZ finds repeated
substrings; a bitpacked delta stream has none, because the values sit at different offsets
and smear across byte boundaries. What is left is redundancy in the symbol distribution,
which is exactly and only what an entropy coder takes. Cheap CBOR compresses well for the
opposite reason: it repeats its key names every frame.

Run-length encoding was checked and is not worth having. 13 percent of muscle deltas are
zero, but the runs are short and scattered, and an entropy coder already spends about 3
bits on a symbol that common.

## Real motion, and the correction it forced

`bench/wire_learned.py`. The synthetic gait above makes every muscle an independent
sinusoid, so it has no inter-joint coupling. Driving the tracked avatar in MuJoCo under
gravity and contact, in its own 26 degree of freedom joint space:

| coder | bytes/body/frame |
| --- | --- |
| order-0 entropy of deltas | 26 |
| order-1, context on the joint's own previous delta | 21 |

So the 53 byte figure was pessimistic: physically coupled motion compresses about twice as
well as motion assembled from independent sinusoids. Not a like for like swap, because 26
driven joints is not 49 muscles, so the direction is the result and not the ratio.

## The pose manifold, which is not there

`bench/wire_manifold.py` against sinew-mocap's calibrator set, `sinew-mocap/mount-drift`
release `calibrator-v1`: 11794 real poses, 25 subjects, 11 AddBiomechanics studies, 30
segments in the 6D continuous rotation representation.

The poses are natural and not a spread over the space. Two drawn at random sit 34 degrees
apart, where two uniform rotations sit 131 apart, and no segment has a spread over 60
degrees.

| components | of 180 |
| --- | --- |
| 90 percent of variance | 59 |
| 99 percent | 124 |

Truncating to 48 leaves a median segment 10 degrees wrong. Stripping the global heading
first, which linear PCA provably cannot represent, makes it slightly worse.

This contradicts an earlier claim in `spec/CrowdBudget.lean` that coordinated human motion
is low rank. That is a claim about a single activity and it does not survive 25 subjects and
11 studies. A pose is a small ball in a high dimensional space, not a thin sheet in one, so
a linear latent has nothing to take.

The set cannot answer the temporal question, which is where every gain has come from.
Consecutive rows are 30 degrees apart, so it holds a pose distribution and not a motion.

## On the platform

`bench/fly/run_all.py`. Fly `performance-2x`, `sjc`, one machine created, run once, and
destroyed. The image is `bench/fly/Dockerfile`, 72 MB.

| batch | median us | p90 us |
| --- | --- | --- |
| 14 | 41.02 | 52.56 |
| 28 | 39.35 | 44.10 |
| 56 | 46.37 | 51.48 |

Against 27.3 median and 31.4 p90 on the desk, the same body costs 1.7 times as much here.
The tail is wider too: 28 percent between median and p90 against 15 at the desk.

| vCPU | people at p90, desk | people at p90, platform |
| --- | --- | --- |
| 1 | 487 | 301 |
| 3 | 1280 | 830 |
| 4 | 1607 | 1064 |

Three vCPU held a thousand at the desk and hold 830 here. The crowd plane needs four, and
the venue machine goes from needing six to needing seven of the eight it buys.

Nothing about the design was wrong. The arithmetic held and the constant was measured on a
machine nobody deploys to.

## Two machines, two answers

The run above was repeated on a second `performance-2x` in `sjc`, same image, same
settings, a different machine.

| machine | median us | p90 us | people on 3 vCPU at p90 |
| --- | --- | --- | --- |
| `2870276b497228` | 46.37 | 52.56 | 830 |
| `d890411b973d18` | 53.85 | 65.74 | 681 |

25 percent apart on the tail, from the same image on the same size in the same region. This
is shared tenancy, and it is a larger effect than any tuning measured on the desk.

So a single run does not size a plane here. What sizes it is the worst machine the platform
will hand out, and two samples do not bound that either. The design number stands at the
worse of the two until a wider sample exists.

That also puts a floor under how much of this can be answered by benchmarking at all. A
plane that must hold 60 Hz on a machine it cannot choose has to degrade rather than assume,
which is an admission-control question and not a physics one.
