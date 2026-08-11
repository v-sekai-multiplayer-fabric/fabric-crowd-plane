# The crowd that touches

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

Oldest entry first. A new entry goes at the bottom.

## The airlock is retired

The measurements stand: a stopped room wakes to its first tick in 3.4 seconds over three
restarts, a cold create takes 5.9, and 60 occupants on one core run at a load of 0.21 median
and 0.31 at p99 with no missed ticks in 1199.

The mechanism they were taken for does not. The product sells solid bodies, an airlock is
the seam where solidity stops, and one contact solve already holds about 2000 people. Any
venue worth building is one room.

The cold start numbers keep their value under a different heading. Scale to zero makes an
empty room free, which is what the 15 dollar budget rests on, and 3.4 seconds is how long a
returning player waits. Neither has anything to do with travel between rooms.

## The feature, measured for the first time

`bench/touchable.py`. Every measurement before this one gave each avatar its own MjData, so
avatars passed through one another. That is cheaper and it is not the product. This is one
model, one contact solve, and avatars that collide with each other.

Desk. 100 avatars, varying how close they stand. They have no balance controller, so they
collapse into a heap, and a heap presses far harder than a standing crowd. Read these as an
upper bound on cost.

| spacing | us/frame | p99 us | person-person contacts | load at p99 |
| --- | --- | --- | --- | --- |
| 0.60 m | 6046 | 34657 | 331 | 2.08 |
| 0.75 m | 5879 | 8961 | 277 | 0.54 |
| 1.00 m | 4532 | 7328 | 159 | 0.44 |
| 1.50 m | 3395 | 4871 | 0 | 0.29 |
| 2.50 m | 3421 | 4755 | 0 | 0.29 |

Two things follow, and the second is the important one.

Touch is not free. A body that touches nobody costs 34 microseconds a frame here. The same
body at shoulder distance costs 59. So contact roughly doubles a person, and it does it in a
solve that cannot be split across machines.

And the cost arrives at the tail, not the median. At 0.6 metres the median is 6046 and the
p99 is 34657, which is 5.7 times worse. A 60 Hz deadline is met at the tail. So the crowd
that breaks a room is not the average crowd, it is the moment the average crowd bunches, and
nothing in the median warns of it.

Scaling at 0.75 m spacing:

| avatars | us/frame | p99 | load at p99 |
| --- | --- | --- | --- |
| 25 | 1596 | 2300 | 0.14 |
| 50 | 3224 | 7575 | 0.45 |
| 100 | 5489 | 8208 | 0.49 |
| 200 | 11589 | 23717 | 1.42 |
| 400 | 19757 | 83015 | 4.98 |

So the touchable ceiling is about 150 on the desk and about 90 on Fly, against the 500 this
logbook has been assuming. The 500 came from a thousand free capsules at 2.4 microseconds
each, and a free capsule is not a person: an avatar is 14 capsules on 27 joints, and when two
of them press the solver couples both articulated bodies into one island.

The next measurement is not an optimisation. It is a balance controller. These bodies are
falling over, and a heap of ragdolls is the worst contact case there is. A standing crowd
touches at the shoulders. Whether the ceiling is 90 or 500 depends on that number, and it
does not exist yet.

## The stance controller, which does not work yet

`bench/stance.py`. The bodies in the entry above have no controller, so they lie in a heap,
and a heap is not a crowd. A controller was needed before the ceiling meant anything.

An early draft pulled each root toward its waist tracker. That is cheap, robust, and assumes
a headset. Most bodies in a crowd are unattended, so it was thrown away. What is needed is a
body that stands on its own feet with nothing to hold on to.

Two faults in the model had to go first, and both were the model rather than the controller.

The feet were capsules, `fromto` with a radius, which is a line contact. A body cannot
balance on two lines. They are boxes now, 0.23 by 0.09 metres, and the sole is the base of
support the ankle strategy works against.

The actuators were 150 Nm. A 69.7 kg body needs about 275 Nm at the hip to hold its own
torso out at a 0.4 metre lever, so no controller could have stood it up. They are 300 Nm now,
derived from that figure.

With both fixed, and PD to a stance pose plus a linear-inverted-pendulum ankle strategy in
both the sagittal and frontal planes, a single body still does not hold a stance. It falls
in about five seconds, gets itself back up at around twenty, and falls again by thirty. The
gains are derived rather than guessed, so this is not a tuning failure. Standing balance for
a 27 degree of freedom humanoid needs a whole-body controller, a stepping strategy, or a
learned policy, and none of those is a gain.

## What a standing crowd costs, measured around the missing controller

