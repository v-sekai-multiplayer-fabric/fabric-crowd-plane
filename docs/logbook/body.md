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

## The timestep the whole budget used is unstable for a crowd

The demo teleported. Bodies jumped, popped out of each other, and eventually the run went
NaN. Measured, 40 bodies pushed for 20 simulated seconds, substeps chosen to keep the frame
at 60 Hz:

| timestep | substeps | deepest penetration | max qvel | teleporting frames | us/frame |
| --- | --- | --- | --- | --- | --- |
| **16.7 ms** | 1 | **-1133 mm** | **18729404** | **118 of 1200** | 2340 |
| **8.3 ms** | 2 | **-46 mm** | 23 | **0** | **5490** |
| 4.2 ms | 4 | -40 mm | 33 | 0 | 9405 |
| 2.1 ms | 8 | -53 mm | 99 | 468 | 18793 |

At 16.7 ms the solver loses **a metre** of penetration, ejects bodies at velocities near ten
million, and dies. Halving the step fixes all three at once.

### The error, and it is mine

An earlier entry measured the timestep on **one** body, found 8 ms stable under a driven
muscle load, and reported it as the lever that made the budget work. It then became 16.7 ms
here, one step for each frame, and every capacity figure in this logbook was computed on it.

One body is not a crowd. A single body in contact with a floor has a handful of constraints
and forgives a long step. Forty bodies pressing on each other share one coupled solve, and
what a long step does there is fail to resolve penetration, then correct it violently the
next step. That correction is the teleporting.

The general form is worth keeping: **a stability result measured on one of a thing does not
transfer to many of them in contact.** The same mistake appeared earlier with solver
iterations, where iterations looked free on a barely-touching musculoskeletal body and turned
out to matter for a crowd.

### What it costs

5490 microseconds for 40 bodies is **137 microseconds for a body for a frame**, against the 55
this logbook has been using.

| | people for one core, physics at half the tick | always-on for 15 dollars |
| --- | --- | --- |
| 16.7 ms, unstable, as budgeted | 151 | 80 |
| **8.3 ms, stable** | **60** | **57** |

Capacity falls by 60 percent. The 15 dollar figure falls less, from 80 to 57, because egress
is most of that bill and the wire did not change.

The model default is now 8.3 ms with two substeps.

## The crowd was never unstable at 16.7 ms

The teleporting had nothing to do with the timestep. Halving the step and running two
substeps was the wrong fix, it cost twice the compute, and it did not work.

The drive was the fault. `PUSH` applied a constant 1200 N for as long as a client held the
stick, with no speed it settles at. A constant force has no equilibrium: 1200 N on 70 kg is
17 m/s^2, held, so the body accelerates until the solver cannot follow. A held stick is not
an edge case. It is what a player does.

Both steps under a held stick, 40 bodies, one minute:

| drive | step | deepest | max qvel | top speed | teleports |
| --- | --- | ---: | ---: | ---: | ---: |
| constant 1200 N | 16.7 ms x1 | -32128 mm | 1.47e9 | 7539 m/s | 2815 |
| constant 1200 N | 8.3 ms x2 | -228 mm | 2.86e6 | 3765 m/s | 3048 |
| velocity-targeted | 16.7 ms x1 | -61 mm | 18.1 | 2.7 m/s | 0 |

The second row is the point. The substep version diverges too. It reaches 3765 m/s instead
of 7539, so a twelve second clip looks acceptable and a minute does not. A smaller step buys
time against an unbounded drive, it does not bound it.

The drive now targets a speed and stops pushing once the body has it, with PUSH as the
ceiling on the force it may use to get there. One step of 16.7 ms for one frame of 16.7 ms.

Two other faults fell out of the same reading. Both planes stepped a 16.7 ms model twice a
frame, so the world ran at twice real time, not half: `Room.__init__` overrode the XML with
`opt.timestep = TICK` and the native plane declared 16.666 in its own XML. And the earlier
armature sweep was measured with `d.ctrl` never assigned, so the 26 actuators produced no
torque and the derivation from actuator saturation described a term that was not running.

### A pose servo is not a balance controller

Driving the 26 motors as a PD servo holding the rest pose was tried, because a motor is the
honest way to move a body and a force on the pelvis is not. It does not stand. The crowd
collapses and is then ejected upward, which reads as standing if height is sampled once at
the end: mean height ran 0.96, 0.39, 0.34, 0.27, and then 0.99 at fifteen seconds while the
velocities stayed near 43. A PD hold has no term for where the centre of mass sits over the
feet, so there is nothing in it that balances. The motors wait on the trained controller.

## Jolt, measured against MuJoCo

Same 14 links, same radii, same box feet, same density, same 0.9 m grid, and the mass agrees
to the gram: 69.99 kg in both. One core, one collision step, 16.7 ms, worst frame in microseconds.

| bodies | MuJoCo | Jolt |
| ---: | ---: | ---: |
| 40 | 2781 | 1937 |
| 60 | 4143 | 3090 |
| 80 | 5794 | 3602 |
| 100 | 5608 | 4886 |
| 120 | 9083 | 6809 |
| 200 | - | 10416 |
| 300 | - | 17341 |

