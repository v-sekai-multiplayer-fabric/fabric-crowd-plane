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

## Sizing against a machine nobody chose

Two samples are a range, not a bound. Extending the table above to a machine 20 percent
worse than the worse of the two, which nothing observed rules out:

| p90 of the body | crowd vCPU for 1000 | venue vCPU |
| --- | --- | --- |
| 31.4 us, the desk | 3 | 6 |
| 52.6 us, the good machine | 4 | 7 |
| 65.7 us, the bad machine | 5 | 8 |
| 80.0 us, unobserved | 6 | 9 |

The platform sells eight. A touchable thousand fits the good machine with a core spare,
fits the bad machine with none, and does not fit a machine slightly worse than one already
seen.

No constant makes that safe, because the quantity it would bound is not bounded. So the
constant goes, and admission triggers on a ratio instead: the work a tick took over the
tick period, both measured on the machine that is running. Admit while the rolling p99 of
that ratio stays under one. A tick longer than a tick is a missed frame, so the threshold
is one by definition rather than by choice, and a slow machine admits fewer people without
anybody deciding it should.

What it costs is the promise. A venue cannot advertise a size it will always hold. It can
advertise what it holds on the worst machine it will keep, and give back the rest as
headroom. That is weaker than a fixed capacity and it is the true one.

## A ten minute tick loop, which is where the microbenchmark stopped being true

`bench/fly/tick_loop.py`. Fly `performance-2x`, `sjc`, machine `2872616f530748`. 301 bodies,
one core, 36000 ticks at 60 Hz, a fixed schedule, and a count of every tick that overran.
301 is what the microbenchmark on the good machine said one core holds at p90.

| | us |
| --- | --- |
| budget for a tick | 16667 |
| work, p50 | 16525 |
| work, p90 | 17275 |
| work, p99 | 20723 |
| work, p99.9 | 24115 |
| work, max | 45505 |
| tick start lateness, p99 | 236931 |
| tick start lateness, max | 286227 |

**13150 ticks of 36000 missed. 36.5 percent.**

Two things in that table are worse than the arithmetic that preceded it.

The work itself is 18 percent above what the microbenchmark predicted: 55 microseconds for
each body against 46.4. A microbenchmark steps the same bodies in a tight loop with
everything hot. A tick loop sleeps between passes, and what it wakes up to is a colder
cache. The difference is not measurement error. It is the cost of being a loop.

And the lateness is the real result. A tick begins a quarter of a second after it was due,
at p99. Work never exceeded 45 milliseconds, so a tick that starts 237 milliseconds late was
not delayed by its own work. It was descheduled. This is a shared tenancy virtual machine
and the hypervisor takes the core away for intervals far longer than a frame.

So 99 percent load is not a tight fit. It is a broken one, and a p90 from fifteen samples
over a few seconds cannot see it. Every capacity figure derived from the microbenchmarks
above should be read as a ceiling that is never reached.

| physics share of the tick | people for one core, at 55 us a body |
| --- | --- |
| 100 percent | 303 |
| 75 percent | 227 |
| 50 percent | 151 |

The load ratio in `spec/CrowdBudget.lean` is what makes this safe without a constant. This
entry is why it is needed: the number that was wrong was not the body cost. It was the
belief that a measured body cost predicts a loop.

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

## A trained stance, and what makes a constant acceptable

The rule this project works under says not to add a tuning constant, because a constant is a
guess about a workload nobody has measured. The sharper form of it, and the one adopted here,
is that a constant is acceptable when it holds across every known case and carries margin for
the known unknowns. Then it is not a guess with a name. It is a measurement with a name.

That decides how a trained policy is judged. It is the largest constant a system can have,
so it is not admitted on principle and it is not refused on principle either. It is admitted
on coverage: does it hold a stance when the body starts off balance, when it is pushed, when
it is crowded, and when it stands on someone's foot. Those are the known cases. The known
unknown is a crowd denser than any measured, and the margin against it is that a body which
fails should fall over, which is a legal outcome rather than an explosion.

`bench/train_stance.py` trains a LINEAR policy with Augmented Random Search: one matrix from
64 observations to 26 torques, 1664 parameters.

The reason to start linear is not that a matrix can be read while a network cannot. Both are
just numbers, both store and diff the same way, and 1664 of them are no more interpretable
than 100000. An earlier draft of this entry claimed otherwise and was wrong.