Desk. Roots pinned upright each frame so the bodies stand, limbs still physical, contact
still solved between people. This measures the crowd the controller is supposed to produce,
without waiting for it.

| avatars | spacing | us/frame | p99 us | person-person | load at p99 |
| --- | --- | --- | --- | --- | --- |
| 100 | 0.75 m | 3055 | 4311 | 28.5 | 0.26 |
| 200 | 0.75 m | 6394 | 7648 | 58.8 | 0.46 |
| 400 | 0.75 m | 13834 | 16542 | 119.5 | 0.99 |
| 200 | 0.60 m | 8052 | 9573 | 156.1 | 0.57 |

A standing crowd is about twice as cheap as a fallen one, and it touches far less: 28
person-to-person contacts at 100 standing against 277 at 100 collapsed. Both numbers are
real. A crowd standing at arm's length barely touches, and the touching only starts when it
packs to 0.6 metres.

So the ceiling is about 400 on the desk at a full tick, about 200 with half the tick left
for everything else, and about 120 to 150 of those on Fly. That is above the 80 this
competes with and well under the 500 this logbook assumed for most of its length.

The pin is a cheat and it has to go. A pinned root cannot be pushed, and being pushed is the
entire product. The number above is what the crowd costs once a stance controller exists.
Until then there is standing or there is touching, and not both.

## UN-RETIRED: the airlock, for a reason the retirement missed

The entry above retires the airlock, on the grounds that it is the seam where touch stops and
that any venue worth building fits one contact solve. Both claims still hold. The conclusion
drawn from them does not.

What it missed is that **migration is not a travel feature**. It is the mechanism underneath
the price.

The 15 dollar venue costs 15 dollars because the machine stops when the room is empty and
wakes to its first tick in 3.4 seconds, measured. That is scale to zero, and it is worth 5.6
times the bill. But a room that sleeps is a room players are moved into and out of, so
scale-to-zero **is** migration seen from the outside.

And one machine holds 139 people at the measured cost. The 140th has to go somewhere.

So there are three reasons a player crosses machines, and none of them is a travel mechanic:

| why | how often | what it costs if it is visible |
| --- | --- | --- |
| the room was asleep and had to wake | every first arrival | 3.4 seconds of nothing |
| the room is full at 139 | at capacity | a refusal, or a jump |
| the machine died | rarely | a reconnect, and lost state without a store |

An airlock is what turns each of those from a freeze into a walk. That is a much better
argument than the one it was retired on, and it is the one that should have been written
first.

### What this changes about the shape

The airlock is not a doorway to another *place*. It is a doorway to another *machine*, and
the room on the far side may be the same room. That is the part the earlier design got
backwards: it treated the airlock as a graph edge between venues, when it is really the
seam where the process running you changes.

### CORRECTION: a planned crossing loses nothing

An earlier version of this paragraph said a crossing needs `Weft.Actor` to write to disk,
that it does not, and that a doorway would therefore lose everything. That confused the code
with the design and got the consequence backwards.

`Weft.Actor.Store` specifies a local SQLite write-ahead log, which is disk, with **async
replication to FoundationDB** behind it. The cost is stated in the module itself: a crash can
lose the last few commits that were not yet replicated. That is the deliberate trade, and it
is the right one, because a synchronous FoundationDB commit is about a millisecond and this
is off the write path.

The important part for an airlock is that **a crossing is planned**. A player walking through
a doorway is not a crash. The actor knows it is about to move, so it flushes and then hands
off, and the lazy replica is not what carries it. The lazy path only matters when a machine
dies without warning, and losing the last few commits then is what the design already accepts
everywhere else.

So the doorway does not need new durability guarantees. It needs a flush-then-handoff, which
is a smaller thing.

What is genuinely missing is the code rather than the design. `Weft.Actor` holds a memory map
today, and the prototype of the replicated store, `Weft.Actor.Store.Replicated` and its
`.Replicator`, was deleted because CI kept failing on it. That deletion was about a flaky
test rather than a wrong design, which is worth remembering before rebuilding it from
scratch.

## The doorway, built

`proto/airlock.py`. A crossing is a small state machine: open, sealed, arriving.

    0.00s  sealed with 3
    0.00s  bound to room-33
    3.41s  far side ready and state flushed
    5.01s  held 1.59s so the walk covers the wake
    5.01s  3 admitted to room-33

Three things it gets right, and each is a measurement rather than a preference.

**The wake and the flush overlap.** Waking a stopped machine is 3.4 seconds, measured over
three restarts, and a planned flush is a fraction of that. Run in parallel they cost 3.41
rather than 3.55 in series, because nothing about one waits on the other.

