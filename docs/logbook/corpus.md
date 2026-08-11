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

## How much is missing, and who it is of

A target of "enough data" is a guess unless something fixes the scale. The O3DE corpus fixes
it: it covers walking and turning well enough that a motion matching demo works on it, and
covers everything else badly. Its **weakest well-covered** behaviour is turning, seven clips
totalling 450 s. That is a measured floor for what one behaviour costs.

| behaviour | have | missing to 450 s |
| --- | ---: | ---: |
| getting up | 10 s | 440 s |
| sitting | 12 s | 438 s |
| standing still | 71 s | 380 s |
| being pushed | 74 s | 376 s |
| strafing | 154 s | 297 s |
| | | **1932 s, 32 minutes** |

"Standing still" counts only 40 per cent of the measured idle frames, because `TurnOnSpot1`
is 60 per cent of them and it is turning in place, not standing.

Generating it is 193 clips of 10 s, about 8 minutes of diffusion on the 4090. Usable motion
goes from 0.48 h to 1.01 h. Acquisition was never the answer: every corpus searched for was
non-commercial, and the thing that was missing costs a quarter of an hour of compute.

### Thirty-two minutes of whom

A corpus generated at one default body is 32 minutes of one morphology. Gait is not scale
invariant. Step length and cadence follow leg length, and the torque a hip needs follows
mass, so a controller trained on one body learns balance tuned to those proportions. A venue
is not one body.

Anny carries conditional distributions over height, weight, muscle, and proportions, with a
morphological age mapping, so a body can be sampled from a stated population instead of
defaulted to. The axes that matter here are anthropometric rather than appearance: limb
length, mass distribution, age, and mobility.

Most of that variation belongs in training, as randomisation over the body, and costs no
extra motion. Gait does not, so the clips are **stratified and not multiplied**: five strata
sampled across the distribution at 386 s each, still 32 minutes. Multiplying instead would
cost 161 minutes and buy far less, because the same clip retargeted onto five bodies is one
gait wearing five sizes.

The population sampled from has to be written down with the corpus. A distribution nobody
states is a default nobody chose, and the default here is whatever body the generator emits.

## Two real get-up clips, and a file that lies about which way is up

Two CC-BY clips of getting up off the floor were downloaded by hand from Fab: Klian's
`anim_ue4_gettingup_up` and `_down`, 12.2 s together at 120 fps on the UE4 mannequin. Getting
up is the largest gap in the corpus, 10 s held against 450 s wanted, so this is real mocap of
exactly the missing behaviour and it is 3 per cent of the gap. It is a reference to check
generated get-ups against rather than a way to fill it.

They arrived as USDZ, which is the intermediate this repo already chose, and two of the three
traps that keeps producing showed up again inside them.

**Centimetres, stated.** `metersPerUnit` is 0.01. That is now the fourth source with a unit
that is not metres, after Anny, the somaskel77 BVH, and the two halves of Kimodo that
disagree with each other. USD states it, which is the whole argument for USD.

**The declared up axis is wrong.** The stage says `upAxis = Y` and the bind pose spans 162.7
cm in Z against 21.5 cm in Y. It is UE4 data and UE4 is Z-up, and the exporter wrote the axis
metadata without moving the data under it. Measured on Y the skeleton is 0.21 m tall.

The guard that catches this is the one already written for the Anny converter: refuse a
skeleton that is not between 0.5 and 2.5 m. It works here without modification, and it works
because it asks whether the result is a person rather than whether the metadata is
self-consistent. A file can be internally consistent and still be wrong.

**The joint names are gone.** The Skeleton names its 60 joints `n8` to `n67`. Three real names
survive in the Xform tree above it, `root_01`, `pelvis_02`, `spine_01_03`, and the rest have
to be recovered by matching the topology to the published UE4 mannequin hierarchy. That is
deterministic and it is work, and it is not done. Kimodo emits SOMA names already, which is
the cheaper 97 per cent of this gap.

## Foot contacts, derived and then checked against a model that knows

Motion matching uses foot contact as a matching feature and a physics tracker uses it to know
when a foot may carry load. Kimodo emits contacts. The O3DE clips, 100STYLE, and the Fab USDZ
do not, so the corpus disagrees about whether the information exists.

`bench/foot_contacts.py` derives them with NVIDIA's own heuristic from
`kimodo/motion_rep/feet.py`, Apache-2.0: a foot is in contact when it is low and slow. Their
call passes 0.15 and 0.10. Two bare numbers is what this repo does not keep, so both are
derived instead. The height threshold is the skeleton's own lowest foot position plus a tenth
of that skeleton's standing height, so a short body and a tall one get different thresholds.
The speed threshold is a quarter of the median joint speed in that clip, so a clip of standing
and a clip of sprinting are each judged on their own terms.

The derivation is not trusted, it is measured, because Kimodo's clips carry contacts the model
itself produced:

