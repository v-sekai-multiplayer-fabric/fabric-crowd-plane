# fabric-crowd-plane

A thousand people in one venue. Simulated at 60 Hz, published at 20 Hz, with one entity for
each joint.

State: the budget is proved and nothing is built. Read the gate below before writing code.

## Why this exists

weft's only workload is a recording. An external traffic simulator writes positions to a
file, and everything downstream replays that file. A recording does not respond to anything,
so it proves the decode path and nothing about the system under load.

It is also the easy case. A vehicle rides one and a half dimensions, and the model forbids
two of them from sharing a point, so density has a ceiling built into the road. That trace
peaks at 8637 entities.

A crowd has no such ceiling. Bodies touch, pressure builds at a doorway, and an arch forms
across a gap and holds. The flow through that gap does not follow from how many people want
through it. This plane simulates that, live.

## One entity for each joint

A musculoskeletal human is 206 entities, and not one entity that carries a pose.

weft's packet is 100 bytes with 6 bytes of rotation. It cannot describe a 206-joint body.
Split the body across entities and the packet fits with no change at all.

A thousand people is then 206000 entities, which is 23 times the recorded traffic peak. This
is the first dense workload weft has had.

## The budget is a proof

`spec/CrowdBudget.lean` holds every number, and each one is a theorem. It typechecks with
Lean 4.33.0 and it uses no Mathlib.

    lean spec/CrowdBudget.lean

Writing the budget this way caught two errors before any code existed. The tick is 16666
microseconds and not 16667. The crowd is 23 times the recorded peak and not 24.

| | microseconds | where it comes from |
| --- | --- | --- |
| publish 206000 joint entities, on one tick in three | 257 | 1.25 ns each, measured |
| steer 1000 agents, ten neighbours each | 200 | assumed |
| contact, 1000 tapered capsules | 2000 | assumed |
| left for biomechanics | 14209 | what remains |

When a measurement replaces an assumption, the constant changes and the theorems hold or
fail. That is why the budget is not a comment.

## The gate

**Measure one MS-Human-700 step on one core before writing anything else.**

Musculoskeletal models integrate muscle dynamics far above the frame rate. A half
millisecond internal step makes one 60 Hz frame into 33 substeps, and a 500 microsecond
nominal step becomes 16 milliseconds, which is the whole budget for one body.

The number decides the shape of everything after it, and the spec already states what each
answer buys:

| one step | bodies for each plane | planes for a thousand people |
| --- | --- | --- |
| 100 us | 142 | 8 |
| 500 us | 28 | 36 |
| 2000 us | 7 | 143 |
| 5000 us | 2 | 500 |

The count is derived from the budget. It is never chosen.

## The three layers

**Steering** runs for all thousand, every simulation tick. A Generalized Centrifugal Force
Model in two dimensions. The force-based family is what captures pushing in a dense crowd,
which is why it is chosen over a velocity-based one. Nothing in the fabric has one, so this
is written here.

**Contact** runs for all thousand, every simulation tick. Tapered capsules, because a thigh
is wider at the hip than at the knee, and a plain capsule is wrong exactly where bodies
press together.

**Biomechanics** runs for as many bodies as the budget affords. MS-Human-700 in MuJoCo on
the CPU, driven by the steering velocity.

## The shape is already proved elsewhere

`lean-humanoid-rom` holds `TaperedCapsule`, with radii in integer micrometres. That is the
same unit as weft's packet, so no float drift stands between the physics, the proof, and the
wire.

Its `taperedCapsulesCollide` is approximate. It samples three points on each capsule and
checks nine pairs. The physics engine does the exact test. Measuring where the two disagree
bounds the error of that approximation, and the result belongs back in that repository.

## What this does not do

It does not reach weft's control plane. The BEAM reads the data plane through a NIF and
never speaks the bus, and the loop between them is unwritten.

It does not decide what fills the gap between published frames.

It does not put Python or a GPU in the tick loop.
