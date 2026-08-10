# The platform

Part of the crowd plane logbook. See `README.md` for the apparatus and the index.

Oldest entry first. A new entry goes at the bottom.

## On the platform

`bench/fly/run_all.py`. Fly `performance-2x`, `sjc`, one machine created, run once, and
destroyed. The image is `bench/fly/Dockerfile`, 72 MB.

| batch | median us | p90 us |
| --- | --- | --- |
| 14 | 41.02 | 52.56 |
| 28 | 39.35 | 44.10 |
| 56 | 46.37 | 51.48 |

Against 27.3 median and 31.4 p90 on the desk, the same body costs 1.7 times as much here.
The tail is wider too: 28 percent between median and p90 against 15 at the desk.

| vCPU | people at p90, desk | people at p90, platform |
| --- | --- | --- |
| 1 | 487 | 301 |
| 3 | 1280 | 830 |
| 4 | 1607 | 1064 |

Three vCPU held a thousand at the desk and hold 830 here. The crowd plane needs four, and
the venue machine goes from needing six to needing seven of the eight it buys.

Nothing about the design was wrong. The arithmetic held and the constant was measured on a
machine nobody deploys to.

## Two machines, two answers

The run above was repeated on a second `performance-2x` in `sjc`, same image, same
settings, a different machine.

| machine | median us | p90 us | people on 3 vCPU at p90 |
| --- | --- | --- | --- |
| `2870276b497228` | 46.37 | 52.56 | 830 |
| `d890411b973d18` | 53.85 | 65.74 | 681 |

25 percent apart on the tail, from the same image on the same size in the same region. This
is shared tenancy, and it is a larger effect than any tuning measured on the desk.

So a single run does not size a plane here. What sizes it is the worst machine the platform
will hand out, and two samples do not bound that either. The design number stands at the
worse of the two until a wider sample exists.

That also puts a floor under how much of this can be answered by benchmarking at all. A
plane that must hold 60 Hz on a machine it cannot choose has to degrade rather than assume,
which is an admission-control question and not a physics one.

## Sizing against a machine nobody chose

Two samples are a range, not a bound. Extending the table above to a machine 20 percent
worse than the worse of the two, which nothing observed rules out:

| p90 of the body | crowd vCPU for 1000 | venue vCPU |
| --- | --- | --- |
| 31.4 us, the desk | 3 | 6 |
| 52.6 us, the good machine | 4 | 7 |
| 65.7 us, the bad machine | 5 | 8 |
| 80.0 us, unobserved | 6 | 9 |

The platform sells eight. A touchable thousand fits the good machine with a core spare,
fits the bad machine with none, and does not fit a machine slightly worse than one already
seen.

No constant makes that safe, because the quantity it would bound is not bounded. So the
constant goes, and admission triggers on a ratio instead: the work a tick took over the
tick period, both measured on the machine that is running. Admit while the rolling p99 of
that ratio stays under one. A tick longer than a tick is a missed frame, so the threshold
is one by definition rather than by choice, and a slow machine admits fewer people without
anybody deciding it should.

What it costs is the promise. A venue cannot advertise a size it will always hold. It can
advertise what it holds on the worst machine it will keep, and give back the rest as
headroom. That is weaker than a fixed capacity and it is the true one.

## A ten minute tick loop, which is where the microbenchmark stopped being true

`bench/fly/tick_loop.py`. Fly `performance-2x`, `sjc`, machine `2872616f530748`. 301 bodies,
one core, 36000 ticks at 60 Hz, a fixed schedule, and a count of every tick that overran.
301 is what the microbenchmark on the good machine said one core holds at p90.

| | us |
| --- | --- |
| budget for a tick | 16667 |
| work, p50 | 16525 |
| work, p90 | 17275 |
| work, p99 | 20723 |
| work, p99.9 | 24115 |
| work, max | 45505 |
| tick start lateness, p99 | 236931 |
| tick start lateness, max | 286227 |

**13150 ticks of 36000 missed. 36.5 percent.**

Two things in that table are worse than the arithmetic that preceded it.

The work itself is 18 percent above what the microbenchmark predicted: 55 microseconds for
each body against 46.4. A microbenchmark steps the same bodies in a tight loop with
everything hot. A tick loop sleeps between passes, and what it wakes up to is a colder
cache. The difference is not measurement error. It is the cost of being a loop.

And the lateness is the real result. A tick begins a quarter of a second after it was due,
at p99. Work never exceeded 45 milliseconds, so a tick that starts 237 milliseconds late was
not delayed by its own work. It was descheduled. This is a shared tenancy virtual machine
and the hypervisor takes the core away for intervals far longer than a frame.