The reason is that it is the smallest thing that might work. If it holds a stance, the task
was easy and nothing larger is needed. If it fails, that is evidence about the task rather
than about the training, and the next step is capacity. Starting with capacity teaches
neither.

First run, 300 iterations in 26 seconds: the return did not move, 130 at the start and 139 at
the end. A return of 130 is about 43 steps, so the body was falling inside a second and the
policy had learned nothing. Training is cheap enough that the answer is more of it.

## Reinforcement learning, and a target that is not balance

ARS with a linear policy ran 2750 iterations and did not learn. The return started at 88 and
ended at 164, which is about 55 steps before falling, with no trend. That is the linear
policy doing the job it was picked for: it says the task needs capacity, not more search.

It also says the target was wrong. A balance controller keeps a body upright and does
nothing else. What a social world needs is what a console game has: a character controller
that takes a stick, walks, turns, and runs, and that stays physical while it does so. VRChat
moves an avatar kinematically along a capsule and the physics is decoration. A physically
simulated character controller is the thing that cannot be faked, and standing still is the
degenerate case of it rather than the goal.

NVIDIA's ProtoMotions 3 is that, and it is Apache-2.0. `examples/experiments/steering` is
literally the task: walk in a target direction at a target speed, with Adversarial Motion
Priors keeping the gait natural, and the target changing periodically. Its sibling
`path_follower` follows a path. Both are commands, not playback.

The ecosystem around it matters as much. SOMA is a standard skeleton that unifies parametric
body models, and there are pretrained motion trackers for a SOMA 23-body humanoid with 66
actions, trained with PPO on the BONES-SEED corpus. A motion tracker is the other half of
the product: a body that follows a reference pose physically, so being pushed is a deviation
the policy recovers from rather than an animation that ignores it.

Apparatus. The machine that ran every earlier measurement has an RTX 4090 in it, which went
unused for the whole session. ProtoMotions installs with `torch` on cu124 and its MuJoCo
extra, except `openmesh==1.2.1` which does not build here and is not needed to train.
Training needs a GPU-parallel backend: the MuJoCo backend asserts `num_envs == 1` and is for
inference only. Newton 1.0.0 with Warp 1.16.0 installs cleanly and is what the training below
uses.

## Running the pretrained tracker, which diverges

`~/.config/systemd/user/weft-tracker.service`. The SOMA BONES-SEED FSQ motion tracker,
69 MB of PPO weights for a 23-body humanoid with 66 actions, run against its own
`soma23_bones_seed_mini` motion set in the MuJoCo backend.

It loads 61 motions and steps. It never acts, and then it explodes:

    WARNING:absl: Nan, Inf or huge value in QACC at DOF 0. Time = 0.0030
    [Step    1] root_vel=[0.00, 0.25, 2.20]      max_dof_vel=      9.653  max_ctrl=0.0
    [Step  601] root_vel=[0.00, 0.25, 2.20]      max_dof_vel=      9.653  max_ctrl=0.0
    [Step 2901] root_vel=[956.35, 539.38, 376.77] max_dof_vel= 200126.487  max_ctrl=0.0

`max_ctrl` is 0.0 at every step, so the policy emits no torque at any point. Steps 1 and 601
are byte-identical, which reads like a frozen state, and by step 2901 the root is travelling
at 956 metres a second. So it is not merely inert: with no control at all the free bodies
integrate into nonsense, and the NaN in QACC on the very first step was the warning.

The model card says the weights were trained in IsaacLab. Nothing claims they transfer to
MuJoCo, and they do not. A pretrained checkpoint is only pretrained for the simulator it was
trained in, which is the finding: the fast path of taking NVIDIA's weights off the shelf is
closed unless the simulator matches.

### Four things that had to be fixed before it would even run

Worth recording because none of them are about humanoids.

A system unit runs as `init_t`, and SELinux under Enforcing refuses to let `init_t` exec an
interpreter labelled `user_home_t` or `user_tmp_t`. `SELinuxContext=` in the unit did not
help. A USER unit runs in the user's own unconfined context and works, so the job is
`systemctl --user`, followed with `journalctl --user -u weft-tracker -f`.

The install was under `/tmp`, which on this host is tmpfs, so 16 GB of it were sitting in
RAM. Moving it to a real filesystem fixed the label problem and gave back the memory.

