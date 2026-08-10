# Inference, and the cost of thinking

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

A learned controller is a fifth layer in the tick budget, alongside publish, steer, contact,
and the body. This book is what it costs and how to make it cheaper.

Oldest entry first. A new entry goes at the bottom.

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
