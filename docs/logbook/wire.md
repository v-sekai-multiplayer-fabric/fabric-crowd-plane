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

## The org already specified the wire, and this book reinvented it

`lean-entity-packet` is the source of truth: `XRGridEntityPacket`, 100 bytes, fully integral
so it models exactly in Lean, with Plausible roundtrip properties, a `packet_golden.csv` of
canonical bytes, and a C++ decoder differentially verified against 64 golden vectors.

| offset | field | encoding |
| --- | --- | --- |
| 0 | global_id | u32 |
| 4 | position xyz | int64 absolute micrometres |
| 28 | velocity xyz | i16 scaled to V_MAX |
| 40 | hlc | u32, frame shifted 8 with counter |
| 44 | class and owner | u32 |
| 48 | sub_index | u32 |
| 52 | rotation | i16 swing-twist x3 |
| 58 | payload | 42 bytes |

Alongside it, `lean-interest-mgmt` specifies who sees whom and the solve order, and
`lean-fabric-protocol` holds the saturation and SLA bounds. None of these were read before
this book measured a wire format from scratch.

### Reconciling 100 bytes with 21

The crowd plan puts one entity on each joint, so a body is 27 packets, which is 2700 bytes.
This book measured 21 bytes for a body. That is 128 times apart and it is not a
contradiction: **the packet is the schema and the compression is the transport.**

Everything the 21-byte measurement exploits is redundancy the packet deliberately leaves in.
Position is an absolute int64 micrometre coordinate that changes by a few hundred
micrometres between frames. The HLC increments by one. Class, owner, and sub-index never
change. The payload is constant for a joint. Delta between frames plus an entropy coder takes
all of it, which is exactly what `wire.md` measured, and none of it requires a different
format on the wire.

So the correct prototype emits `XRGridEntityPacket` and compresses the stream. The invented
format in `proto/plane.py` is wrong twice over: it is not the org's schema, and it is
uncompressed.

`packet_golden.csv` is the conformance test, and a C++ decoder already passes it. Anything
this repository writes should pass it too rather than assert compatibility.

## Conformance: 64 of 64 golden vectors

`proto/entity_packet.py` mirrors the Lean codec field for field, and
`proto/test_packet_golden.py` checks it both ways against `packet_golden.csv`: decode must
reproduce the fields, and re-encoding must reproduce the canonical bytes exactly.

**64 pass, 0 fail.**

It caught one bug, and it was the kind a README cannot catch. The table in the repository
lists field offsets, and reading it left a 4-byte gap between velocity at 28 and the HLC at
40. The Lean says 6: velocity ends at 34 and bytes 34 to 39 are unused. The header is 58
bytes, not 56, and the assertion that the header must end where the payload begins failed on
the first run.

That is the argument for the golden vectors existing. A summary of a format is not the
format, and this book has now been caught twice in one day working from summaries: once here
and once when a wire format was measured from scratch while a specified one sat in the
organisation with proofs attached.

## DECIDED: the wire is the org packet, and it costs 2.5 times the capacity

`bench/wire_packet_stream.py`, real simulated motion, 13 joints a body, one 100-byte
`XRGridEntityPacket` for each joint:

| form | B/body/frame |
| --- | --- |
| packets raw | 1300 |
| through zstd | 277 |
| delta the varying fields, then zstd | 195 |
| entropy floor of those deltas | 108 |
| the body-oriented form measured earlier | 21 |

Five times the body-oriented form at the floor, and it is not a compression failure. The
packet carries an absolute int64 position for **each joint**: three independent eight-byte
coordinates that all move every frame, when a skeleton derives every one of them from its
parent's rotation and a bone length that never changes. A coder removes redundancy, and
independent positions are not redundant.

What that costs, at 4 near bodies at 20 Hz and 70 far at 1:

| wire | kB/s | egress share | always-on for 15 dollars |
| --- | --- | --- | --- |
| body-oriented, 21 B | 3.5 | 73 percent | 59 |
| **packet floor, 108 B** | **10.4** | **89** | **24** |
| packet delta and zstd, 195 B | 17.4 | 93 | 15 |

