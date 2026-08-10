# fabric-crowd-plane

Simulate a thousand people in one venue at 60 Hz, published at 20 Hz, with one entity for
each joint.

State: the gate is measured and the budget is proved against it. No simulator yet.

Bodies touch, pressure builds at a doorway, and an arch forms
across a gap and holds. The flow through that gap does not follow from how many people want
through it. This plane simulates that, live.

weft's packet is 100 bytes with 6 bytes of rotation. It cannot describe a whole articulated
body. Split the body across entities and the packet fits with no change at all.

MS-Human-700 has 85 joints. Not 206: that is the bones in a skeleton, a different count from
the model's articulation. It reports 81 bodies, 85 joints, 85 degrees of freedom, and 700
actuators, and the 700 is muscles.

A thousand people is then 85000 entities, 9 times the densest thing weft has run.

## The gate

`bench/gate_msk_step.py` advances one body and reports what a 60 Hz frame costs. MuJoCo
3.11.0, median of nine runs of two hundred steps.

| | |
| --- | --- |
| one `mj_step` | 509 us |
| model timestep | 2 ms, so a frame is 8 substeps |
| one body, one frame | 4075 us |
| budget for biomechanics | 14360 us |
| **bodies for each plane** | **3** |
| **planes for a thousand people** | **334** |

The fear was worse than the finding: a half millisecond timestep would have made a frame 33
substeps and one body the whole budget. It is 2 ms and eight.

The result still decides the design. **Biomechanics is a sample of the crowd, not the
crowd.** Three in a thousand is what the measurement allows, so a cheaper pose source for
the other 997 is required rather than optional.

## The budget is a proof

`spec/CrowdBudget.lean` holds every number as a theorem. Lean 4.33.0, no Mathlib.

    lean spec/CrowdBudget.lean

It has already earned its place twice. Before any code existed it caught the tick being
16666 microseconds and not 16667. Then the gate moved two constants at once, the joint count
and the body cost, and every theorem was rechecked without anyone having to remember which
figures depended on them.
