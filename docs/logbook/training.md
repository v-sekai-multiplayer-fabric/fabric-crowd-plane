# Training runs

Each run that was launched, the hypothesis it was launched to test, and what came back.
A hypothesis that turned out wrong stays here with the reason, because the wrong ones are
what stopped the next run being launched the same way.

`controller.md` holds what the controller must do. This holds the attempts to train it.

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

## H2 under test: the discriminator was learning five times faster than the policy

Reading the resolved config rather than guessing found the number that makes H2 more than a
suspicion.

    actor_optimizer          lr 2e-5
    critic_optimizer         lr 1e-4
    discriminator_optimizer  lr 1e-4      <- five times the actor

An adversarial pair only teaches while neither side wins. The discriminator was given five
times the actor's learning rate and reached 100 percent accuracy on expert motion in the
first epochs, after which the policy had nothing to climb.

`weft-steer-h2.service`: discriminator learning rate to 1e-5, a tenth of what it was and half
the actor's, with the gradient penalty raised from 5.0 to 10.0. Everything else unchanged,
same 500 iterations, same motion set, so the comparison is clean.

Two false starts worth recording, because the next override will hit them too. The config
path is not what the experiment file suggests: it is `agent.model.discriminator_optimizer.lr`
and `agent.amp_parameters.discriminator_grad_penalty`, and the way to find a path is to read
the indentation of `results/<name>/resolved_configs.yaml` rather than the Python that built
it.

**What counts as a pass.** `discriminator/pos_acc` should come off 1.000 into the 0.7 to 0.9
band, and `rewards/unnormalized_amp_rewards` should stop falling. If both happen and
`env/total_env_reward_mean` is still flat at 0.41, then H2 was real and insufficient, and H1
becomes the next suspect rather than H3.

## RESULT: H2 works, and the criterion written for it was the wrong one

Same 500 iterations, same motion set, discriminator learning rate 1e-4 to 1e-5 and gradient
penalty 5.0 to 10.0. End-of-run values:

| series | baseline | H2 | |
| --- | --- | --- | --- |
| `info/episode_reward` | 30.6 | **128.9** | 4.2 times |
| `env/total_env_reward_mean` | 0.415 | **0.463** | first movement in this series at all |
| `rewards/unnormalized_amp_rewards` | 0.133 | 0.183 | stopped collapsing |
| `discriminator/agent_acc` | 0.947 | 0.892 | slightly less certain |
| `discriminator/pos_acc` | 1.000 | **0.999** | did not move |

The prediction was that `pos_acc` would fall into the 0.7 to 0.9 band, and it did not. By the
criterion written down in advance, H2 fails.

By outcome it plainly works. Episode reward went up 4.2 times and the task reward moved for
the first time across two runs. So the hypothesis was right and **the proxy chosen to test it
was wrong**: a discriminator can still classify expert motion perfectly while leaving the
policy a usable gradient, because what matters is the slope it presents, not the accuracy it
reaches. `unnormalized_amp_rewards` turning from falling to rising was the honest indicator
and it was in the table all along, one row down.

Worth keeping because the next hypothesis will need a criterion too, and the lesson is to pick
the one nearest the outcome rather than the one nearest the mechanism.

### What it does not settle

Episode reward was still climbing at the end, 106.6 at the midpoint and 128.9 at the finish,
so 500 iterations stopped the run rather than finished it. That makes H3 the next test, and it
is now a different question from the one first written: not "does more training rescue a dead
run", but "how far does a run that is already learning go".

## RESULT: H2 works, and the criterion written for it was the wrong one

Same 500 iterations, same motion set, discriminator learning rate 1e-4 to 1e-5 and gradient
penalty 5.0 to 10.0. End-of-run values:

| series | baseline | H2 | |
| --- | --- | --- | --- |
| `info/episode_reward` | 30.6 | **128.9** | 4.2 times |
| `env/total_env_reward_mean` | 0.415 | **0.463** | first movement in this series at all |
| `rewards/unnormalized_amp_rewards` | 0.133 | 0.183 | stopped collapsing |
| `discriminator/agent_acc` | 0.947 | 0.892 | slightly less certain |
| `discriminator/pos_acc` | 1.000 | **0.999** | did not move |