**The decision is to accept it.** 24 always-on rather than 59.

Three options were on the table. Diverge for skeletons and keep 59, at the cost of the crowd
plane no longer speaking the format the rest of the fabric speaks. Extend the packet with a
skeleton class whose position is derived rather than sent, which is the technically better
answer and is a change to a spec repository owned elsewhere. Or accept the packet as it
stands.

Accepting buys one format, one conformance test, one decoder already verified in C++, and no
negotiation. It costs 35 always-on players at the 15 dollar tier. That is the trade, taken
deliberately, and the extension stays available if the number ever matters more than the
simplicity.

One caveat on the figure: this measured 13 joints a body, and the crowd budget assumes 36. A
36-joint body makes the packet form proportionally worse, so 24 is the optimistic end.

## The three netcode levers, and which of them this design actually uses

Asked plainly: interpolation, extrapolation, and sending intents with rollback over
deterministic code. None had been applied systematically, and one had been broken outright.

### Extrapolation: measured, and it works the opposite way round

The packet carries a velocity at offset 28, scaled to V_MAX, and its purpose is exactly this.
Every measurement in this book sent it as **zero**.

`bench/wire_extrapolate.py`, position error a viewer would see, in millimetres:

| send rate | hold, mean | hold p99 | extrapolate, mean | extrapolate p99 |
| --- | --- | --- | --- | --- |
| 20 Hz | 59.5 | 266 | **32.3** | **203** |
| 10 Hz | 112.0 | 508 | 85.3 | 532 |
| 5 Hz | 197.8 | 826 | 210 | 1220 |
| 2 Hz | 363.6 | 1231 | 599 | 3333 |

It halves the error at 20 Hz and **makes things worse below 10**. Limbs swing, so carrying a
joint forward in a straight line overshoots the turn, and the further it is carried the more
confidently wrong it gets.

So extrapolation is a quality lever at a fixed rate, not a way to lower the rate. That is the
reverse of how it is usually reached for, and it means filling in the velocity field is worth
doing while cutting the send rate on the strength of it is not.

### Interpolation: available, and it costs the thing being sold

Buffering a frame and interpolating between two known states is smooth by construction and
never overshoots. It costs one frame of latency, minimum, and this design already spends its
latency budget on a 16.7 millisecond tick to make a shove feel instant.

For **far** bodies that is free: nobody can push them, so a frame of delay is undetectable,
and the design already sends them at a lower rate. For bodies within reach it is the one
thing not to do.

### Intents, rollback, and deterministic code: does not survive a crowd

Sending only inputs and having every participant simulate the same thing is the cheapest wire
there is. It is how fighting games and lockstep strategy games work, and it needs bit-exact
determinism, which is what a fixed-ISA sandbox like libriscv would provide.

It does not fit here, for a reason that has nothing to do with determinism. **Every client
would have to simulate every body.** A room holds 139 bodies at 55 microseconds each, which
is a whole core, and the clients are headsets. Lockstep trades bandwidth for compute on every
participant, and this workload has no compute to spare on the participants.

Emulation makes it worse: a fixed ISA is slower than native by a large factor, and the budget
already spends 91 percent of a person on the body.

What survives from that family is the half that needs no determinism: **predict your own
avatar locally and reconcile against the server.** One body, not 139, and a mismatch corrects
against authority rather than requiring everyone to agree in advance. That is ordinary
netcode and it is worth doing.

### Where that leaves the wire

| lever | verdict |
| --- | --- |
| velocity in the packet, extrapolated at 20 Hz | **use it** — halves the error, costs nothing, currently zeroed |
| extrapolate to justify a lower rate | do not — worse than holding below 10 Hz |
| interpolate far bodies | use it — they are already slow and cannot be touched |
| interpolate near bodies | do not — it spends the latency the product sells |
| lockstep over a deterministic sandbox | no — every client would simulate the whole room |
| local prediction of your own body | worth doing, and needs no determinism |
