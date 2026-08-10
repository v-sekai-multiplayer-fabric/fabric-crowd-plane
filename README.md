# fabric-crowd-plane

**Every number is measured. Steering is written. Nothing else is.**

Simulate a thousand people in one venue at 60 Hz, published at 20 Hz, with one entity for
each joint.

weft's packet is 100 bytes with 6 bytes of rotation. It cannot describe a whole articulated
body. Split the body across entities and the packet fits with no change at all.

The crowd uses the locomotion model: 81 bodies, 36 joints, 100 actuators. The full model is
85 joints and 700 actuators, and the 700 is muscles. A walking crowd needs no hands and no
face, and the locomotion variant costs a quarter as much.

## The budget

| | us each frame | |
| --- | --- | --- |
| publish 36000 joint entities | 45 | 1.25 ns each |
| steer 1000 agents | 280 | `bench/bench_steering.cpp` |
| contact, 1000 free capsules | 2433 | one MuJoCo step each frame |
| left for biomechanics | 13908 | |
| one locomotion body | 950 | 8 substeps; muscles need them |
| **bodies for each plane** | **14** | |

`spec/CrowdBudget.lean` holds all of it as theorems. Lean 4.33.0, no Mathlib.

    lean spec/CrowdBudget.lean

## Three findings

**Free capsules need no substeps.** The eight substeps come from muscle dynamics. A capsule
carries none, so it steps once each frame: 2433 us against 15231 at a 2 ms timestep.

**Threads do not help the capsules.** A thousand form a thousand islands, and at one contact
each there is nothing to solve. 1, 4, 8 and 16 threads land within 4 percent.

**A hundred people need no approximation.** Eight cores carry 112 bodies, so every one of
them is a real musculoskeletal body. A thousand needs 72 cores, and the bus is shared
memory, so a venue cannot be split across machines.

## One engine

MuJoCo does contact and biomechanics both. No second physics library.

It has no tapered capsule primitive. A tapered capsule is a round cone, which is closed
form, and `mjplugin.h` wants exactly `sdf_distance` and `sdf_gradient`. The attributes map
one to one onto `lean-humanoid-rom`'s `TaperedCapsule`: `p0`, `p1`, `r0`, `r1` in integer
micrometres, the same unit as weft's packet.

## Next

The venue, the bodies wired to the steering, the publish path.
