# The wire

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

Oldest entry first. A new entry goes at the bottom.

## The wire

`bench/wire_muscle.py`, `bench/wire_cheap_vs_nasty.py`, `bench/wire_dict.py`. Bytes for one
body for one frame.

| form | bytes |
| --- | --- |
| position and rotation for each joint, 100 B an entity | 3600 |
| rotations only, 12 bit, packed | 174 |
| cheap CBOR JSON-LD, zstd with the last frame | 884 |
| 49 muscles at their own bit depth, packed | 76 |
| packed then zstd | 83 |
| delta then zstd | 69 |
| static trained dictionary, 110 KiB | 72 |
| keyframe every 20 or 60 frames | 75 |
| streaming, full session history | 69 |
| order-0 entropy floor, delta | 53 |

Muscle space is V-Sekai's `godot-humanoid-project`, Apache-2.0, Lyuma and lox9973. A pose
is 95 scalars, each one axis of one joint normalised over an anatomical range the file
states. 49 of them are a body without fingers, eyes, or jaw.

Two rows are worth reading twice. Compressing the packed stream makes it **bigger**, and no
dictionary scheme reaches the entropy coder. A dictionary feeds LZ and LZ finds repeated
substrings; a bitpacked delta stream has none, because the values sit at different offsets
and smear across byte boundaries. What is left is redundancy in the symbol distribution,
which is exactly and only what an entropy coder takes. Cheap CBOR compresses well for the
opposite reason: it repeats its key names every frame.

Run-length encoding was checked and is not worth having. 13 percent of muscle deltas are
zero, but the runs are short and scattered, and an entropy coder already spends about 3
bits on a symbol that common.

## Real motion, and the correction it forced

`bench/wire_learned.py`. The synthetic gait above makes every muscle an independent
sinusoid, so it has no inter-joint coupling. Driving the tracked avatar in MuJoCo under
gravity and contact, in its own 26 degree of freedom joint space:

| coder | bytes/body/frame |
| --- | --- |
| order-0 entropy of deltas | 26 |
| order-1, context on the joint's own previous delta | 21 |

So the 53 byte figure was pessimistic: physically coupled motion compresses about twice as
well as motion assembled from independent sinusoids. Not a like for like swap, because 26
driven joints is not 49 muscles, so the direction is the result and not the ratio.

## The pose manifold, which is not there

`bench/wire_manifold.py` against sinew-mocap's calibrator set, `sinew-mocap/mount-drift`
release `calibrator-v1`: 11794 real poses, 25 subjects, 11 AddBiomechanics studies, 30
segments in the 6D continuous rotation representation.

The poses are natural and not a spread over the space. Two drawn at random sit 34 degrees
apart, where two uniform rotations sit 131 apart, and no segment has a spread over 60
degrees.

| components | of 180 |
| --- | --- |
| 90 percent of variance | 59 |
| 99 percent | 124 |

Truncating to 48 leaves a median segment 10 degrees wrong. Stripping the global heading
first, which linear PCA provably cannot represent, makes it slightly worse.

This contradicts an earlier claim in `spec/CrowdBudget.lean` that coordinated human motion
is low rank. That is a claim about a single activity and it does not survive 25 subjects and
11 studies. A pose is a small ball in a high dimensional space, not a thin sheet in one, so
a linear latent has nothing to take.

The set cannot answer the temporal question, which is where every gain has come from.
Consecutive rows are 30 degrees apart, so it holds a pose distribution and not a motion.