**The walk is longer than the wake, on purpose.** A five second transit covers a 3.4 second
wake with 1.6 seconds spare. If the transit finished first the player would stand in a sealed
room waiting for a machine, which is the freeze the doorway exists to hide. So the minimum
transit is not a feel decision: it is the measured wake plus margin.

**The destination is bound while the batch is inside**, not when the doorway was built. A room
needs one doorway rather than one for each place it connects to, which is the whole reason
this shape was worth keeping after the first design was retired.

### What it does not do yet

The `place`, `wake`, and `flush` calls are seams with defaults that sleep for the measured
durations. Wiring them means the control plane choosing a machine, Fly starting it, and
`Weft.Actor` writing to disk, and the last of those is the code deleted in #96.

So the doorway is real and what it opens onto is simulated. That is the honest state, and it
is the right order: the timing budget is the part that could have been wrong, and it is not.

## RETIRED AGAIN: no airlock. The wake was never on the critical path.

The doorway built in the entry above is deleted. It existed to hide a 3.4 second machine wake
behind a 5 second walk, and hiding it was the wrong idea: **the wake does not have to be on
the critical path at all.**

`lean-fabric-protocol/core/WaypointBound.lean` derives a migration budget from
`maxTravelTicks = ceil(simDiameter / vMaxPhysical)`. An entity cannot move faster than
vMaxPhysical, so there is always a bound on the earliest it can reach a boundary. A bound on
arrival is a warning, and a warning is enough to start the machine early.

`proto/handoff.py`, at a horizon of 1.5 times the wake:

    walking at 1.4 m/s, 10 m from the boundary
       2.59s  ada is 5.1s from the north wall, waking room-07
       9.15s  ada crossed into room-07, waited 15 ms

    running at 3.0 m/s, 10 m from the boundary
       0.00s  ada is 3.3s from the north wall, waking room-07
       4.39s  ada crossed into room-07, waited 15 ms

**152 milliseconds at the seam**, which is the flush and nothing else. The runner is inside
the horizon at the first tick; the walker enters it at 2.59 seconds. Both arrive at a room
that is already running.

### Why the horizon is affordable

The worst case in `WaypointBound` is vMaxPhysical, which is 30 m/s at 60 Hz. Waking every room
an entity could reach at 30 m/s would wake all of them, since 3.4 seconds at that speed is 102
metres and a room is 30. But vMax is a **bound**, not a speed. Watching actual velocity puts
the walker's horizon at 4.8 metres and the runner's at 10.2, which is a fraction of a room.

So the hard bound guarantees correctness and the observed velocity makes it cheap, which is
the shape of every good predictor.

### What this deletes

The airlock, for the second and final time. The first retirement was for a reason that was
true and incomplete: the seam is where touch stops. It came back because migration is what
makes scale-to-zero possible and scale-to-zero is what makes the price. Both of those still
hold. What has changed is that the migration no longer needs hiding, so there is no mechanism
left to build, only a prediction to run.

A boundary is now just a boundary. Players walk across it.

## Interest management, from the spec

`proto/interest.py`, against `lean-interest-mgmt/core/AuthorityInterest.lean` and the
`ghostBound` formula proved in `lean-spatial-oracle/core/Formula.lean`.

The spec separates two things this prototype had been running together.

**Authority** is the zone advancing an entity's physics. Exactly one, always. **Interest** is
a read-only ghost held by a neighbouring zone, and there can be many. The registration rule is
not a radius: an entity enters a zone's interest when its k-tick kinematic expansion overlaps
that zone, where the expansion is

    ghostBound v a_half k = v*k + a_half*k*k

with monotonicity in v, a and k proved, which is what makes it safe as a bound.

    two 15 m zones, k = 30 ticks, hysteresis = 240 ticks
    ghostBound at 1.4 m/s over 30 ticks =  0.70 m
    the same at vMaxPhysical            = 15.0 m

    t= 5.20s  x=14.30m  GHOST      ada -> zone-b   (reach 0.7 m overlaps zone-b)
    t= 9.68s  x=20.58m  AUTHORITY  ada -> zone-b   (240 ticks inside)

Ghosted 0.7 metres before the border. Authority moved 4.5 seconds later and 5.6 metres past
it. Different questions, different answers, and an entity that brushes a boundary is ghosted
at once and never migrates at all.

### The same predictor, twice

`handoff.py` took a machine wake off the critical path by predicting who was approaching a
boundary. This registers a ghost by predicting the same thing. Both are `ghostBound`, and both
work for the same reason: **vMaxPhysical guarantees correctness and observed velocity makes it
cheap.** 0.70 metres against 15.0 is a factor of twenty, and the twenty is free because the
bound is only needed when the estimate is wrong.

