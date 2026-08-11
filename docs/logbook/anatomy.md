# The body itself

What the avatar is made of: its segment lengths, its masses, its joint ranges, and the motors
that drive it. Every number here is a measurement or a ratio of two, with the source attached.

`body.md` holds what a body costs to simulate. This holds what a body is.

## The body was not a person, and somebody had already fixed that

The body in `assets/tracked_avatar.xml` was written by hand from round numbers. Measured
against real anatomy it is wrong in four ways at once, and the last two explain behaviour
that had been blamed on the solver.

**Segment lengths.** Against Anny's SOMA rest pose the legs are 8 to 9 per cent short and the
arms 3 to 4 per cent short. Thigh 0.400 against 0.433, shin 0.390 against 0.424.

**Segment masses.** MS-Human-700 gives a distribution: trunk 26.2 per cent, pelvis 13.9,
thigh 10.4 each, shin 4.8, upper arm 3.2, forearm 1.85, hand 0.65. A first pass grouping by
name reached only 73 per cent of body mass, because the trunk is 50 separate bodies whose
names match no obvious pattern. Taking the trunk as the remainder is the only way to be sure
nothing is dropped.

**Joint ranges are wider than a person's.** Ankle 1.3 times, shoulder 1.3, elbow 1.2, and hip
flexion has its sign convention inverted: the model allows -109 to 34 degrees where the
anatomy is -30 to 115. Only the knee agrees, at 0 to 138.

**Every joint carries the same 300 N m.** Against measured human maxima the neck is 10 times
too strong, the elbow 5.5, the shoulder 3.8, the ankle 2.1, and the hip and knee 1.4.

The last two together describe a body with superhuman arms that can also reach poses a person
cannot. A controller on that frame will find a strategy that works and is not balance, which
is what the PD servo did: it collapsed the crowd and then ejected it upward.

### The prior art was already installed

None of this is new. `protomotions/robot_configs/soma23.py` carries the same body under
`BUILT_IN_PD` and splits it three ways:

| group | effort limit |
| --- | ---: |
| Spine, Chest, Neck, Head | 300 |
| Shoulder, Arm, Hand | **150** |
| Leg, Shin, Foot, ToeBase | 300 |

Arms at half of legs and trunk. Our flat 300 gives arms exactly twice what NVIDIA ships for
the same skeleton. The direction argued from muscle anatomy and from the literature is the
direction their config already takes, and theirs has trained working policies, which is
better evidence than either.

Their numbers and the literature disagree on how far to go. The literature puts the elbow at
55 N m and the shoulder at 80, which is a ratio nearer four to one than two to one, and it
puts the neck at 30 against their 300. Two to one is what is known to train, so that is the
floor of the correction and not the whole of it.

`bench/real_body.py` holds every number with the source it came from. Nothing in it is a
tuning constant: each value is a measurement or a ratio of two measurements.

### What MS-Human-700 is not for

It is not the body. 700 muscles at a 2 ms timestep is 4182 microseconds a frame for ONE
body, so about 4 to a core against roughly 200 for capsules. The Locomotion variant, at 100
muscles and 36 degrees of freedom, is 966 microseconds and about 17 to a core, still twelve
times worse. It is a reference for masses, ranges, and the relative pattern of strength.

Its muscle sum is also not a torque limit. Summing every muscle at peak isometric force over
its moment arm counts antagonists that in reality oppose each other, and lands 1.5 to 4 times
above measured human maxima: hip 755 against about 210, ankle 583 against about 140. A first
pass also reported a knee ceiling of 20936, which came from summing the model's knee slide
degrees of freedom, whose moment arms are newtons and not newton metres. Thirteen of its 85
degrees of freedom are translations and must be excluded.

## Recovering the motors for a body that was sampled, not built

Anny samples a shape: height, mass, proportions, muscularity. It does not sample actuators,
and a 1.5 m 48 kg body cannot be driven by numbers that fit a 1.9 m 95 kg one. The torque
limits, the armature, and the gains all have to move with the body or the controller is
driving something that is not there.

None of it is fitted. Each follows from dimensional analysis anchored on the one body whose
numbers were measured.

**Torque follows mass.** Muscle force follows physiological cross-sectional area and the
torque follows that force times a moment arm. Isometrically, area goes as L^2 and the arm as
L, so torque goes as L^3, and mass goes as L^3 as well. Torque per kilogram is therefore
constant, which is why the literature reports it that way. It survives non-isometric scaling
too: hold height and vary mass, and area goes as m/L while the arm still goes as L, so torque
goes as m again.

**Muscularity modulates it at fixed mass**, because two bodies of equal mass do not have equal
cross-section. It multiplies torque and nothing else.

**Inertia follows m L^2**, so armature does, and so do the gains. `body.md` above records the
bound kp < 4I/dt^2, so kp follows inertia, and critical damping puts kd at 2*sqrt(kp*I),
which follows inertia too. `kp` is set at 0.6 of its own ceiling, which is a ratio to a
derived bound and not a number chosen to feel right.