| clip | agreement | model | derived |
| --- | ---: | ---: | ---: |
| sit_stand2 | 99.6% | 0.71 | 0.70 |
| idle_stand | 89.3% | 1.00 | 0.89 |
| get_up | 73.6% | 0.72 | 0.51 |

It reproduces the model almost exactly for locomotion and standing, and falls to three
quarters on a floor transition, which is where the question is genuinely ambiguous: during a
get-up the hands and knees carry load and "is the foot in contact" stops being the right
question. The number to distrust is the one on the behaviour we have least of.

### Conditioning on contacts needs no retraining

`foot_contacts` is a channel of `KimodoMotionRep`, four values beside root position, joint
positions, rotations, and velocities. The denoiser takes `motion_mask` and `observed_motion`,
which mark which channels are known and supply them. Masking the four contact channels and
supplying a pattern is therefore contact conditioning, using machinery that already exists.

The documentation says contacts are "trained to support this, but not currently implemented
in the demo UI or Python API". That is true of the UI and the public API and not of the model,
which is a useful distinction to have found before writing a training loop to add a feature
that is already there.

## The retarget had a tool the whole time

This logbook has repeatedly called retargeting "deterministic and it is work", without naming
anything to do it with. `chungmin99/pyroki` is that tool: MIT, JAX, differentiable forward
kinematics from a URDF, a Levenberg-Marquardt solver on manifolds, joint limits as hard
constraints, and self-collision costs. It ships `10_humanoid_retargeting.py` and a fancier
variant, so humanoid retargeting is an example rather than something to invent.

Three of its properties matter here specifically.

**Joint limits are constraints, not suggestions.** The ranges measured out of MS-Human-700 in
`anatomy.md` become hard constraints in the solve, so a retarget cannot produce the poses the
old body could reach and a person cannot.

**Self-collision is a cost.** Retargeting a tall body's motion onto a short one naively puts
limbs through the torso. This is the thing that makes the Anny cross product real rather than
theoretical: one clip onto five sampled bodies is five IK solves, each respecting that body's
own limb lengths and its own limits.

**protomotions already reads its output.** `convert_pyroki_retargeted_robot_motions_to_proto.py`
imports `robot_config` and `extract_qpos_from_transforms`, so the path from a pyroki solve to
soma23 qpos exists and does not need writing.

SMPL appears in the repository only as a joint name list in `examples/retarget_helpers/_utils.py`
and never inside `src/pyroki`. A list of joint names is a naming scheme, which is the same
distinction that admits a mixamo-compatible rig while refusing mixamo data.

The one real cost is that the parser reads URDF and our body is MJCF, so the avatar needs
converting before it can be a retarget target.

## The gap generation, and where a prompt stops working

Ten prompts, ten samples each, a hundred clips, all segmented into four sentences with their
own durations because commas produce one segment and the model abandons everything after the
first clause. That fix held. A different limit showed up behind it.

Sitting works. Four of the five sitting clips span 1.76 to 1.85 m vertically, which is a body
that starts standing and ends down.

**Getting up mostly does not.**

| clip | vertical span | |
| --- | ---: | --- |
| getup_kneel | 1.80 m | stands |
| getup_back | 1.16 m | partial |
| getup_sit | 0.95 m | partial |
| getup_quick | 0.66 m | does not stand |
| getup_front | 0.43 m | never leaves the floor |

`getup_front` was prompted with four sentences: lies face down, pushes onto hands and knees,
brings one foot forward, stands up. Every one of the eight sampled frames is prone. Ten
seconds face down.

This is not the comma fault again. The prompts were correct this time, and the model still
would not do it. Floor-to-standing is rare in motion capture, so it is likely thin in Bones
Rigplay as well, and a text prompt cannot pull a diffusion model into a region of the
distribution it barely has.

The fix is the constraint mechanism rather than another prompt sweep. A full-body keyframe
pinning the pelvis at standing height in the final second states the requirement instead of
describing it, which is what constraints are for and what `KimodoLocoMoGen` used in place of
retraining. Not done yet.

**Sitting is closed. Getting up is half open.** The measured 878 s gap is therefore about half
shut, and the remaining half needs authored constraints.

## 100STYLE converts, once the ruler is right

1620 BVH files unpack to 3.2 GB across style directories named `WalkingStickLeft`, `Rocket`,
`Drunk`, `Aeroplane`. The first conversion pass refused **all forty** it tried:

    no unit makes this a person: 272.56 in file units

The data was fine. `pick_scale` summed every offset along each axis, which adds both legs to
the spine and both arms, and over-counts height by more than half. A 1.7 m skeleton measured
that way reads 2.7. Accumulating each offset down its own parent chain instead gives the real
height, and then all forty convert, unit chosen by measurement as centimetres, 56.7 minutes of
motion.

The guard was wrong and still did its job: it refused rather than writing 1620 files of 2.7 m
people that nobody would have questioned until training.