So 99 percent load is not a tight fit. It is a broken one, and a p90 from fifteen samples
over a few seconds cannot see it. Every capacity figure derived from the microbenchmarks
above should be read as a ceiling that is never reached.

| physics share of the tick | people for one core, at 55 us a body |
| --- | --- |
| 100 percent | 303 |
| 75 percent | 227 |
| 50 percent | 151 |

The load ratio in `spec/CrowdBudget.lean` is what makes this safe without a constant. This
entry is why it is needed: the number that was wrong was not the body cost. It was the
belief that a measured body cost predicts a loop.

## Gamend, and why it is not a competitor

`https://appsinacup.com/gamend-stress-test/`. A game backend stress-tested to 4000 concurrent
connections, about 3000 requests a second, on 4 vCPU and 1 GB for 8 dollars a month, in
Elixir over SQLite or Postgres. 99.98 percent success. p99 latency **15 seconds**.

Reading it as a rival to this plane would be a category error, and the differences are the
useful part.

| | Gamend | this |
| --- | --- | --- |
| simulates | account writes and user data reads | 60 Hz rigid-body physics |
| concurrency | 4000 connections | 120 to 150 bodies |
| work for each unit | about one request, bursty | 55 microseconds every 16.7 ms, forever |
| p99 latency | 15 seconds | 16.7 milliseconds |
| hardware | 4 vCPU, 1 GB | 2 vCPU, 4 GB, dedicated |
| cost | 8 dollars a month | 15 |
| admission control | a hard cap of 1000 connections | tick load p99 under 1, and a person-hour budget |

**CORRECTION.** An earlier draft of this entry said accounts and persistence are "exactly
what weft needs and does not have". That is wrong, and weft's own `lib/` says so: about 3000
lines of Elixir holding `Weft.Actor`, a single-writer actor addressed by `{name, key}`,
`Weft.Actor.Store` with the SQLite-over-FoundationDB design, `Weft.Pool` for serverless
runner pools, plus zones, gateway, interest, and limits. All of it rivet-shaped. The overlap
with Gamend is real and it is large: two Elixir game backends with actors and persistence.

What weft has that is genuinely absent is **durability**. `Weft.Actor` says it plainly: state
is an in-memory map standing in for per-actor KV, and the SQLite-over-FoundationDB store is a
design rather than code. Gamend has a working store at 4000 connections. weft has a better
design for a different tier and no rows on disk.

So the two do compose, but not the way that draft claimed. It is not that one supplies a
missing layer. It is that they serve two different tiers of persistence which this design has
been treating as one.

### The number that matters, and it is the latency

A p99 of 15 seconds is not a criticism. For account creation it is fine, because nobody
notices a slow signup and the work is bursty enough that queueing is the right answer.

For a shove it is fatal, and the gap is **three orders of magnitude**. That single row is why
the two systems cannot share a machine class, and it explains the price difference below
better than any other line.

### The price difference is the deadline

Gamend gets 4 vCPU for 8 dollars, which is about 2 dollars a vCPU. This design assumes 31
dollars, which is 7.75 times more. That gap looked like a mistake in the cost model and it is
not: their vCPUs are shared and mine are dedicated. A shared vCPU is scheduled against other
tenants, which produces exactly the tail that a 15-second p99 absorbs and a 16.7 millisecond
tick cannot.

`platform.md` already measured what that tail does here: 237 milliseconds of hypervisor
deschedule at p99 on a machine that was only 99 percent loaded, and 25 percent variance
between two machines of the same size in the same region. On dedicated cores. Shared would be
worse.

So the honest reading of the 7.75 times is not that the cost model is pessimistic. It is that
**a real-time deadline costs about eight times as much per core as a request-response
workload**, and any comparison of dollars between the two has to carry that.

### What is worth stealing

Their hard cap of 1000 simultaneous connections is admission control, arrived at from the
same direction as the tick-load gate here: a system that degrades instead of refusing will
degrade for everybody. Their write-up also records that 256 MB ran out of memory and that
database timeouts dominated until caching went in, which is the same shape as this logbook
finding that the microbenchmark stopped being true inside a loop. Both are the difference
between measuring a component and running a system.

## Two tiers of persistence, costed as one

The correction above exposes a sizing error worth its own entry.

The full production bill puts 442.52 dollars a month into persistence: a three-node
FoundationDB cluster at 314.16, a store plane at 83.36, and 300 GB of volumes at 45.00. That
was sized because the architecture mandates FoundationDB, and it was sized once for two jobs.

Those jobs are not alike.

