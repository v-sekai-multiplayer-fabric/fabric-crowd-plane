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
