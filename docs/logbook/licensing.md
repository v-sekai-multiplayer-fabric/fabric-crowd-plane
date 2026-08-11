# Licensing

What may legally train a policy weft ships, and every way a permissive badge turns out to
cover only the code. The rule lives in `bench/corpus.py` and `bench/test_corpus.py` fails if
it is broken.

`corpus.md` holds what the corpora contain. This holds whether they may be used.

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

## CC0, which is the category the search kept missing

Every source above was searched for as a dataset, and datasets in this field are almost all
non-commercial. The category that is not is game art: assets an artist made to be used, put
into the public domain outright.

**Quaternius Universal Animation Library** is CC0 1.0. Not a permissive licence with terms to
inherit, but public domain, so there is nothing to attribute and nothing to carry into a
policy's weights. It holds 120+ animations at 30 fps on a retargetable humanoid rig, and its
contents are close to the gap list this logbook has been keeping:

- locomotion in **8 directions**, which is the decoupled facing the O3DE clips have only 10
  per cent of
- **sitting**, which nothing else here has
- **push**, which is the interaction a touchable crowd is made of
- crawling, swimming, jog, sprint, death
- **root motion on every locomotion clip** since v3.0, which is what AddBiomechanics lacks

Its rig is described as compatible with other rigs, Mixamo among them. That is a bone naming
scheme and not a source: the animations are original work. The blocklist still refuses any
path containing `mixamo`, because a rule that matches on the path cannot tell a compatible rig
from the real thing, and a false refusal is cheap where a false admission is not.

The download is name-your-own-price and needs a browser session, so it is not scripted here.
Nothing has been fetched yet.

### What the whole search says

Sorting by licence finds MIT repositories wrapping non-commercial mocap. Sorting by dataset
finds Max Planck and Ubisoft. The two categories that actually clear are:

1. **An engine or an open movie that had to clear its own assets.** O3DE.
2. **Game art released as CC0.** Quaternius, Kenney.

Both are cases where somebody had a commercial reason to own their assets outright. No
research dataset in this field is in that position, which is why none of them clear.

### The rule had a hole, and the CC0 entry found it

Adding Quaternius exposed a bug in `classify` that had been there since the first version.
It walked the path one component at a time and returned on the first component that matched
anything, checking blocked and then allowed within each component. So

    /opt/weft-motion/quaternius/mixamo_rig/Walk.glb

was admitted. `quaternius` matched at the third component and the function returned before it
ever saw `mixamo_rig`.

That is the exact shape a corpus goes wrong in: a blocked source dropped inside an allowed
directory. It is not a hypothetical, it is how anyone would organise a download.

`classify` now scans the whole path for a blocked name before it considers any allowed one.
Blocked wins wherever it appears. The regression test covers three nestings, because the same
hole admits `o3de-motion-matching/lafan1/` and `addb/amass/` just as readily.

### A rig naming scheme is not a source

`mixamorig` is a bone prefix. It appears inside files whose motion is entirely their author's,
and a large part of the retargeting ecosystem references it, Godot's humanoid mapping among
them. What Mixamo licenses is the animation data, the curves. A set of bone names is short
strings, and a skeleton hierarchy is mostly dictated by where human joints are rather than by
anyone's choice.

So the rule now strips any component beginning `mixamorig` before it looks for a blocked name.
Original work does not become someone else's for using a naming convention.

A directory called `mixamo` is left refused, because that is a different claim: it says where
the clips came from. `mixamo_rig`, with the separator, stays refused too. It could be either,
and the rule matches on a path and cannot ask.

This is a tooling decision and not a legal opinion. The distinction between a functional
naming interface and the licensed work is the ordinary one and the industry relies on it, but
nothing here has been through a lawyer, and it should be before it carries weight in a release.

## A video needs two independent signals

For video, the licence field the search filter reads and the uploader's own description must
**both** assert CC-BY. Either alone is one self-assertion by someone who may not hold the
rights, and a mismarked tag is worse than no tag because it looks like consent. Requiring
both does not make an uploader right. It makes a careless tag much less likely to be the
only evidence.

The performer is a separate question from the recording. Whoever uploaded a video granted the
licence, and the people in it did not sign it. Extracting joint angles is not a likeness, but
that is reasoning rather than settled ground, so `video_admissible` returns what was relied
on and states that performer rights are not established by the video licence, instead of
returning a bare yes.

## A marketplace is not a source

Booth.pm was checked as a corpus. The SDK at `thisoverride/BoothPM-SDK` is MIT and real, but
the `.json` search endpoint Booth used to expose no longer returns JSON, so a query needs the
scraper. That did not turn out to matter, because the answer does not depend on what a search
returns.

Booth is roughly ten thousand authors who each wrote their own terms, usually in Japanese,
usually forbidding redistribution. There is no blanket licence, so **neither dict can hold
it**. Blanket-allowing would admit items whose authors forbid exactly this. Blanket-blocking
would refuse an author who explicitly permits it. Both are wrong, and a rule that is wrong in
both directions is not a conservative default, it is a broken one.

It is also mostly the wrong goods. Booth sells avatars, clothing, and accessories, which are
models and not motion, and its avatars are stylised VRChat characters rather than
anthropometric bodies. Anny's parametric distribution is strictly better for a physics body,
because it samples proportions rather than art direction.

So marketplace items are admitted **one at a time, by a person, and the person is recorded**.
`per_item_admissible` takes who read the terms, and refuses when that is empty. It has no
default and no automatic pass, because the thing being checked is not the item, it is whether
anybody actually read it.

