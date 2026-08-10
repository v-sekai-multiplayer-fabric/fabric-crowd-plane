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

## RESULT: the 15 to 20 minute prediction held

Training started at 12:09 and the last checkpoint was written at 12:28:43. **19.7 minutes**
for 500 iterations, against a prediction of 15 to 20 made at epoch 27.

The rate stayed flat at about 26 epochs a minute from epoch 27 to the end. The hypothesis
said a run that slowed down would be the good sign, because episodes lengthen once a policy
stops falling over immediately. It did not slow down, so the timing was easy to predict and
the policy probably did not learn much. Finishing on time is not the same as succeeding, and
the reward curve is the thing to read next.

Checkpoints are at `results/soma_steer/last.ckpt` (173 MB) and `score_based.ckpt`.

## HYPOTHESIS: 500 iterations in 15 to 20 minutes

Recorded while it runs, so the estimate cannot be revised after the fact.

Training started at 12:09 and reached epoch 27 by 12:10:04. Each epoch reports collecting in
about 1 second and optimising in under 1, so the observed rate is roughly 20 to 25 epochs a
minute for 2048 environments of SOMA-23 on the 4090.

At that rate 500 iterations finishes in **15 to 20 minutes**, and the run should be done
around **12:25 to 12:30**.

This replaces the estimate given before any iteration had run, which was one hour, and which
was a guess with no measurement under it. The correction is a factor of three or four, in the
optimistic direction.

### What would falsify it

The rate is measured over the first 27 epochs, which are the cheapest. Two things could slow
it down and neither is visible yet.

Episodes lengthen as the policy stops falling over immediately, so collection gets more
expensive as the policy improves. A run that ends at 40 minutes rather than 20 has probably
learned something, which makes overrunning this estimate a good sign rather than a bad one.

The log repeats `opt.ccd_iterations, currently set to 200, needs to be increased`, which is
continuous collision detection failing to converge. If that is raised to fix contact quality,
every step gets dearer and this estimate goes with it.

### What the run does not settle

Finishing is not succeeding. 500 iterations was chosen as enough to see whether the policy
learns at all, not as a budget known to produce a controller. If it walks badly at 500, the
answer is more iterations, and this timing estimate is then the unit of cost for that
decision rather than the answer to it.

## The policy is a tick cost, and nobody had costed it

The budget has four layers: publish, steer, contact, and the body. A learned controller adds
a fifth, and it is not small.

The actor in `examples/experiments/steering/mlp.py` is an MLP from the observation to 1024,
then 512, then 66 actions. Only the actor runs at deployment; the critic and the
discriminator are training only. MEASURED on one CPU core, fp32 through BLAS, 150 bodies with
a 400-wide observation, which is the shape a deployed plane would run:

| hidden | us/frame | us/body | share of a 16666 us tick |
| --- | --- | --- | --- |
| 1024 x 512 | 15747 | 104.98 | **94.5 percent** |
| 512 x 256 | 10201 | 68.01 | 61.2 |
| 256 x 128 | 6506 | 43.38 | 39.0 |
| 128 x 64 | 3962 | 26.42 | 23.8 |

At the shape ProtoMotions trains, **the policy costs more than the physics it steers**: 105
microseconds a body against 55 for the body itself. A plane running it would spend 94 percent
of its tick deciding what to do and have nothing left to do it in.

The arithmetic is not surprising once written down. 150 bodies through 1024 by 512 is 290
MFLOP a frame, which at 60 Hz is 17.4 GFLOP a second sustained, and that is most of one core.
A dense matmul on a CPU is already near the machine's limit, so this is not an
implementation problem to optimise away.

Two levers, and they multiply.

Narrow the network. 256 by 128 costs 39 percent of a tick instead of 94. Whether the task
needs 1024 by 512 is unmeasured: that width was chosen for full-body motion tracking over the
whole AMASS corpus, and steering on flat ground is a much smaller problem.

Run it slower than the physics. A controller does not need to think at the rate the body
integrates. Holding an action for two frames puts 256 by 128 at 20 percent of a tick, and for
three frames at 14 percent. 20 to 30 Hz control over 60 Hz physics is ordinary in robotics.

Together they take the fifth layer from 94 percent to about 14, which is affordable. Neither
is free: a narrow policy may not learn the task, and a slow policy reacts late to a shove,
which is the one thing this product sells.

### The deployment path

`protomotions/utils/export_utils.py` exports a policy to ONNX with `torch.onnx.export`, and
`onnxruntime` is already a dependency of the MuJoCo extra. There is also a pretrained model
named `g1-bones-deploy`, so the project intends deployment rather than only research.

