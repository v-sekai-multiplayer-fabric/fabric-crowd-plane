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