### What it settles about the wire

Every wire measurement in this book assumed four near bodies and seventy far ones, with
nothing deciding which was which. This decides it, and it decides it per zone rather than per
player, which is the cheaper shape: a ghost costs a zone once, not once for each observer who
can see it.

### What it does not have yet

The spec puts a causal vector clock on each replica, `RelReplica` with `VClock`, so staleness
is causal rather than wall-clock. This implementation has no clock on a ghost at all. That is
the next thing to read rather than to invent.

## The thread closes: two rooms, one boundary, a player crossing

`proto/two_rooms.py`. Two zones, each authoritative over its own half and each with its own
contact solve. room-b starts stopped.

    t= 1.32s x= 7.87m  WAKING    room-b (5.1s out, it is asleep)
    t= 5.92s x=14.31m  GHOST     ada into room-b   (reach 0.7 m overlaps)
    t= 6.42s x=15.01m  CROSSED   into room-b, waited 153 ms
    t=10.40s x=20.58m  AUTHORITY ada -> room-b     (240 ticks inside)
                                  room-a released it; exactly one holder, checked

Four mechanisms in the right order, each built separately and none of them adjusted to make
this run: the approach is predicted and the far room woken while the player walks, a ghost is
registered when the kinematic expansion overlaps, the crossing costs a flush, and authority
follows four seconds later once presence is continuous.

**room-b was woken in 3.40 seconds, entirely while ada was still walking.** The player waited
153 milliseconds, which is the flush.

### A single-writer violation, and why it is worth writing down

The first run ended with both rooms claiming the entity:

    room-a[up] auth=['ada']    room-b[up] auth=['ada']

The transfer read the old owner **after** `ist.step` had already reassigned it, so the release
compared a room against itself, decided nothing needed releasing, and left two writers. Every
line of output looked correct. The invariant is what caught it, and only because it was
checked rather than assumed.

That invariant is not a detail here. `Weft.Actor` rests on it: one process for each entity,
mailbox ordering doing the serialisation, no leases and no fencing. Two writers means the
serialisation is gone and nothing downstream notices until state diverges. So the assert stays
in, at the moment of transfer and at the end of the run.

### What is still standing in

The rooms are processes rather than machines, and `wake` sleeps for the measured duration
rather than calling `flyctl` — though `proto/fly_rooms.py` does call it, and three cold starts
came back in 2.64, 2.79 and 2.77 seconds. The flush is a sleep, because the store it should
call is the code deleted in #96.

Neither of those is a question about whether the design works. They are wiring.

## There is nothing to flush, and two documents disagree about why

The crossing budgeted 150 milliseconds to flush an actor's state before handing it over. That
was modelling a design weft does not use.

`CLAUDE.md` and `fabric-store-plane/prove_handoff.c` agree: **an actor has no local database
file.** SQLite runs over a VFS whose pages are in FoundationDB, and `PRAGMA
journal_mode=MEMORY` stops it writing a journal. So a commit is already durable and already
visible to every other machine. A handoff is a close and an open, and `prove_handoff.c` exists
to demonstrate exactly that: two processes sharing nothing but FoundationDB, the reader with
no file to copy and no restore step.

What remains is the open on the far side, which is a FoundationDB read path. A synchronous
FoundationDB transaction was measured at about 1.9 milliseconds, so the crossing is a few
milliseconds.

    t= 6.42s x=15.01m  CROSSED   into room-b, waited 11 ms

Down from 153.

### The disagreement

`lib/weft/actor/store.ex` describes something else entirely: a local SQLite file for each
actor in WAL mode, async replication to FoundationDB, and a hydrate-on-open step to rebuild
the local file after a handoff. That design needs a flush, because a handoff must wait for the
replicator to catch up.

The two cannot both be right. One says the file does not exist; the other builds replication
and hydration around it.

`CLAUDE.md` is the authority and `fabric-store-plane` is the implementation, so **the moduledoc
is stale**. It also explains the shape of what #96 deleted: `Store.Replicated` and its
`Replicator` were building the moduledoc's design, and the deletion note says they replicated
logical key and value rows rather than WAL frames, which is a bug in a design that should not
have been there.

So the answer to "rebuild what #96 deleted" is **no**. What it deleted was an implementation
of a superseded design, and the store this project actually wants already exists in another
repository with a proof beside it.

That is worth more than the eleven milliseconds. An hour of work was about to go into a
component the architecture had already replaced, and the only thing that caught it was reading
the implementation instead of the moduledoc that described it.

