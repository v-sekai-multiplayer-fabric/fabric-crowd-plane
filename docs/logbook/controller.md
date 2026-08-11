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