So the plane loads an ONNX actor and runs it with onnxruntime on the CPU, alongside MuJoCo.
No PyTorch at runtime and no GPU. The measurements above are the budget that path has to fit.

### Open question: ONNX to Slang to CPU

The organisation has a Lean 4 to Slang pipeline that cross-compiles compute kernels to
Vulkan, Metal, and a CPU backend. Whether an ONNX actor can be routed through it is not
answered here, and the honest expectation is that it would not help on the target hardware.
The numbers above are dense fp32 matmul through BLAS, which is already close to what a CPU
can do, so a different code generator competes with a well-tuned GEMM rather than with
something naive. Slang earns its place if the plane ever runs on a GPU, or if the policy is
quantised to int8, where a hand-written kernel can beat a generic library. Both are
measurements nobody has taken.

## Quantising the policy: 4 bit is the wrong lever for this shape

A 1024 by 512 actor is 0.97 M parameters. That is 3.87 MB in fp32, 0.97 in int8, and 0.48 in
int4, against activations of 0.61 MB for 150 bodies. Every one of those fits in cache.

So this workload is not memory bound. Arithmetic intensity for a 150-row batch is about 75
FLOP for each byte of weight loaded, which is far above the point where a CPU stops waiting on
memory and starts waiting on its own arithmetic. Quantisation helps a memory bound problem by
moving fewer bytes, and helps a compute bound one only if the machine has instructions that
multiply the smaller type faster.

**No CPU has a 4 bit matmul instruction.** A 4 bit model is unpacked to int8 before anything
multiplies it, so int4 runs at int8 speed and merely stores smaller. Storage is not the
problem here.

int8 is a different matter, and it depends on the host. The desk machine is a Ryzen 3800X
with AVX2 and no VNNI, so int8 buys little there. A Zen 4 EPYC has AVX-512 with VNNI and
would give something like 4 times. The Fly host reports itself only as "AMD EPYC" with no
model, so whether the target has VNNI is **unknown and worth one command to find out**.

Ranked by what is certain:

| lever | factor | certainty |
| --- | --- | --- |
| narrow 1024x512 to 256x128 | 2.4x | measured |
| run control at 20 Hz over 60 Hz physics | 3x | measured |
| int8 with VNNI | maybe 4x | unverified, host unknown |
| int4 | about 1x for speed | argued above |

The first two multiply to about 7 times and take the policy from 94 percent of a tick to 14.
They are also the two that cost something real: a narrow policy may not learn the task, and a
policy thinking at 20 Hz reacts late to a shove, which is the one thing this product sells.
Quantisation costs accuracy instead, which is a different currency and a smaller bill.

## What the first run actually did, and four hypotheses about why

500 iterations finished on time and did not learn. The curves say so plainly.

| series | start | quarter | half | three quarters | end |
| --- | --- | --- | --- | --- | --- |
| `env/total_env_reward_mean` | 0.396 | 0.413 | 0.408 | 0.411 | 0.415 |
| `info/episode_reward` | 13.1 | 59.4 | 46.6 | 23.1 | 30.6 |
| `rewards/unnormalized_amp_rewards` | 0.594 | 0.104 | 0.159 | 0.172 | 0.133 |
| `discriminator/pos_acc` | 0.995 | 1.000 | 1.000 | 1.000 | 1.000 |
| `discriminator/agent_acc` | 0.994 | 0.939 | — | — | 0.947 |

The task reward is **flat**: 0.396 to 0.415 across 500 iterations, which is noise. Episode
reward rises to 59 and falls back to 30, so whatever it found it then lost.

The discriminator is the loud signal. It classifies expert motion perfectly and agent motion
at about 95 percent, and it does so from the first epochs. That is the classic adversarial
failure: once the discriminator separates the two distributions completely, the AMP reward
carries almost no gradient, and the unnormalised AMP reward falling from 0.594 to 0.133 is
that happening.

### H1: the reference motion is wrong for the task

`soma23_bones_seed_mini.pt` is a mini subset shipped to smoke-test the motion tracker. AMP
teaches a policy to move like its reference data, so if that subset is not locomotion, no
amount of training produces walking. **Prediction:** a locomotion-rich reference set moves
`unnormalized_amp_rewards` up rather than down, and `discriminator/pos_acc` off 1.000.
**Cost to test:** retargeting Mixamo's 2457 clips to SOMA-23, which is a pipeline, not a flag.

### H2: the discriminator is too strong

`pos_acc` pinned at 1.000 from the start means the policy never receives a usable gradient.
The standard remedies are a lower discriminator learning rate, a heavier gradient penalty, or
fewer discriminator updates per policy update. **Prediction:** weakening it moves `pos_acc`
into the 0.7 to 0.9 band and `unnormalized_amp_rewards` stops falling. **Cost to test:** one
override and a 20 minute run. This is the cheapest test and the evidence for it is the
strongest, so it goes first.