**Hot actor state** is per-actor SQLite pages behind a single-writer invariant, read and
written while a body is being simulated, and it is what FoundationDB is for: no local file,
so an actor's database migrates between machines with no copy. That is `Weft.Actor.Store`.

**Metagame state** is accounts, profiles, and inventory. It has no deadline, it is read far
more than written, and a request-response store on a shared vCPU serves it. That is what
Gamend does for 8 dollars.

Charging the second at the price of the first is the mistake. If the metagame tier costs 8
rather than 442, the full production bill falls from 1679.05 to about 1244.53 a month, which
is 1.24 for each head against 1.68. A 26 percent cut from deleting an assumption rather than
optimising anything.

What this does not license is deleting FoundationDB. The hot tier still needs it, and at the
15 dollar scale a single node on the venue machine already covers that, which the 15 dollar
topology assumed and the production topology forgot.

## One FoundationDB, on disk, backed up to S3

The entry above says a three-node cluster was priced where one node would do, and leaves open
what a single node actually costs in safety. Two settings answer it, and both were already in
`CLAUDE.md` without being put together.

**The storage engine.** FoundationDB in `memory` mode keeps the whole dataset in RAM, so a 4
GB machine caps actor state at a couple of gigabytes. In `ssd` mode the data is a B-tree on
disk and the limit is the volume instead. A small machine then holds far more than the 15
dollar topology needs, and the 4 GB is working memory rather than a ceiling.

**The backups.** A three-node cluster buys redundancy: one node dies and the other two carry
on. `fdbbackup` to the S3-compatible endpoint buys durability instead: the machine dies, and
the data is restored from object storage.

Those are different guarantees and only one of them is worth 314 dollars a month.

| | three nodes | one node, ssd, backed up |
| --- | --- | --- |
| survives a node dying | yes, with no interruption | yes, after a restore |
| survives losing the data | yes | yes |
| downtime when a machine dies | none | minutes |
| cost | 314 dollars a month | included in the venue machine |

For a venue on a 15 dollar ceiling, minutes of downtime after a machine failure is obviously
the right trade, and paying three times the machine bill to avoid it is obviously the wrong
one. So the single-node configuration is `single` redundancy, the `ssd` engine, and
`fdbbackup` streaming to `versitygw`, which is exactly the arrangement CLAUDE.md already
describes for the packaged release.

The three-node cluster is not deleted. It is what a deployment buys when downtime starts
costing more than 314 dollars a month, and that is a threshold rather than an architecture.

## Shared vCPU holds 60 Hz, and the earlier conclusion was wrong

`bench/fly/tick_loop.py`, `shared-cpu-2x` with 2 GB in `sjc`, 60 bodies, 36000 ticks.

| | shared, 60 bodies | dedicated, 301 bodies |
| --- | --- | --- |
| work p50 | 3679 us, 22 percent of tick | 16525 us, 99 percent |
| work p99 | 5171 | 20723 |
| work max | 22918 | 45505 |
| **tick lateness p99** | **283 us** | 236931 |
| **missed ticks** | **1 of 36000** | 13150 |

One missed tick in ten minutes, on the machine class this logbook said could not hold a
deadline. The p99 lateness is 283 microseconds against 237 milliseconds on a dedicated core.

**The 237 milliseconds was load, not tenancy.** The earlier entry attributed it to the
hypervisor taking the core away, and then a cost model was built on the idea that a real-time
deadline requires dedicated cores at eight times the price. The dedicated machine was running
at 99 percent of its tick. This one is running at 22. Nothing about the machine class was
being measured; headroom was.

### The clean comparison, same load, same image, same region

| | shared-cpu-2x | performance-2x |
| --- | --- | --- |
| work p50 | 3679 us | 3594 |
| work p99 | 5171 | 4847 |
| work max | 22918 | 8718 |
| lateness p99 | 283.5 us | 231.6 |
| lateness max | 19435 | 12526 |
| **missed ticks** | **1 of 36000** | **0 of 36000** |

At 22 percent load the two machine classes are **the same machine** for this purpose. The
median differs by 2 percent and the p99 by 7. Dedicated is better only in the tails: the
worst tick is 22.9 milliseconds against 8.7, and the worst late start is 19.4 milliseconds
against 12.5. One tick was missed on shared and none on dedicated, out of thirty-six
thousand.

So dedicated buys a tighter tail and nothing else, and it costs 5.6 times. At a 15 dollar
ceiling that is not a trade worth making. What it might be worth is insurance against
unexpected load, since a shared core has less to give when something spikes, and the worst
tick already runs 2.6 times longer there.

### What it costs if it holds