An editable install remembers its path, so moving the tree broke the import until
`uv pip install -e .` was rerun.

`MUJOCO_GL=osmesa` fails here because PyOpenGL cannot load a GL library. `egl` works, and the
machine has a 4090 to back it.

### Apparatus, corrected

The machine that ran every measurement in this logbook has an RTX 4090 in it. Everything
above was measured on the CPU because nobody checked. The desk figures stand as CPU figures
and the comparison against Fly is still like for like, but any future training belongs on the
GPU.

## Motion data

`Datasets` on the house share carries what the training needs.

`Mixamo_Full_Animation_Packs/BVH_T-Pose.rar`, 104 MB, extracts to **2457 BVH clips** with a
Hips root and a standard humanoid hierarchy. This is a retarget away from a SOMA MotionLib.
`7z` cannot read RAR; `unar` can.

`addb-all`, 67 GB, is AddBiomechanics as train and test splits under `With_Arm`, by study:
Han2023, Carter2023, vanderZee2022 and others. This is the same corpus the sinew calibrator
set was sampled from, except these are sequences rather than sampled poses, so it is also
what the temporal compression question needed and could not get earlier. Copying it over SMB
runs at about 6.6 MB a second, so it takes about three hours.

### The fork this leaves

Two ways to a controller, and they differ in kind rather than in effort.

Retrain in Newton on the 4090, using the Mixamo clips as the motion prior for
`examples/experiments/steering`. Hours of training on hardware that is already here, and the
result is ours and matches our simulator.

Or install IsaacLab and use NVIDIA's checkpoints as they are. A large install, but their
weights work immediately and their skeleton, SOMA-23, is one we would likely adopt anyway.

The second is faster to a demo and the first is faster to a product, because a policy trained
in a simulator we do not run is a policy we cannot change.

## HYPOTHESIS: how long sim-to-sim transfer takes

Recorded before doing it, so it can be wrong in public.

The product trains on a GPU and deploys on a CPU. Training needs thousands of parallel
environments, which is IsaacLab or Newton. Deployment is one Fly `performance-2x` with no
GPU, which is MuJoCo. So a policy has to cross simulators, and the question is what that
costs.

The answer depends entirely on which simulator it trains in, and the two candidates are not
the same kind of gap.

**Newton to MuJoCo is not really a transfer.** Newton exposes `SolverMuJoCo`, and the crash
that blocked training came from `mujoco_warp/_src/solver.py`. Newton is MuJoCo's own solver
compiled through Warp onto the GPU. Same contact model, same constraint solver, same MJCF.
What differs is float precision, solver iteration count, timestep, and how many contacts the
GPU path keeps. All four are numbers we set on both sides.

**IsaacLab to MuJoCo is a real transfer.** PhysX is a different engine with a different
contact model and a different actuator model. Nothing carries over except the intent.

### The predictions

| route | training runs to a working policy | elapsed | confidence |
| --- | --- | --- | --- |
| Newton to MuJoCo | 1 to 2 | hours to two days | moderate |
| IsaacLab to MuJoCo | 5 to 10, with domain randomisation | one to four weeks | low |

One training run for a single steering task on one skeleton and flat terrain is estimated at
one to four hours on the 4090. That figure is a guess from ProtoMotions' own claim of 12
hours on four A100s for the entire 40-hour AMASS corpus, which is a far larger job, so the
error bar on it is wide.

### What would falsify each

Newton to MuJoCo is wrong if a policy trained in Newton and run in MuJoCo falls over
immediately, or if matching the two configurations turns out to need more than the four
numbers above. That would mean the GPU solver diverges from the CPU one in a way the
configuration cannot express, which would be worth knowing on its own.

IsaacLab to MuJoCo is wrong in the optimistic direction if NVIDIA already trained with
enough domain randomisation that their checkpoints transfer untouched. The one attempt so
far failed, but it failed with `max_ctrl` exactly 0.0 at every step, which is more consistent
with actions never reaching `data.ctrl` than with a policy behaving badly. That attempt does
not settle the question and should not be cited as if it did.

### The decision this drives

Train in Newton, deploy in MuJoCo, because same-engine transfer is the cheap one and because
a policy trained in a simulator we do not run is a policy we cannot change. The cost of being
wrong is bounded: if Newton to MuJoCo does not transfer, the fallback is domain randomisation
in Newton, which is the same work as the IsaacLab route without the second engine.