### H3: 500 iterations is far too few

500 was chosen as "enough to see whether it learns", with nothing behind it. AMP locomotion
in the literature runs to thousands. **Prediction:** if H2 and H1 are the real faults, more
iterations of the current setup changes nothing, and the flat task reward stays flat. **Cost
to test:** about 4 minutes for each 100 iterations, so 3000 is roughly 2 hours.

### H4: the task reward is being normalised into nothing

`reward_norm/var` sits between 197 and 249, so the raw task reward of about 0.41 is divided
down to 0.027. The AMP reward post-normalisation is 0.028, which is the same size. If the
normaliser is scaling a nearly constant task reward against a collapsing AMP reward, the
policy sees two small numbers and no clear direction. **Prediction:** the flat task reward is
the cause rather than the symptom, and it stays flat under H2 and H3 as well. **Cost to
test:** free, since it is read off the runs done for the others.

### The order

H2 first because it is one flag and 20 minutes. H3 second because it is only time. H1 last
because it is a retargeting pipeline, and because if H2 fixes the gradient then H1 becomes a
question about which motions rather than whether there are any.

## Hypotheses for making inference cheap enough to feel like a console

The target is not a percentage. It is that a shove reads as instant. A console character
controller answers the stick within one or two frames, so **16 to 33 milliseconds is the bar**,
and any saving bought with latency is spending the thing being sold.

That immediately demotes the cheapest lever measured so far. Running control at 20 Hz for
everybody is 3 times cheaper and puts 50 milliseconds between a shove and a reaction, which
is worse than a console and worse than what a player notices.

### I1: narrow the network

1024x512 to 256x128 is 2.4 times, MEASURED, and costs no latency at all. **Prediction:** a
steering policy on flat ground does not need the width chosen for tracking all of AMASS.
**Falsified if** the narrow policy will not learn the task, which is a training question and
not an inference one.

### I2: control-rate level of detail, near at 60 Hz and far at 20

The idea the rest of this design already uses, applied to thinking instead of to bytes. A
body you can reach must answer in one frame. A body across the room can think at 20 Hz and
nobody can tell, because you cannot push it.

| near at 60 Hz | far at 20 Hz | us/frame | share of tick | worst latency for anyone reachable |
| --- | --- | --- | --- | --- |
| 150 | 0 | 6506 | 39.0 percent | 16.7 ms |
| 30 | 120 | 3036 | 18.2 | 16.7 ms |
| 10 | 140 | 2458 | 14.7 | 16.7 ms |
| uniform 20 Hz | | 2169 | 13.0 | **50 ms for everyone** |

Ten near at full rate costs 14.7 percent against 13.0 for the uniform version. **Four tenths
of one percent of a tick buys back console latency for every body a player can touch.** That
is the whole argument. **Prediction:** interest radius already decides who is near, so this
needs no new mechanism. **Falsified if** switching a body between rates makes its motion jump,
which is a real risk and the reason to measure it rather than assume it.

### I3: int8 through VNNI

Maybe 4 times, and unverified because the Fly host reports only "AMD EPYC" with no model. Zen
4 has AVX-512 VNNI and Zen 3 does not. **Cost to test:** one command on a Fly machine to read
`/proc/cpuinfo`, which should have been done already. No latency cost. **Falsified if** the
target is Zen 3, in which case int8 buys almost nothing.

### I4: distil a wide policy into a narrow one

I1 costs capacity during training. Training wide and distilling into 256x128 for deployment
recovers it, because imitating a working policy is a much easier problem than discovering
one. **Prediction:** a distilled narrow policy beats a narrow policy trained from scratch.
**Cost to test:** a second training stage, cheap next to the first.

### I5: framework overhead

Every number above is numpy through BLAS, which is close to what a tuned C++ plane would
reach. onnxruntime adds a graph, and a graph has per-call overhead that matters when the call
is 43 microseconds. **Prediction:** onnxruntime lands within 20 percent of raw BLAS for this
shape, and if it does not, the plane should call a GEMM directly and skip the runtime.
**Cost to test:** one benchmark, not yet run.

### What is not on this list

Four-bit weights, for the reason in the entry above: the actor is cache-resident, so the
problem is arithmetic and not bytes, and no CPU multiplies four-bit numbers.

Running the policy on a separate machine. It costs 41.68 dollars a month against a 15 dollar
ceiling, it is the cross-machine per-tick path weft forbids, and it puts a network hop inside
a deadline that already loses 237 milliseconds to the hypervisor at p99.