`shared-cpu-2x` with 2 GB is 14.90 dollars a month against 83.36 for `performance-2x`, which
is 5.6 times. Spread over 139 people a core it moves the machine from 0.000822 dollars for
each person-hour to 0.000147.

It does not move the bill by 5.6 times, because egress does not change. At the lean wire the
total goes from 0.001072 to 0.000397 for each person-hour, so 15 dollars buys 37368
person-hours rather than 13852, and **51 always-on players rather than 19**.

Egress then becomes 63 percent of the cost rather than 23. Once compute is cheap the wire is
the wall, and the next optimisation is bytes rather than cycles.

## Waking a room for real

`proto/fly_rooms.py` wires the `wake` seam in `handoff.py` to `flyctl machine start`. Three
cold starts of a stopped `shared-cpu-1x` in sjc:

    2.64s   2.79s   2.77s

That is the API returning, where the 3.4 seconds budgeted for a wake is the machine reaching
its first tick, measured earlier over three restarts of a `performance-2x`. The two are
consistent and the budget holds with room to spare, which matters because the whole point of
predicting an approach is to have the far side up before anybody arrives.

Both numbers are worth keeping separate. The API return is what a placer can observe. The
first tick is what a player needs. Budget the second and monitor the first.

The machine class here is `shared-cpu-1x`, which is what the 15 dollar tier runs on rather
than the dedicated instance the earlier wake measurement used. Waking is not slower on shared
hardware, which is one more place the shared-versus-dedicated question came out flat.

## Deployed: a room on Fly, a client here, a browser drawing it

`deploy/Dockerfile` and `deploy/fly.toml`. One `shared-cpu-1x` with 1 GB in sjc, running
`proto/plane.py` and nothing else. `auto_stop_machines` is on and `min_machines_running` is
zero, so an empty room bills nothing.

    [plane] 40 bodies simulating, publishing on :8770
    [plane] 80s  1 clients  136 person-to-person contacts  13.84 kB/s each

The client ran on a laptop, connected over WSS to the public internet, and drew the crowd in a
browser from localhost. The datacenter simulates and the player's machine renders, which is
the split the prototype README argues for and this is the first time it crossed a real
network.

### The wire got better with more bodies

13.84 kB a second for 40 bodies at 20 Hz is **17 bytes for a body for a frame**, against 22
measured as an entropy floor and 25 measured locally with 12 bodies.

Below the floor is not a contradiction: the floor was per-body entropy measured
independently, and this is a whole frame compressed together. Forty bodies in one frame share
structure that twelve do not — the same header fields, the same delta shapes, muscles moving
through the same ranges — and zstd finds it across bodies as well as across time.

So the wire improves with crowd size, which is the opposite of the usual direction and worth
knowing before sizing anything from the small measurements in `wire.md`.

### What that does to the numbers

At 17 bytes and the 139 people a core measured earlier, 15 dollars buys about 207 always-on
players rather than 72. That is an extrapolation from two measurements taken separately, and it
should be believed only as far as the smaller of them: the capacity figure came from a driven
avatar with no controller, and a real crowd will differ.

## A plane that falls behind stops accepting players

The deployed room served one client and then refused every reconnection with a handshake
timeout, and the browser reconnected in a loop showing an empty scene. Fly returned 502 while
the machine was plainly running and simulating.

The cause was four lines in the tick loop:

    rest = t0 + i * TICK - time.perf_counter()
    if rest > 0:
        await asyncio.sleep(rest)

`if rest > 0` looks like a harmless guard against sleeping a negative duration. It is a
starvation bug. The moment the simulation overruns its tick, `rest` goes negative, the `await`
never executes, and the loop spins without yielding. Nothing else on the event loop runs, so a
new client's handshake is never served and times out. The plane keeps simulating perfectly and
becomes unreachable.

    await asyncio.sleep(rest if rest > 0 else 0)

That is the fix, plus a clamp that stops trying to catch up once more than ten ticks behind.
Zero restarts afterwards, 136 person-to-person contacts, a stable client.

The property worth stating: **a plane under load must still be able to accept a player.** A
system that stops admitting exactly when it is busiest looks identical to one that has
crashed, and the admission control this design relies on cannot run if admission is the first
thing starvation kills.

It also explains why the first diagnosis was wrong. The frame builder was measured at 0.1
milliseconds and cleared, and it was never the problem: the loop was not slow, it simply never
gave anything else a turn.

## The plane starved its own event loop, and the fix has a proof behind it

The deployed room refused connections intermittently. It looked like the network and it was
not.

    rest = t0 + i * TICK - time.perf_counter()
    if rest > 0:
        await asyncio.sleep(rest)