The prediction was that `pos_acc` would fall into the 0.7 to 0.9 band, and it did not. By the
criterion written down in advance, H2 fails.

By outcome it plainly works. Episode reward went up 4.2 times and the task reward moved for
the first time across two runs. So the hypothesis was right and **the proxy chosen to test it
was wrong**: a discriminator can still classify expert motion perfectly while leaving the
policy a usable gradient, because what matters is the slope it presents, not the accuracy it
reaches. `unnormalized_amp_rewards` turning from falling to rising was the honest indicator
and it was in the table all along, one row down.

Worth keeping because the next hypothesis will need a criterion too, and the lesson is to pick
the one nearest the outcome rather than the one nearest the mechanism.

### What it does not settle

Episode reward was still climbing at the end, 106.6 at the midpoint and 128.9 at the finish,
so 500 iterations stopped the run rather than finished it. That makes H3 the next test, and it
is now a different question from the one first written: not "does more training rescue a dead
run", but "how far does a run that is already learning go".

## Which motion may train the controller

Mixamo is blocked. Its terms cover using the animations inside a project, and a trained
policy carries the corpus in its weights and is redistributed, which is not the same thing.
`bench/corpus.py` holds the rule and `bench/test_corpus.py` fails if it is broken. Unknown
provenance is refused by default, because silence is not consent.

Two corpora were measured against what a gamepad controller needs.

**AddBiomechanics, 130 files, 68 GB.** 125 readable, 4380 trials, 7.7 hours at 250 Hz. Five
files are zero bytes and did not transfer. It is the wrong corpus for control, and the
reason is not size:

- Every trial is treadmill-pinned. The root travels 0.04 to 0.38 m during six seconds of
  running, so root velocity is near zero whatever the subject is doing. The speed a stick
  would command is the belt speed, and the belt speed is not recorded.
- There is no turning at all. A treadmill runs in a straight line.
- Standing is 0.8 per cent, about 3.5 minutes.

Recovering belt speed from the centre of pressure was tried and does not work. It returns
1.00 m/s for a trial named fast and 1.08 for one named slow, inverted and far too low,
because the centre of pressure tracks heel-to-toe roll-over under a planted foot rather than
the belt. Roughly a quarter of a metre per stance whatever the speed.

What AddBiomechanics does have is gait with measured ground reaction forces, which is rare.
That is a later corpus for a different question.

**O3DE motion matching, 22 clips, 28 minutes.** Apache-2.0 or MIT at the reader's option,
confirmed from the repository's own `LICENSE.txt`. It arrives through
`godot-motion-matching-demo`, which credits it.

- Root motion is real. Extents run 6.8 to 26 m.
- `TurnOnSpot1` has an extent of 0.97 m against about 10 m for everything else. The corpus
  states what it contains and then measures out as containing it.
- The clips are the command vocabulary: a speed ladder, seven turning clips, starts and
  stops, and one clip each for jump, crouch, and push, which are the three commands the
  plane already takes.

At 30 Hz this is about 50000 frames, four times the mini set the three local runs used.

The skeleton is Godot's `GeneralSkeleton`, so 22 of the 23 SOMA bodies map by name or by an
obvious rename. Only `Neck2` has no source, because VRM carries one neck bone where SOMA
carries two. Anny supplies the SOMA rest pose that the split needs.

## Generating the missing behaviours, and six ways it lies quietly

Neither corpus holds standing, sitting, getting off the floor, or being jostled. Kimodo, an
NVIDIA kinematic motion diffusion model, generates them and emits `somaskel77` directly, which
is the target skeleton, so these clips need no retarget at all. It also ships foot contacts,
which the O3DE clips do not have.

Six things in this path produce a file that loads, passes every numeric check, and is wrong.
They are written down because none of them announces itself.

**1. A prompt separated by commas is one segment.** Kimodo splits a prompt on full stops and
gives each piece its own span. `walks to a chair, sits down, waits, then stands up` is a single
twelve second segment, and the model follows the first clause and abandons the rest. The clip
sat down, fell to the floor, and stayed there for the last four seconds. Written as four
sentences with `--duration "3 3 3 3"` the same request produces walk, sit, stand, walk away.

