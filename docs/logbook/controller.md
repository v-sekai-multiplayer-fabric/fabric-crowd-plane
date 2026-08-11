# The controller

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

Oldest entry first. A new entry goes at the bottom.

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

## The inputs, and how few of them are trained

Two lists get conflated. What a player sends is not what the policy sees.

### What the steering task takes today

Read from `examples/experiments/steering/mlp.py`. The whole command is three things:

| field | shape | what it is |
| --- | --- | --- |
| `tar_dir` | 2 | which way to move, a unit vector on the ground |
| `tar_speed` | 1 | how fast |
| `tar_face_dir` | 2 | which way to face, separately from moving |

Direction and facing being separate is exactly a twin-stick controller: left stick moves,
right stick or the headset's yaw turns, and strafing falls out of the pair without anything
being added for it.

The policy's observation is larger and is not player input: full body state in maximal
coordinates, the same again as 8 steps of history, the root rotation, and the three fields
above. The history is what lets it infer contact and momentum without being told.

### What the product needs and does not have

| input | source | trained? |
| --- | --- | --- |
| move direction, 2 | left stick, or waist translation in roomscale | **yes** |
| move speed, 1 | stick magnitude | **yes** |
| face direction, 2 | headset yaw, or right stick | **yes** |
| jump | button | no |
| crouch | headset height, or button | no |
| head pose, 6DOF | HMD | no |
| hand poses, 2 x 6DOF | controllers | no |
| waist and feet, 3 x 6DOF | trackers, optional | no |

So the controller under training can walk where it is pointed and nothing else. Jump and
crouch are extra task components. The tracked upper body is a different problem again: those
are not commands to a locomotion policy, they are targets for a motion tracker, which is the
other pretrained model in this repository and the reason both halves exist.

### Upstream costs almost nothing, and it was never costed

Every wire measurement in `wire.md` is downstream. Upstream, at 60 Hz, 4 bytes a float:

| what the client sends | floats | kB/s |
| --- | --- | --- |
| steering command only | 5 | 1.2 |
| plus jump, crouch, sprint | 6 | 1.4 |
| plus 3-point tracking | 27 | 6.5 |
| plus 6-point | 48 | 16.6 |
| plus 11-point | 83 | 35.0 |

Downstream is 10.8 kB/s a client, so a fully tracked player sends about three times what
they receive. That inverts the usual assumption and it is still small: 35 kB/s times a
thousand players is 35 MB/s inbound, which is a fraction of what the venue already pushes
out. Ingress is not billed on the platform, so it costs machine time rather than money, and
the machine time is the edge decoding it, which remains the one unmeasured term in the
topology.

## Composing whatever the player is wearing

Every player brings a different rig. A headset alone is three degrees of freedom at the head.
Add controllers and it is three points. Add a waist and feet and it is six. Add elbows and
knees and it is eleven. Then face tracking and eye tracking arrive, and they are not joints
at all.

A policy trained on a fixed six-point rig cannot take three, and retraining one policy for
each combination is not a design. The requirement is composition: any subset, gracefully.

### The body: MaskedMimic already is this

`data/pretrained_models/masked_mimic/smpl` is a controller whose model card describes it as
producing "physically simulated motion while conditioning on **sparse or masked** future body
targets", for a 24-body SMPL humanoid with 69 actions, trained on AMASS. That is the
requirement stated as a method: mask out the targets a player does not have, and the policy
inpaints the rest physically.

It is the third controller in this repository and the right one for tracked players, where
the other two are for something else:

| controller | what drives it | who it is for |
| --- | --- | --- |
| steering | a direction and a speed | a player on a stick, and every unattended body |
| motion tracker | a full set of body targets | a fully tracked player |
| **masked mimic** | **any subset of targets** | **every real player, because rigs differ** |

The steering policy under training is still needed, because a body with no trackers at all
still has to walk. The two compose: steering supplies where to go, masked targets supply what
the tracked parts are doing.

### The face and the eyes are not physics

Blendshapes and gaze do not go through a controller. Nothing about a smile is dynamic, and
routing it through a policy would be inventing work. They are a separate channel: measured on
the client, published as data, applied on the other client. The physics never sees them.

That separation also makes them cheap. Blendshapes and gaze sit in a bounded range and 8 bits
covers them, and a face does not need 60 Hz.

| channel | params | rate | kB/s |
| --- | --- | --- | --- |
| ARKit-style blendshapes | 52 | 30 Hz | 1.56 |
| eye gaze, lid, pupil | 8 | 30 Hz | 0.24 |
| body, 11-point tracking | 77 | 60 Hz | 35.0 |

The whole face costs a twentieth of the body. It is worth stating because the intuition runs
the other way: faces feel expensive because they look expensive, and they are 1.8 kB a second.

