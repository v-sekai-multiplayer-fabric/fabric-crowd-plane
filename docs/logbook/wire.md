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

| send rate | hold | extrapolate | interpolate |
| --- | --- | --- | --- |
| 20 Hz | 59.5 | **32.3** | **15.5** |
| 10 Hz | 112.0 | 85.2 | **38.5** |
| 5 Hz | 197.8 | 209.8 | **86.0** |
| 2 Hz | 365.9 | 603.4 | **199.3** |

Interpolation beats both at every rate, and by enough to change a decision: **interpolating at
10 Hz is better than holding at 20**, which is better quality at half the bandwidth. It costs
one send interval of latency, which is 100 milliseconds at 10 Hz.

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

## Evaluated: the levers buy quality, not capacity

| configuration | kB/s | egress share | always-on | why |
| --- | --- | --- | --- | --- |
| baseline: 4 near at 20 Hz held, 70 far at 1 Hz | 9.5 | 88 percent | 26 | |
| plus extrapolation on near bodies | 9.5 | 88 | **26** | error 59.5 to 32.3 mm, zero bytes |
| plus interpolation on far bodies | 9.5 | 88 | **26** | smoother, zero bytes |
| near at 10 Hz interpolated | 5.2 | 80 | 44 | error 38.5 mm, and **100 ms** |

**The cost does not move.** Both adopted levers are free in bytes: velocity is already inside
the 100-byte packet and was being sent as zero, and interpolating far bodies changes what the
client does with samples it already receives. They halve the visible error and buy nothing at
the till.

The one that would move the cost is the one that cannot be taken. Near bodies are **91 percent
of the wire**, and the only way to shrink them is to send them less often, which needs
interpolation, which costs 100 milliseconds on exactly the bodies a player can reach. That is
the latency the product exists to sell.

So the number stands at **24 to 26 always-on for 15 dollars**, and this line of work is
finished: the wire is as small as it gets without spending the thing being sold.

## Squeezing the packet without changing the packet

Every tactic here is a transport transform: reversible, invisible to the schema, and the
decoder still hands the application the packets the encoder was given. `bench/wire_codec_tactics.py`.

| tactic | B/body/frame |
| --- | --- |
| temporal delta of the absolute position | 111.2 |
| plus spatial decorrelation, joint minus root | 111.1 |
| plus joint offsets quantised to millimetres | 88.1 |
| plus an order-1 context model | **76.9** |

**Spatial decorrelation bought nothing, and that is the useful result.** Subtracting the root
before delta-coding looked obvious: every joint's absolute position carries the body's global
translation, so removing it should collapse the entropy. It does not, because the temporal
delta has already removed it. The delta of an absolute position and the delta of a
root-relative position differ only by the root's own delta, which is a few hundred
micrometres. The first transform had already taken what the second was reaching for.

The two that worked are unglamorous. Joint offsets do not need micrometre precision, and a
millimetre is invisible on a limb, which is 21 percent. An order-1 model conditioning each
value on its own previous delta is another 12.

111 to 77 bytes, a 1.44 times squeeze, no schema change, no negotiation.

### What is left, and why it stays

77 bytes against 21 for a body-oriented encoding is still 3.7 times, and the residue is not
compressible. The packet stores a position for every joint: 39 int64 values for a body, which
after every transform still carry real information, because a limb genuinely moves. The
body-oriented form sends rotations and derives the positions from a skeleton, so it never
pays for them at all.

That gap is the price of the format decision, now measured rather than estimated. It buys 31
always-on players rather than 26, and a body-oriented wire would buy 59.

### A caution about this measurement

An earlier version of this table read 10.4 bytes rather than 111, because the entropy was
pooled across joints and counted once instead of summed over all 39 values in a body. The
number was ten times too good and looked plausible. It was caught by comparing against the
earlier packet measurement of 108, which is the argument for making a new measurement agree
with an old one before believing it.

## CORRECTION: the packet was measured carrying the wrong thing

Every packet measurement in this book packed raw quaternion components into the rotation
field. The field is `i16 swing-twist x3`, and the pose representation this project chose is
the Mecanim muscle system: three scalars for a joint, each normalised to an anatomical range.
Swing-twist and muscles are the same decomposition. The field already fits what we send, and
I filled it with something we would never send.

That made every comparison in this book unfair in the same direction: quaternion-per-joint
packets measured against a muscle-space body encoding.

`bench/wire_packet_muscle.py`, same motion, same method, muscles in the rotation field with
per-muscle bit depth taken from each joint's own range at 0.088 degrees:

| form | B/body/frame |
| --- | --- |
| packet with quaternions, positions derived, order-1 | 53.5 |
| **packet with muscles, positions derived, order-1** | **26.1** |
| body-oriented encoding, measured earlier | 21.0 |

**1.24 times, not 2.55.** The residue is the root position in int64 micrometres and the parts
of the envelope that do not compress to nothing.

### What that does to the decision

| wire | kB/s | egress share | always-on for 15 dollars |
| --- | --- | --- | --- |
| packet with quaternions, as wrongly measured | 5.1 | 79 percent | 42 |
| **packet with muscles** | **2.9** | **59** | **57** |
| body-oriented, if we diverged | 2.5 | 55 | 59 |

The earlier entry recorded that taking the org packet costs 35 always-on players, and framed
that as a deliberate trade of capacity for one format and one conformance test. **That cost
was almost entirely my measurement error.** The real price is 2 players out of 59, which is
not a trade at all.

So the decision to accept the packet was right, and the reasoning under it was wrong. The
skeleton-class extension discussed earlier is also unnecessary: the position field does not
need removing from the schema, it only needs to stop varying, and the rotation field was
already the correct shape.
