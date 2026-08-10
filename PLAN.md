# What this is, and the shortest path to it

## The product, in one line

**In VRChat you walk through your friends. Not here.**

Bodies are physical. You can push someone and they move. You can lean into a crowd and it
resists. That is the whole feature, and everything below either delivers it or pays for it.

## The mechanism

A **physics-based character controller**, driven by a VR controller or a gamepad the way a
console game is driven: stick in, locomotion out. Not kinematic movement with physics painted
on top. A body that walks because it is pushing on the floor can also be pushed, and one that
slides along a capsule cannot.

Standing still is the degenerate case of that controller, not a separate feature.

## The constraint

**15 USD a month on Fly, as a ceiling and not a target.** The system must be unable to
exceed it, which makes person-hours the quantity to derive and admission control the thing
that enforces it.

## What is measured, and where

All figures are on the hardware that would run it. `docs/logbook/` holds the
apparatus for each.

| quantity | value | where |
| --- | --- | --- |
| one body, one frame, in a real 60 Hz loop on Fly | 55 us | measured |
| concurrent bodies, one core, physics at half the tick | about 139 | measured |
| wire, one body, one frame | 21 bytes | measured |
| person-hours for 15 dollars a month | about 43000 | derived |
| the same, as always-on players | about 59 | derived |
| a room that wakes from stopped to its first tick | 3.4 s | measured |

The venue is **one Fly machine, `shared-cpu-2x` with 1 GB**, stopped whenever it is empty,
with FoundationDB single-node on the same box in `ssd` mode, backed up to the S3-compatible
endpoint. A 1 GB volume at 15 cents a month is the only cost that accrues with nobody
present.

Shared rather than dedicated because it was measured rather than assumed: at 22 percent load
the two classes are the same machine, 3679 microseconds against 3594 at the median, one
missed tick in 36000 against none. Dedicated buys a tighter tail and costs 5.6 times, and an
earlier draft of this plan bought it on the strength of a 237 millisecond figure that turned
out to be a machine running at 99 percent rather than a machine being shared.

**Egress is now most of the bill.** At the lean wire it is 65 percent of the cost of a
person-hour and the machine is the rest, so the next optimisation is bytes and not cycles.
Halving the wire again is worth more than any remaining physics work.

## What is built

- A crowd that actually touches: many avatars in one MuJoCo model, one contact solve,
  person-to-person contacts confirmed. `bench/touchable.py`.
- The cost model, as 200 theorems that fail loudly when a constant moves.
  `spec/CrowdBudget.lean`.
- The wire: muscle-space, per-muscle bit depth from anatomical range, delta, order-1 context
  coding. 79 times smaller than sending joint positions.
- Deployment and measurement on Fly, including what breaks. `bench/fly/`.

## What is not built, and it is one thing

**The controller.** Everything else is scaffolding around a body that cannot stand up.

A derived controller does not work: PD to a stance pose plus an ankle strategy falls in five
seconds. A linear policy trained with ARS does not learn it in 2750 iterations. Both results
are recorded, and both say the same thing, which is that standing balance for a 27 degree of
freedom humanoid is a real problem and not a gain to tune.

## The steel thread

The prototype is one thin path that touches every layer, end to end, and it is not a demo of
physics alone. It is:

**Two people in a room push each other. One walks through a doorway. The room on the far side
is a different machine that was asleep. They arrive with their state and keep pushing.**

Every part of that sentence is a layer, and each is there because leaving it out would let a
later layer cheat:

| the sentence | the layer | state |
| --- | --- | --- |
| two people in a room | one MuJoCo model, one contact solve | measured, `bench/touchable.py` |
| push each other | contact between articulated bodies | measured |
| walk | the character controller | in training |
| through a doorway | the airlock, hiding a 3.4 s wake | not built |
| a different machine | placement, and a room that was stopped | not built |
| that was asleep | scale to zero, which is what 15 dollars buys | measured, `bench/fly/room.py` |
| with their state | flush, then hand off | designed; the replicated store was deleted in #96 |
| and keep pushing | the same contact solve on the far side | measured |

The migration is in the thread on purpose. Without it the 15 dollar price is a lie, because
the price comes from machines that stop, and machines that stop mean players that move.

## The speedrun, in order

1. **A controller that stands and takes a stick.** It is learned. Two routes:
   - *ProtoMotions on Newton, trained here on the 4090.* The right answer: ours, and it
     matches the simulator we run. Blocked today on an upstream Warp codegen bug in
     `mujoco_warp`, which is a one-line fix in their solver kernel.
   - *ProtoMotions on IsaacLab with NVIDIA's weights.* Works immediately, large install, and
     a policy trained in a simulator we do not run is a policy we cannot change.

   A kinematic root with physical limbs was considered and is **rejected**. It is what games
   ship and it is faster to a demo, and a kinematic root cannot be pushed. Being pushed is
   the feature, so the shortcut deletes the product. This is the same objection that makes
   the pinned-root measurement in the logbook a cheat rather than a result.
2. **A venue**: floor, walls, one doorway.
3. **The publish path**: joint entities onto the ring at 20 Hz in muscle space.
4. **One machine on Fly**, scale to zero, admission on measured tick load and on the
   person-hour budget.
5. **Sixty people in a room, pushing each other.** That is the demo, and it is the pitch.
6. **One of them walks through a doorway onto a second machine and keeps pushing.** That is
   the steel thread closing, and it is what proves the price rather than the physics.

## What is deliberately not being built

Cross-machine interest fanout, and per-tick state between machines. A touchable crowd is one
contact solve on one machine, so a venue larger than one machine cannot share the only
feature worth selling.

The **airlock stays**, for a reason its first design got wrong. It is not a way to make a
venue bigger. It is the seam where the machine running you changes, which happens because
rooms stop when empty and that is what makes the price. `docs/logbook/crowd.md` records the
retirement and the reversal.