### What this changes

The plane gains a second input path that bypasses the controller entirely, and the wire gains
a channel that is not joint rotations and does not compress like them. Neither is costed in
`wire.md`, which measures body pose only, and both should be before the topology is called
settled.

## max_ctrl is zero because the policy sends zero, not because the sim ignores it

`max_ctrl=0.0` had stood as the blocker for the tracker verdict. Reading the write path first:
the config is `built_in_pd` in every checkpoint, which reaches
`self.data.ctrl[self._dof_to_actuator] = targets` with no branch that can skip it, and the log
shows the map built as 66 DOFs to 66 actuators with kp from 200 to 800. Nothing there is
wrong, so the interesting question was whether the sim was stepping at all.

A probe of the bare MJCF in plain MuJoCo, with no protomotions in the process:

| ctrl | after 0.5 s | max joint movement |
| --- | --- | --- |
| 0.0 | root at −4.90 m, free fall, 2 contacts | — |
| 0.3 | root at −4.90 m | **0.2981 rad** |

**The actuators work.** A commanded 0.3 produces 0.298 of movement, so the MJCF, the actuator
transmissions and the gains are all sound.

The probe also corrected two readings of the eval log. The model's rest root is `[0, 0, 0]`,
so `root_pos=[0.00, 0.00, 0.00]` for twenty thousand steps is the **default pose untouched**
rather than a body held at the origin. And `ncon=27` against the probe's 2 is a body resting
on the heightfield with many contacts, not a body pinned. The intermediate reading, that the
harness was replaying kinematically, does not survive either number.

The MJCF timestep is 0.002, since 500 steps fell 4.90 m and that is one second of gravity.
The inference config reports `fps=1000`, which is 0.001.

### Where that leaves it

The write path works, so `targets` are zero, so `_common_actions` is zero. **The actions
leave the policy as zeros**, and every measurement taken downstream of that is a measurement
of an unactuated body falling over. `success_rate 0.000` from the three training runs says
nothing about the training, and it never did.

The next step is upstream of the simulator: whether the checkpoint's weights loaded, and
whether the agent's output reaches `step()` at all.

## The checkpoint is trained, and 0.0 was a print format

The actions leave the policy as zeros, so the next suspect was the checkpoint. It is not.

| | |
| --- | --- |
| epoch | 56800 |
| best evaluated score | **0.99960** |
| model tensors | 31, none of them entirely zero |
| action head `_actor.mu.mlp.12` | (66, 1024), so 66 outputs for 66 DOFs |

NVIDIA scored this tracker at 0.9996 on its own evaluation. The weights are trained, they are
intact, and the head is the right width for our skeleton.

Then the head's bias settles what `max_ctrl` was really showing. Its maximum is **0.0458**.
A network given degenerate observations returns approximately its final bias, so a policy that
sees nothing useful emits about 0.046 rad. The debug line formats as `max_ctrl={:.1f}`.

**0.046 prints as 0.0.**

So the control was probably never zero. It was one decimal place hiding a number far too small
to hold a body up, which looks exactly like no control and is not the same fault. This is the
second time in this project a formatted number has been read as a measurement, after the
constraint endpoints, and both times the fix was to look at what produced the digits.

That moves the suspect from the policy to what the policy is fed. A tracker that scores 0.9996
on correct observations and collapses on ours is an observation plumbing fault, and plumbing is
assembly rather than research.

## The control was never zero. It was railed at pi

Tracing a live eval, with the reset and the control path wrapped rather than the source
edited, overturned most of the previous entry.

    RESET called: root_pos=[168.9 145.2 1.036]   dof_pos max=2.485
    after reset:  qpos[0:3]=[168.9 145.2 1.036]  ncon=2
    ctrl step   0: |targets| max=2.33449  root_z=1.036
    ctrl step 200: |targets| max=3.14159  root_z=0.628
    ctrl step 400: |targets| max=3.14159  root_z=0.002

**Reset works.** The root is placed at 1.036 m on the terrain, which is the reference's own
height, and the reference is sound: 61 motions, 12629 frames, all finite, 30 fps, first-frame
root z averaging 0.911 m.

**The control works too, and that is the problem.** The targets are not zero. They sit at
3.14159, which is pi, on nearly every step, and the body falls from 1.036 m to 0.002 m.

### Why pi

`build_pd_action_offset_scale` derives a 3 DOF joint's action range as

    scale = min (2 * action_scale * max |limit|) pi

Measuring the MJCF: 66 hinge joints, every one limited, and the span of every one is exactly
360.0 degrees. So `max |limit|` is pi for all of them, the `min` selects pi, and the offset is
zero. A normalised action of 1.0 becomes a **180 degree target on every joint**.

