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
| wire, one body, one frame, as fabric packets | 108 bytes | measured |
| person-hours for 15 dollars a month | about 17500 | derived |
| the same, as always-on players | about 24 | derived |
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

**Egress is now nearly the whole bill.** The wire is `XRGridEntityPacket` from
`lean-entity-packet`, which the crowd plane speaks rather than inventing its own, and which
costs 108 bytes for a body once compressed against 21 for a body-oriented encoding. That is
deliberate: one format, one conformance test, one already-verified decoder, at the price of
24 always-on players rather than 59. Egress is then 89 percent of a person-hour, so no
remaining physics work changes the bill.

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

## What `proto/server.py` is, and is not

It is a **viewer**, and it breaks three rules to be one: the plane is Python where the rule
says C++, it talks over a WebSocket where the transport is HTTP/3 and WebTransport and never
HTTP/1.1, and it reaches clients over sockets where planes reach things over iceoryx2.

It is kept because looking at the physics is worth something and it took an hour. It is not
the steel thread and must not be described as one. A steel thread is thin and **real**; that
file is thin and fake, and it exercises none of the layers the design is made of.

The one charge it does not answer to is speed. `bench/fly/tick_loop.py` is also Python and
held 60 Hz on Fly with one missed tick in 36000 at 60 bodies. Python can carry a
prototype-scale tick. It cannot prove the design.

## The steel thread

The prototype is one thin path that touches every layer, end to end, and it is not a demo of
physics alone. It is:

**Two people in a room push each other. One walks across a boundary. The room on the far side
is a different machine that was asleep, and was woken while they were still walking. They
arrive with their state, in 152 milliseconds, and keep pushing.**

Every part of that sentence is a layer, and each is there because leaving it out would let a
later layer cheat:

| the sentence | the layer | state |
| --- | --- | --- |
| two people in a room | one MuJoCo model, one contact solve | measured, `bench/touchable.py` |
| push each other | contact between articulated bodies | measured |
| walk | the character controller | in training |
| across a boundary | predictive pre-wake, no doorway | **built**, `proto/handoff.py` |
| a different machine | two zones, one boundary, single writer asserted | **built**, `proto/two_rooms.py` |
| that was asleep | woken while they walked, 2.6 to 2.8 s real | **built**, `proto/fly_rooms.py` |
| with their state | flush, then hand off | designed; the replicated store was deleted in #96 |
| and keep pushing | the same contact solve on the far side | measured |

The migration is in the thread on purpose. Without it the 15 dollar price is a lie, because
the price comes from machines that stop, and machines that stop mean players that move.

### The native side, honestly

`native/dataplane` is 135 lines: a seqlock ring and a throughput smoke test. It does not link
iceoryx2, does not run MuJoCo, and has no tick loop. `native/nif` is 112 lines and works. So
the plane is unwritten and the ring under it is not.

That splits the thread into two pieces with very different costs.

**The plane, in C++, writing the ring, read by the BEAM through the NIF.** About 300 lines,
because three of the four parts exist. Every link in that chain is a layer the design
specifies, so it is a real thread with the client cut off the end. This is next.

**The edge.** A WebTransport server means a QUIC stack, and that is days rather than hours.
It costs the same whether it is built before the plane or after, so it goes after.

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

The **airlock is gone**, for the second and final time. It existed to hide a 3.4 second
machine wake, and the predictive bound in `lean-fabric-protocol` takes the wake off the
critical path entirely: watch who is approaching, start the far side while they are still
walking, hand over in the time a flush takes. A boundary is just a boundary.
`docs/logbook/crowd.md` records the retirement, the reversal, and the second retirement.