Jolt is faster by about a third to a half on the worst frame, not by the order of magnitude
the first run suggested. That first run measured a benchmark whose push never stopped, so it
was timing an explosion. The MuJoCo row at 100 coming in under the row at 80 is measurement
noise and a reminder that these are worst-frame numbers from a single fifteen second run.

## Jump was the same fault as walk, and outlived the fix

`JUMP` put 6000 N on the pelvis for every frame the key was down. The pelvis alone is
12.23 kg, so that is 490 m/s^2, and holding the key held the force. Traced frame by frame it
does not jump: it passes 5 m and is still climbing at 6.8 m/s. This is the constant-force
fault the walk drive had, left behind because the walk was fixed by hand and the jump beside
it was not read.

A jump is an impulse with a height. `JUMP_HEIGHT` is 0.5 m, a standing human jump, and the
takeoff speed that reaches it is sqrt(2*g*h) = 3.13 m/s. It is applied once, on the press,
and only when some part of the body touches something that is not itself. Holding the key
for ten seconds now leaves the pelvis 78 mm above rest with no vertical speed.

The height that comes out is 0.36 m and not the 0.50 m asked for. Takeoff loses 18 per cent
of the speed to the ground contact it is pushing against, and the rise from what survives is
2.555^2/2g = 0.333 m, which is what the trace shows. That is honest for a velocity injected
at the root rather than a push from the legs, and it moves when the controller lands.

The bodies are lying down while this happens. Resting pelvis height is 0.110 m, because
nothing holds them up. A jump from a heap is still a jump, but it is not the picture.

## The body was not a person, and somebody had already fixed that

The body in `assets/tracked_avatar.xml` was written by hand from round numbers. Measured
against real anatomy it is wrong in four ways at once, and the last two explain behaviour
that had been blamed on the solver.

**Segment lengths.** Against Anny's SOMA rest pose the legs are 8 to 9 per cent short and the
arms 3 to 4 per cent short. Thigh 0.400 against 0.433, shin 0.390 against 0.424.

**Segment masses.** MS-Human-700 gives a distribution: trunk 26.2 per cent, pelvis 13.9,
thigh 10.4 each, shin 4.8, upper arm 3.2, forearm 1.85, hand 0.65. A first pass grouping by
name reached only 73 per cent of body mass, because the trunk is 50 separate bodies whose
names match no obvious pattern. Taking the trunk as the remainder is the only way to be sure
nothing is dropped.

**Joint ranges are wider than a person's.** Ankle 1.3 times, shoulder 1.3, elbow 1.2, and hip
flexion has its sign convention inverted: the model allows -109 to 34 degrees where the
anatomy is -30 to 115. Only the knee agrees, at 0 to 138.

**Every joint carries the same 300 N m.** Against measured human maxima the neck is 10 times
too strong, the elbow 5.5, the shoulder 3.8, the ankle 2.1, and the hip and knee 1.4.

The last two together describe a body with superhuman arms that can also reach poses a person
cannot. A controller on that frame will find a strategy that works and is not balance, which
is what the PD servo did: it collapsed the crowd and then ejected it upward.

### The prior art was already installed

None of this is new. `protomotions/robot_configs/soma23.py` carries the same body under
`BUILT_IN_PD` and splits it three ways:

| group | effort limit |
| --- | ---: |
| Spine, Chest, Neck, Head | 300 |
| Shoulder, Arm, Hand | **150** |
| Leg, Shin, Foot, ToeBase | 300 |

Arms at half of legs and trunk. Our flat 300 gives arms exactly twice what NVIDIA ships for
the same skeleton. The direction argued from muscle anatomy and from the literature is the
direction their config already takes, and theirs has trained working policies, which is
better evidence than either.

Their numbers and the literature disagree on how far to go. The literature puts the elbow at
55 N m and the shoulder at 80, which is a ratio nearer four to one than two to one, and it
puts the neck at 30 against their 300. Two to one is what is known to train, so that is the
floor of the correction and not the whole of it.

`bench/real_body.py` holds every number with the source it came from. Nothing in it is a
tuning constant: each value is a measurement or a ratio of two measurements.

### What MS-Human-700 is not for

It is not the body. 700 muscles at a 2 ms timestep is 4182 microseconds a frame for ONE
body, so about 4 to a core against roughly 200 for capsules. The Locomotion variant, at 100
muscles and 36 degrees of freedom, is 966 microseconds and about 17 to a core, still twelve
times worse. It is a reference for masses, ranges, and the relative pattern of strength.

Its muscle sum is also not a torque limit. Summing every muscle at peak isometric force over
its moment arm counts antagonists that in reality oppose each other, and lands 1.5 to 4 times
above measured human maxima: hip 755 against about 210, ankle 583 against about 140. A first
pass also reported a knee ceiling of 20936, which came from summing the model's knee slide
degrees of freedom, whose moment arms are newtons and not newton metres. Thirteen of its 85
degrees of freedom are translations and must be excluded.
