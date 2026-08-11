# Which motion may train the controller

Where the training motion comes from, what may legally train a policy weft ships, and every
way a corpus turns out not to hold what its name says.

`controller.md` holds the learning. This holds what it learns from.

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

## Meta's body, and why one licence explains the whole field

Meta's HumEnv is the closest match to our target that exists. 24 rigid bodies with 23
actuated, a 69-dimensional PD action space against our 66, MuJoCo, and a body its own
README describes as "tuned for more realistic behaviors (friction, joint actuation, and
movement range)", which are the two things ours was measured wrong on. Meta Motivo on top of
it is a behavioural foundation model for zero-shot whole-body control, which is standing and
sitting without training them.

Both are CC BY-NC 4.0, and the reason is not a choice Meta made. The body is SMPL-derived,
the motions are AMASS, and the SMPL licence says in its own words that it

> prohibits the use of the Software to train methods/algorithms/neural networks/etc. for
> commercial use of any kind.

AMASS carries the identical sentence. Meta could not have granted otherwise, because Meta
does not own the body model. So the restriction is inherited, not negotiable, and no amount
of reading the repository differently changes it.

That single clause explains the shape of the whole field. HumanML3D is built from AMASS, so
every model trained on HumanML3D inherits it, and that is MDM, MoMask, MotionGPT, T2M-GPT,
MotionLCM, and StableMoFusion. Their MIT and Apache badges are on the code. The weights carry
Max Planck.

### SOMA exists to escape exactly this

`NVlabs/SOMA-X` is Apache-2.0, and its README makes the intent plain. It ships **SOMA-shape**,
a PCA body model of NVIDIA's own, described as offering SMPL-like functionality with 128
coefficients. SMPL support is an optional extra, `py-soma-x[smpl]`, and the SMPL files
themselves "require a separate license". Anny is a listed supported model, which is why Anny
carries a SOMA rig at all.

So the clean stack was not assembled by taste. It is the only one that closes:

| piece | source | terms |
| --- | --- | --- |
| body shape | Anny, NAVER | Apache-2.0 |
| skeleton | SOMA-X, NVIDIA | Apache-2.0 |
| robot config | protomotions `soma23` | Apache-2.0 |
| generated motion | Kimodo-SOMA | NVIDIA Open Model |
| locomotion clips | O3DE | Apache-2.0 or MIT |
| gait with forces | AddBiomechanics | per-study |

Checked on this machine: `py-soma-x` is installed without the `smpl` extra, no chumpy, and no
SMPL model file anywhere on disk. Three SMPL-derived checkpoints do sit inside protomotions
and must not be used: `masked_mimic/smpl`, `motion_tracker/smpl`, `motion_tracker/smpl-terrains`.
The `soma-bones` variants beside them are clean.

`bench/corpus.py` now blocks `smpl`, `amass`, and `humenv` by name, each with the reason
attached, and `test_corpus.py` asserts that the SOMA path is *not* caught by those rules. A
blocklist that also blocked the thing we depend on would be discovered late and by hand.

The test also refuses any undeclared directory in the corpus root. It fired immediately on
`kimodo-src`, `hf-cache`, and `text-encoders`, which were directories added without saying
where they came from. The Llama weights that condition generation are now recorded too,
because they reach the output as surely as a clip does.

## Searching for more sources like O3DE, and why there are almost none

O3DE was found by accident and looked like one of many. An exhaustive sweep of the motion
matching ecosystem says it is close to unique, and the reason is worth writing down because
the next search will look promising in exactly the same misleading way.

**The repository licence is not the corpus licence.** Every search sorted by licence returns
MIT and Apache repositories that ship somebody else's mocap:

| repository | code | the data inside |
| --- | --- | --- |
| `orangeduck/Motion-Matching`, 900 stars | MIT | LAFAN1, CC BY-NC-ND |
| `voxell-tech/bevy_motion_matching` | MIT and Apache | ships `assets/ubisoft_bvh`, so LAFAN1 |
| `JLPM22/MotionMatching`, 586 stars | MIT | not stated anywhere |
| `BandaiNamcoResearchInc/...Motiondataset` | MIT, for the Blender viewer only | CC BY-NC 4.0 |
| `ubisoft/ubisoft-laforge-animation-dataset` | MIT, for the code | CC BY-NC-ND 4.0 |

Daniel Holden states it plainly in his own README: the data "is licensed under Creative
Commons Attribution-NonCommercial-NoDerivatives 4.0 International Public License (unlike the
code, which is licensed under MIT)". NoDerivatives is stricter than the SMPL clause, because
a retarget is a derivative and so is a compiled database.

So the field rests on one corpus. LAFAN1 is to motion matching what AMASS is to motion
generation, and both are non-commercial.

O3DE is the exception because it is not a dataset at all. It is an engine, and its clips are
its own demo content, shipped under the engine's Apache-2.0 or MIT. **The pattern to search
for is an engine or an open movie that had to clear its own assets, not a dataset.**

### CMU is blocked

The CMU Graphics Lab database looked like the second exception. Its terms permit including
the data in a commercially sold product, which no other large corpus here allows. It also
says the data may not be resold directly, "even in converted form", and a shipped policy
carries its corpus in its weights. Whether that is the data in converted form is not a
question to answer optimistically, so it is blocked.

Two things about it are worth keeping even so. The same recordings carry different terms
depending on where they are fetched: raw from `mocap.cs.cmu.edu` under CMU's own licence, or
inside AMASS under Max Planck's. And the wording above came from secondary sources, because
the CMU page did not return anything parseable.

`bench/corpus.py` now blocks `cmu`, `lafan`, `ubisoft`, and `bandai` alongside the SMPL
family, each with its reason, and `test_corpus.py` asserts each is refused under the name it
actually arrives as. `assets/ubisoft_bvh` inside an MIT repository is the case that matters:
nothing about the path says LAFAN1, and nothing about the repository says non-commercial.