That is the third kind of answer this rule now gives. A source can be allowed, blocked, or
answerable only by a reader, and pretending the third kind is one of the first two is how a
corpus acquires something nobody ever checked.

## Fab has CC-BY, and the filter has a trap

Fab.com carries Creative Commons listings alongside Epic's own EULA tiers, and its search
exposes them. It is behind Cloudflare, so `curl` gets a 403 on every endpoint and the query
has to run from a real browser, from which the site's own API answers.

**The parameter is `licenses=cc-by`, plural.** `license=cc-by` is accepted and silently
ignored: it returns the unfiltered catalogue with a filtered-looking URL. That is what it did
here for several queries, and the tell was that every listing came back `Personal` and
`Professional`, which are Epic's price tiers and not licences in the sense that matters.

A probe of seven guessed parameter names all reported "changed", which looked like all of
them worked and meant none of them did: Fab ranks results non-deterministically, so comparing
result ids between two calls detects nothing. The check that worked was reading the licence
field itself. Across 192 listings sampled without a filter, the only values are `Personal`,
`Professional`, and `UEFN - Reference only`. With the plural filter, every result is `CC-BY`
and carries `isCc0`.

That machine readable field is why Fab is admitted where Booth is not. Booth is free text in
Japanese written by each author. Fab states the licence in the API, so the filter is checkable
rather than trusted.

### What is actually there is thin

Keyword counts overstate it enormously. Searching the five gaps under the CC-BY filter returns
80 hits for getting up, 72 for sitting, 59 for push. Almost all of them are props: "sitting"
returns benches and theatre chairs, "strafe" returns an 8 ball and a door, "push" returns a
hand truck and a police car. The filter is on licence, and the keyword matches a title.

The real motion found was a handful of clips, mostly from one seller:

- `Animation - Getting Up 01` and `02`, by Klian, which is the largest gap in the corpus
- `Animation - Smoking 01`, same seller
- `Easy Locomotion Toolkit`

Downloads need an Epic account, so nothing was fetched. Fab is worth a hand search for
specific gaps and is not a corpus. Generation still answers the 32 minutes more cheaply than
assembling it clip by clip from a marketplace.

## Two blocks that are not about licences

The Fab sweep produced the first entries here whose problem is not who owns them.

**Easy Locomotion Toolkit** is CC BY 4.0 and free, and it is blocked. It ships no motion. It
is an Unreal Blueprint system that decides which animation to play, which is the thing weft
is training a policy to do. It surfaced under a locomotion keyword and was briefly written up
as a find before anyone read what it was. Blocking it by name stops the next reader repeating
that, and its entry says the reason is category and not licence, because a blocklist that
does not distinguish the two teaches the wrong lesson.

**Props cannot be blocked by name at all.** Under a CC-BY filter, searching the five gaps
returned 80 hits for getting up, 72 for sitting, 59 for push, and almost none of them were
motion: benches and theatre chairs for `sitting`, an 8 ball and a door for `strafe`, a hand
truck and a police car for `push`. The licence filter answered who owns it. The keyword
matched a title. Nothing checked the middle, which is what the thing actually is.

Enumerating props is unwinnable, so `motion_admissible` defaults to no. A candidate is motion
when it can demonstrate motion: animation tracks, at least two frames, a stated frame rate,
and at least eight joints. A single pose is not a motion. A rate nobody stated is a duration
nobody knows. `Rhino Animation Walk` is animated and is still refused, at four joints, because
it is not a body.

That is the same shape as the provenance rule, which refuses a clip from nowhere rather than
listing every place a clip must not come from. Both default to no and ask the candidate to
show its working.

## The XR catalogue, and a claim in this logbook that was wrong

`cschell/xr-motion-dataset-catalogue` has 25000 downloads and aligns nine XR motion datasets
to one format. It states no licence of its own, and one of its nine says permissions are still
pending, so the aggregator is negotiating per dataset as well. It is head and hand
trajectories rather than full body, which makes it a source of realistic **input** traces for
what an HMD actually delivers, and not a body corpus.

Its constituents were checked one at a time, which is what a catalogue requires.

**Who is Alyx** is `CC BY-NC-SA 4.0`, so non-commercial like nearly everything else. The paper
around it is CC BY, being Frontiers open access, and the paper's licence does not reach the
data. That distinction is worth keeping: an open access paper and its dataset are two
different grants.

The licence is not the important part of that entry.

### Motion identifies the person who made it

The dataset is 110 hours from 71 participants, and it is not only motion. It carries eye
tracking with gaze and pupil position, screen recordings of what each player saw, demographics
including age and sex and body parameters, and physiological data including blood volume
pulse, heart rate, skin conductance and ECG.

And its title is *"Who is Alyx? A new behavioral biometric dataset for **user identification**
in XR"*.

This logbook previously recorded, in the reasoning behind the two-signal video rule, that
extracting joint angles is not a likeness because nobody can be identified from hip flexion.
**That was wrong.** The paper's result is that head and hand motion identifies its author well
enough to work as a biometric. The claim was reasoning, it was offered as reasoning rather
than as fact, and a dataset found while looking for something else disproved it.

The consequence is not only about this dataset. Motion recovered from video of a person is
personal data about that person, so the GEM-X path over CC-BY video inherits a question the
video licence cannot answer, because the uploader granted it and the person in frame did not.
`video_admissible` already refused to return a bare yes there. It was right for a weaker
reason than the real one.