## Places to sit, because a sit needs something under it

Three of the five generated sitting clips put the pelvis at 0.54 to 0.55 m and held it there
for seconds. That is a real chair height and there was no chair. Kimodo generates a body and
nothing else, and the simulator has no furniture either, so the reference asks for a
quasi-static pose in mid air and the physics can only drop the body. **The motion was never
wrong. The world was missing.**

`bench/places.py` is the world. For physics a chair is a box: what a body needs from a chair
is a support surface at a height, clearance for the legs, and an edge to push off. No art is
required, and a primitive carries no licence, which is more than any mesh in this project can
say.

| place | height | why that number | what it teaches |
| --- | ---: | --- | --- |
| step | 0.18 | IRC maximum riser 0.197 m | stepping up and down, sitting on a kerb |
| ledge | 0.30 | low wall | perching, pushing up with the hands |
| sofa | 0.40 | lounge seating, 0.38 to 0.43 | a deep low sit and the hard rise out of it |
| chair, bench | 0.45 | EN 1729 adult seat height, 0.43 to 0.46 | sit, settle, stand |
| stool | 0.65 | counter stool for a 0.90 m surface | perching with the feet unsupported |
| table | 0.74 | EN 527 work surface, 0.72 to 0.76 | leaning on, pushing off, waist obstacle |
| floor | 0 | every scene already has one | cross legged, lying, and getting up |

**No height here was chosen.** Seat and step heights are ergonomic and building standards and
each row names the one it comes from, in the same way `motors.py` takes torque from measured
maxima rather than from a number that felt right. A row that cannot cite a standard is a bug.

The catalogue also gives the check that was missing. A body seated on a support has its pelvis
about 0.06 m above it, so a chair means a pelvis at 0.51 m. The three failed clips sat at 0.54
to 0.55. They were not nonsense, they were **furniture-shaped motion with no furniture**, and
that is now testable rather than something to notice by eye.

protomotions takes these directly: `BoxSceneObject` with width, depth and height is a first
class primitive, and `--scenes-file` passes them to a training run. It ships no scenes of its
own. `places.py --mjcf` emits the same set for the crowd plane, and the file loads in MuJoCo
with seven bodies whose top surfaces measure back at the stated heights.

### Where this came from

Naughty Dog's post system, from Allen Chou's GDC 2023 talk, whose transcript is in
`/opt/weft-talks`. A post is a spot in the world picked for a gameplay purpose, generated
across the navigable space and then scored:

> We rate or score each post using a set of post criteria. And if the final score is zero, we
> reject a post.

The lesson is not the furniture, it is the direction. Do not author a sit and hope the world
suits it. Generate candidate spots from the world, score them, and reject the zeros. Under
that rule a pelvis at 0.55 m with no support scores zero and never becomes a reference.

### Where a box stops being a chair

A solid box at 0.45 m is a seat and nothing else. A real chair is a seat plate on legs, and
the difference is not decoration: **there is no space under a solid box for feet.** Sitting
puts the feet back under the knees, standing up drags them further back still, and a body
that cannot do that either clips through the prop or learns a way of standing that no chair
allows. The same holds for a table, where the whole point is the volume underneath.

So the catalogue is right for support and wrong for clearance. Boxes stay for step, ledge,
bench top and floor, which really are solid, and anything with a void under it needs the void.

Constructive solid geometry is the cheap way to get one. Godot's CSG runs on **Manifold**
since 4.4, so a union of a seat plate and four legs, or a seat with the underside subtracted,
is a watertight mesh rather than a pile of intersecting boxes, and watertight is what a
collision mesh has to be. `v-sekai-multiplayer-fabric/vsekai-godot-mcp` is MIT and drives an
editor over MCP with `create_node`, `call_method` and `call_singleton`, which is enough to
build the CSG tree and to call `GLTFDocument` on it. Headless works too, and needs no addon.

The licence position does not change, which is the point of doing it this way. A CSG tree is
a few numbers and a boolean op, so a prop built from one carries no more licence than the box
it replaces, and after this session's corpus sweeps that is the property worth protecting.

One conversion sits in the way. protomotions resolves a scene object path to `obj`, `stl` or
`ply`, so a glTF out of Godot needs one more step before `MeshSceneObject` will take it. The
crowd plane's own MJCF takes a mesh directly.

**What is still true is that a box is enough to start.** Three sitting clips failed for want
of any support at all, not for want of leg room, and a seat plate at the right height fixes
the first fault today. Leg clearance is the second fault, and it will show up as a body that
sits correctly and puts its feet through the chair.
