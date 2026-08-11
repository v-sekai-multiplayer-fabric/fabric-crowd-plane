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
