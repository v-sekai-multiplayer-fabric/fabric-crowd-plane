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

Which also settles what has to be true for it to work. Crossing must carry the player's
durable state, so `Weft.Actor` needs to write to disk, which it does not yet. Until then a
crossing loses everything, and a demo that loses everything on a doorway is worse than no
doorway.