So the policy is railing its output and the body is told to fold every joint to a half turn.

### What not to do about it

The obvious repair is to give the skeleton anatomical limits, and this project already has
them formalised in `lean-humanoid-rom`. **That repair is wrong here.** `git status` on the
MJCF is clean, so the file is upstream and unmodified, and the tracker that scores 0.9996 was
trained against exactly those limits. Its actions are calibrated to a pi scale. Narrowing the
range changes what an action means and invalidates the weights, and the MJCF has the testing
hours behind it.

The finding is recorded in `lean-humanoid-rom` instead, as a measurement with five decidable
facts, and range of motion is positioned there as a **validator over motion** rather than a
constraint a simulator holds. See that repository's pull request 3.

### Two corrections

The previous entry read `max_ctrl=0.0` as absent control and reasoned from it twice, once to
blame the observations and once to blame the checkpoint. Both were wrong. The value was a
`{:.1f}` print, the live trace shows pi, and the checkpoint and the reference are both sound.

Reference state initialisation also starts a body in the ground. One reset landed at
`root_pos=[88.2 69.8 0.147]` with 14 contacts, which is a body already lying down, because it
samples a random frame of a random motion and some frames are floor frames. That is unnatural
and it is unfair to a tracker, which is then asked to recover from a pose it did not choose.

## The tracker works. The reference observation explodes

Wrapping `BaseEnv.get_obs` and the control path together finally shows the chain end to end.

    obs dump 1   mimic_target_poses  max   1.029  mean 0.223
    act step 0   |target| max 0.9615  railed 0.00  root_z 1.042

    obs dump 2   mimic_target_poses  max 132.009  mean 18.017
    act step 150 |target| max 3.1416  railed 0.88  root_z 0.002

**On a sane observation the tracker emits a sane action and the body stands**, at 1.042 m with
nothing at the limit. That is the first evidence in this project that the controller works at
all, and it is the thing every previous measurement hid.

Then `mimic_target_poses` grows by about two orders of magnitude, from a mean of 0.22 to a mean
of 18.0 and a maximum of 132. From that step on, 88 to 97 per cent of the 66 joints sit at pi
and the root stays at 0.002 m for the rest of the run. **The railing is the consequence, not
the cause.** A network handed an input a hundred times outside its training range saturates,
which is the correct behaviour for a network and tells us nothing about its weights.

A factor near 100 in a project that has already had four unit faults is a suspicious number,
and metres against centimetres is the shape of it. That is the next thing to check.

`previous_actions` is all zero in every dump, which is a second thread and may be the same one.

### Do not trust the built in state print

The `[Step N]` line reports `root_pos=[0.00, 0.00, 0.00]` and `max_ctrl=0.0` at the same
moments a direct read of the same tensors gives pi targets and a moving root, and it sometimes
reports `max_dof_vel=200126`. A body frozen at the origin with 27 contacts, which occasionally
explodes, is not the body being controlled. **There is very likely a second simulator instance**,
and every number in the first three entries of this section came from it.

So the earlier readings were not misinterpreted. They were measurements of the wrong object.

## The body diverges first, and everything else follows

    frame   0   |obs| max      1.520      right after a reset
    frame  60   |obs| max    141.104      about a second later
    frame 360   |obs| max  29852.102

29852 is not a tracking error. It is a body blowing up, and it matches the `max_dof_vel` of
200126 seen in the same runs. So the order of events is settled, and it runs the opposite way
to the order they were found in:

1. Something diverges within about a second of a reset.
2. `mimic_target_poses` follows it, from a mean of 0.22 to a maximum of 141 and then 29852.
3. The policy sees an input a hundred times outside its training range and rails at pi.
4. A railed target against `kp=800` asks for a torque the effort limit clips at 300.
5. That drives more divergence, and the loop closes on itself.

The policy is the fourth step and not the first. It behaves correctly at step 4, which the
first sane frame proves: at an observation of 1.52 it emits 0.96 with nothing at a limit and
the body stands at 1.042 m.

## Placing a body in MuJoCo, and why the origin is the wrong handle

The rest origin of a model is not its standing pose. In `soma23_humanoid.xml` a `qpos` of all
zeros puts the root at z of 0, and the lowest body of the reference sits 0.03 m below its own
root. So a root written at z of 0 buries the feet, the solver answers with a large upward
impulse, and the result is a constant velocity against a position that does not move. That is
exactly the `root_vel` of 2.20 m/s beside a pinned root in the first traces.

The order that works:

1. Write the pose. Root position, root quaternion as wxyz, then the joint angles.
2. Write the velocity in the same breath. A position written over a stale `qvel` is what makes
   a placement look like an explosion.