**2. A number cannot tell whether the motion is the motion that was asked for.** The bad clip
passed everything: 1.80 m tall, 1.70 m travelled, root error zero, units correct, no NaN. Two
of the first four clips were wrong and every check was green on both. Drawing eight frames to a
contact sheet and looking at it took seconds and showed both failures at once. A second clip
prompted for a shove stood almost still for eight seconds. `render_motion.py` exists for this.

**3. `somaskel77` is a ROOT node plus 77 joints.** The shipped T-pose BVH holds 78. The model
emits the 77, so the ROOT is dropped and the rest reparented.

**4. The skeleton is centimetres and the motion is metres, in the same model.** The BVH offsets
put the hips 100 units up; the generated motion puts them at 1.002. One is divided and the
other is not. Anny's SOMA rig is centimetres too, and read as metres it describes a skeleton
154 m tall.

**5. USD holds a translation in the last row, numpy in the last column.** A matrix handed
across without a transpose writes a file that opens and animates and is wrong. Both converters
read their own output back and compare against the source.

**6. `Gf` constructors take Python floats.** A numpy scalar matches no overload and raises from
inside Boost.Python with a message naming only C++ signatures.

USD is the intermediate rather than BVH or FBX. BVH states neither unit nor axis, so every
reader guesses, which is how faults 3 and 4 stay hidden. FBX needs a vendor SDK. A `UsdSkel`
file carries `metersPerUnit`, the up axis, the rest pose, and the animation in one readable
place, and foot contacts ride along as `weft:footContacts`.

### The text encoder is gated, and the way around it has a trap

Kimodo encodes text with LLM2Vec over Llama-3-8B-Instruct, which Meta gates by hand. The
weights are mirrored ungated at `NousResearch/Meta-Llama-3-8B-Instruct` and the LLM2Vec
adapters are open, so the encoder is assembled from both.

`prepare_for_tokenization` applies the Llama-3 chat template only when `config._name_or_path`
is exactly `meta-llama/Meta-Llama-3-8B-Instruct`. So McGill's config is kept verbatim and only
the weight files come from the mirror. Renaming it to the mirror still runs, and silently
changes every embedding the model is conditioned on.

### What is generated is kinematic

These clips are poses, not forces. Nothing here actuates anything. A motion tracker is what
turns a kinematic reference into a policy driving the 66 SOMA degrees of freedom as PD
targets, which the SOMA model card calls the PD-control contract. The corpus is the reference
for that training and is not itself a controller.

## RESULT: H3 finished, and six times the training bought fifteen percent

3000 iterations with H2's settings, against H2's 500.

| series | baseline | H2, 500 iters | H3, 3000 iters |
| --- | --- | --- | --- |
| `env/total_env_reward_mean` | 0.42 | 0.46 | **0.53** |
| `info/episode_reward` | 30.6 | **128.9** | 107.9 |
| `rewards/unnormalized_amp_rewards` | 0.13 | 0.18 | **0.10** |
| `discriminator/pos_acc` | 1.00 | 1.00 | 1.00 |

Six times the training moved the task reward 15 percent and made the episode reward **worse**
than the 500-iteration run. The AMP reward, which H2 had rescued from collapse, collapsed
again over the longer run: 0.18 down to 0.10.

The hypothesis asked "how far does a run that is already learning go". The answer is: not far,
and then backwards. Weakening the discriminator bought a window in which the policy could
learn, and 3000 iterations was long enough for the discriminator to win again anyway.

### Which promotes H1

Three runs now, and the AMP reward falls in all of them. H2 delayed it. H3 shows the delay is
temporary. That is what a policy looks like when it cannot imitate its reference data, and the
reference data is `soma23_bones_seed_mini`, a subset shipped to smoke-test a motion tracker.

**H1 is now the live hypothesis rather than the last one.** Kimodo generates locomotion from
text in the SOMA skeleton with a converter already written, so testing it costs a motion set
rather than a retargeting pipeline.

### What this does not say

It does not say the policy is useless. Nothing here has run it. The curves say it learned
something and stopped, and reading a curve is not the same as watching a body walk. Running
the checkpoint is a separate job and it belongs before any further training, because it is the
only measurement that answers what the training was for.