`bench/motors.py` holds it. The reference body reproduces the measured torques exactly, which
is the check that the scaling has not quietly moved the anchor.

| body | hip | knee | elbow | armature | kp |
| --- | ---: | ---: | ---: | ---: | ---: |
| 48 kg 1.52 m, light build | 122 | 126 | 32 | 0.0110 | 95 |
| 55 kg 1.55 m, muscular | 206 | 213 | 54 | 0.0131 | 113 |
| 70 kg 1.70 m, reference | 210 | 217 | 55 | 0.0200 | 173 |
| 78 kg 1.88 m, light build | 199 | 206 | 52 | 0.0273 | 235 |
| 95 kg 1.90 m, heavy | 328 | 339 | 86 | 0.0339 | 293 |

Hip torque spans a factor of 2.7 and armature a factor of 3.1 across the range Anny samples.
A single set of motors is wrong at both ends by about that much, which is the quantity the
flat 300 N m was hiding.

The second row is the one worth reading twice. A 55 kg muscular body lands within two per
cent of the 70 kg reference at the hip, because muscularity makes up what mass does not. Pure
mass scaling would have made it 40 per cent weaker and wrong.

## Rendering the body, and four ways SOMA-X says no

Stick figures caught two of the first four generated clips being wrong. A body catches more,
because a pose can be joint-correct and still read as inhuman. SOMA-X carries Anny as a
first-class identity model, so `bench/anny_render.py` poses the corpus on the body the corpus
is actually about.

Four mismatches, each a one-line fix, none of them documented:

- `SOMA_procedural_transforms.json` is not in the released assets, so the layer must be built
  with `enable_procedural_transforms=False`.
- Correctives then require those transforms, so `apply_correctives=False` as well.
- MHR **asserts** on a missing `scale_params` rather than defaulting.
- The `anny` on PyPI predates `create_fullbody_model`, which py-soma-x calls. Our own checkout
  at `/opt/weft-motion/anny` has it, so installing the checkout over the wheel fixes it.

### The scale parameter is not a number

Passing `ones` to satisfy the MHR assert produced a body **2.0 m tall**. Sweeping a single
scalar down to 0.70 still produced 1.96 m, which is when it became clear the sweep was the
wrong shape of answer: **MHR has 45 identity coefficients and 68 scale parameters.** Scale is
per segment, not global, so setting all 68 to one value is not a height and searching over
that value cannot find one.

This is the fourth scale or unit error in this project, after Anny's centimetres, the
somaskel77 skeleton disagreeing with the motion beside it, and the Fab USDZ declaring Y-up
over Z-up data. The pattern is identical every time and it is not really about units: **a
number was supplied to get past an error rather than derived from something measured.** The
assert existed precisely because there is no sensible default, and it was answered with a
guess.

The right fix is to solve the 68 parameters for a stated height, with the population coming
from Anny's conditional distributions, which is the same machinery `motors.py` already uses to
scale actuators from height and mass. Not done yet.

## The Anny parameters were already worked out, in Lean, in this org

`v-sekai-multiplayer-fabric/lean-humanoid-rom` holds them, and this session re-derived several
by hand before finding it. What is in there:

- `anny_rom_real.json`, measured bone lengths and joint ranges per sampled body
- `anny_rom_sweep.py` and `anny_to_humanoid_rom.py`, the sweep already written
- `AddBiomechanicsROM.lean`, `B3DParser.lean`, `extract_addbiomechanics_rom.py`
- `addbiomechanics_env/pixi.toml`, the nimblephysics environment **rebuilt from scratch today**
- `core/HumanoidConstraints.lean`, `core/KusudamaSolver.lean`, `core/EWBIKDecomposition.lean`

The API is the part that cost the most time. Phenotypes are a **dict of named tensors**, not a
flat vector:

    model = anny.create_fullbody_model()
    model.get_mesh(phenotype_kwargs={"height": torch.tensor([[0.65]]), ...})

Going through py-soma-x's `SomaLayer` instead, which takes a flat `identity_coeffs`, produced a
sequence of shape errors ending in `[B, 11] got (1, 6)`. The 6 is real: the model is built with
six active phenotypes because `EXCLUDED_PHENOTYPES` drops cupsize, firmness, and the three
appearance categories, while the parser still demands all eleven. Passing eleven zeros then
rendered a **0.44 m** body, and sweeping the height entry moved it only to 0.90 m, which is
where guessing should have stopped.

The units are not uniform either. In `anny_rom_real.json`, **age is in years**, 18.03, while
gender, weight, and height sit near [-1, 1]. A single normalisation assumption across the
eleven is wrong.

### What this cost

Re-derived by hand this session, all of it already present in that repository: the pixi
environment for nimblephysics, the AddBiomechanics reader, segment lengths from the Anny rest
pose, and joint ranges. The measurements agreed, which is some comfort, but agreement was not
worth the time.

The rule that would have caught it is not about Anny. **Search the organisation before
deriving anything anatomical.** Fourteen `lean-*` hexagons exist there, and `lean-humanoid-rom`
is named exactly for what was being rebuilt.