3. Clear what the previous state left. `ctrl` and `qfrc_applied` both go to zero.
4. Run `mj_forward`, because nothing derived is valid until it has run.
5. **Only now measure the lowest body and lift the root by the ground clearance.** The lowest
   point is not knowable until the joints are posed, so this step cannot come earlier.

ProtoMotions holds both halves of step 5 already, in
`terrain.find_terrain_height_for_max_below_body` and in `ref_respawn_offset`.

And a body under physics is not placed twice. A `qpos` write in the middle of an episode
throws away momentum and contact state, so it reads as a jump however careful the write is.
Either it is a reset, which is the sequence above, or it is control, and control moves a body
with actuators toward a target instead of assigning it.

## mjWARN_BADQACC. The physics diverges before the policy acts

Tracing every state write with its caller settled it. There is one write per episode, from
`simple_test_policy` through `env.reset` and `reset_envs`, and it is correct:

    SET_STATE #0 -> root=[40.6 62.4 1.04]
    STEP 0  root=[40.6 62.4 1.04] |qvel|=0.007 ncon=2
    STEP 1  root=[0.   0.   0.002] |qvel|=9.653 ncon=27

**Nothing writes state between those two steps.** A body cannot cross 74 m in 0.02 s, so
nothing moved it. MuJoCo did. Reading the warning counters gives the mechanism:

    STEP 0  |qacc|=2.72e+06  |tgt|=1.006  warnings=none
    STEP 1  |qacc|=9.65e+03  |tgt|=3.142  mjWARN_BADQACC: 1

At step 0 the acceleration is already **2.72 million**, while the action is **1.006**, which is
a sane action and is nowhere near pi. The body is placed correctly, at 1.034 m with two
contacts. So the divergence happens before the policy has any part in it.

MuJoCo detects the bad acceleration, raises `mjWARN_BADQACC`, and restores `qpos0`. `qpos0` is
the model default, which puts the root at the origin with the feet through the floor and 27
contacts. It diverges again, and it is restored again, every step. That is the bit-identical
`qvel` of 9.653 that no single simulator should have produced, and it is why the state looked
frozen while the observation kept moving.

Everything else follows from it. The body reads as being at the origin while the reference
plays at the terrain spawn, so `mimic_target_poses` carries the distance between them, which
was 164 for a spawn at [168.9, 145.2]. That is the factor of a hundred, and it was never a
unit fault. The policy then sees an input far outside its training range and rails at pi,
which is correct behaviour for a network.

### The order, corrected once more

1. The physics diverges on the first step, with a sane action.
2. MuJoCo restores `qpos0`, which is the origin, and the body is buried there.
3. The observation carries the distance from the origin to the spawn.
4. The policy rails, because that input is far outside anything it was trained on.
5. The body stays on the floor, and the episode reports failure.

Every measurement taken before this one was a measurement of step 2 or later.

### What it is not

It is not the checkpoint, which scores 0.9996 and has no zero tensor. It is not the reference,
which is 61 finite motions at 30 fps. It is not the reset, which places the body correctly. It
is not the action range, which is upstream NVIDIA and matches training. It is not a second
simulator, which does not exist. Each of those was suspected here in turn and each is cleared.

It is the MuJoCo model setup. The tracker was trained in IsaacLab, and this is the MuJoCo port
of that model diverging on its first step.

## Force limits are not the fault, and the fault is there before control

The MJCF sets `forcerange` on none of its 66 actuators, so nothing bounds the force MuJoCo
applies. protomotions carries an effort limit per actuator and prints it at startup, and in
implicit PD mode never imposes it. Applying it to the model at run time, from the limits
protomotions already holds:

    forcerange applied to 66 actuators, median limit 300
    step 0  root_z=1.045  |qacc|=2.609e+06  ncon=2   warn=none
    step 1  root_z=-0.180 |qacc|=1.736e+08  ncon=30  mjWARN_BADQACC

**No change.** The body still diverges on the first step and MuJoCo still restores `qpos0`.

The reason is in the first line and it is worth more than the experiment. `qacc` is 2.6 million
**at step 0**, at a correctly placed standing pose, with two contacts, and before any actuator
force is applied at all. A clamp on the actuators cannot help, because the actuators were never
the source.

The bare MJCF at the same pose gives 5900. So the model protomotions builds is about 440 times
worse than the file it is built from, before control enters.

### What is left

Five suspects are now eliminated with evidence: the checkpoint, the reference motion, the reset,
the passive joint springs, and the actuator force limits. The divergence exists in the state
protomotions hands to the first step, so what remains is what protomotions does to the model
between loading it and stepping it. It strips a `<sensor>` element, adds five projectile bodies
as free joints, and sets the timestep. The projectiles are the interesting one, because they are
bodies that the file did not have and the reference knows nothing about.