When the plane falls behind, `rest` goes negative and **nothing awaits**. The loop spins, the
event loop never runs, and an incoming handshake is never serviced. Connections succeeded only
when the plane happened to be keeping up, which is why it worked once and then stopped.

It was falling behind for a separate reason: packet encoding. Building 1040 packets a frame in
Python cost **7956 microseconds against 1169 for the physics itself**. A numpy structured
dtype matching the layout byte for byte does the same work in **88**, ninety times faster,
still passing 64 of 64 golden vectors. The velocity field is populated now too, which it had
never been.

### The loop, rewritten

Godot's shape: an accumulator of real time, spent in whole fixed steps, with a cap on how many
steps one pass may take and the remainder discarded past it. A plane then runs *slower* than
real time under load, visibly, instead of running late forever.

Godot caps at `max_physics_steps_per_frame`, default 8. This does not, because there is a
derived number available. `lean-spatial-oracle/core/Resources.lean`:

    latencyTicksFloor = max (simTickHz / 10) 1
    perNeighborLatencyTicks rtt = max (ceil(rtt*hz/1000) + drainMargin) latencyTicksFloor

That is the lateness the fabric already tolerates: the staging timeout before a migration is
called failed, with a one-tick drain margin proved sufficient. Inside it, being late is
something the rest of the system is built to absorb. Outside it, the ghost bounds and waypoint
periods stop holding, so continuing to chase the debt would simulate a world nothing else
agrees with.

**Six steps at 60 Hz, 100 milliseconds**, and it moves with the tick rate rather than being
pinned to 8.

### Live

40 bodies, 136 person-to-person contacts, one `shared-cpu-1x` in sjc, a client on a laptop and
a browser drawing it. The client reports **1.5 kB a frame, 36 bytes for a body**.

Recordings are in `~/weft-videos` as MKV, AV1 because Fedora ships ffmpeg without x264,
captured losslessly first and encoded second so a slow encoder cannot drop frames of the thing
being recorded. Title burned in, `CITATION.cff` metadata in the container, 30 seconds, with a
9:16 crop for a feed. They are artefacts and not committed, per `CLAUDE.md`.

## The standard plane: native C++, deployed

`src/plane.cpp`, `include/crowd/`, built with CMake against MuJoCo's C API. A plane is a
native process outside the BEAM, and `plane.py` was a stand-in for one.

Local, 40 bodies:

    [plane] 600 ticks in 10.00s (60.0 Hz), 200 frames, 1040 packets each
    [plane] worst step 3038 us, worst encode 22 us, dropped 0 steps

Deployed on a `shared-cpu-1x` in sjc:

    [plane] 30s  60.0 Hz  40 bodies  1040 packets a frame  worst step 6023 us, worst encode 41 us, dropped 0
    [plane] 50s  60.0 Hz  40 bodies  1040 packets a frame  worst step 5319 us, worst encode 25 us, dropped 0

Encoding, which is the part that was pathological in Python:

| | us for a frame of 1040 packets |
| --- | --- |
| Python, packet at a time | 7956 |
| Python, numpy structured dtype | 88 |
| **C++, plain struct** | **22** |

The packet is a `#pragma pack` struct with `static_assert` on every offset, so the layout is
checked at compile time against the Lean spec rather than at test time.

`include/crowd/tick.hpp` holds the loop arithmetic apart from the loop, and `test/tick_test.cpp`
checks it: the cap is `latencyTicks` from the Lean resources spec and not a chosen number, a
long stall is capped instead of becoming thousands of steps, the debt is dropped rather than
chased, and `rest()` is never negative. That last one is the bug that starved the event loop
in the Python plane, now something a test would catch.

The image builds MuJoCo from its own release rather than the Python wheel, so it carries a C
library and no interpreter. `tick_test` runs during the build, so an image cannot be produced
with the tick arithmetic broken.

## The videos were black, and screen capture was the wrong tool

The first recordings were 34 kB of nothing. `x11grab` was grabbing the X root of a Wayland
session, where there is nothing to grab.

`deploy/render.py` renders offscreen through MuJoCo's EGL path instead: no display, no
browser, no compositor. It also needs `<visual><global offwidth=... offheight=.../></visual>`
in the model, because the offscreen framebuffer defaults to 640x480 and is a property of the
model rather than of the renderer.

Recordings are two-pass: lossless FFV1 first, then AV1 with the title burned in and the
`CITATION.cff` metadata in the container. Capture and encode are separate jobs, and a slow
encoder must not drop frames of the thing being recorded. 30 seconds, with a 9:16 cut.
They are artefacts and are not committed.
