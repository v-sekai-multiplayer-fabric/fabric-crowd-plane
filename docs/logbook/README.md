# Crowd plane logbook

Every measurement of the crowd plane, with the conditions it ran under.

A number without its conditions is not a result. The same body costs 258 microseconds
measured alone, 433 measured inside a full plane, and 55 measured in a real loop on the
machine that will actually run it. So each entry names the apparatus, the method, and the
outcome. An entry that turned out to be invalid stays, and it says why.

Inside each file the oldest entry is at the top and a new entry goes at the bottom. This is
the order of a laboratory notebook, so it must not change after the fact.

**A file here stops at about 250 lines.** Past that nobody reads it, and a logbook nobody
reads is a diary. When one fills up, split it by subject rather than by date, because the
question a reader arrives with is always about a subject.

`../../spec/CrowdBudget.lean` holds the budget these feed. It holds the arithmetic and this
holds the measurements. `../../PLAN.md` says what is being built.

## The books

| file | what is in it |
| --- | --- |
| `body.md` | what one simulated body costs, and every lever that failed to make it cheaper |
| `wire.md` | the wire format, from 3600 bytes a body to 21 |
| `platform.md` | Fly: the body measured there, the variance between machines, and a tick loop that missed a third of its frames |
| `crowd.md` | bodies that touch each other, and the stance controller that does not work yet |
| `controller.md` | what the controller must do, its inputs, and the body it drives |
| `training.md` | each training run, the hypothesis it tested, and what came back |
| `corpus.md` | which motion may train a policy weft ships, and what each corpus really holds |
| `inference.md` | what running the policy costs, and how to make it console-fast |

## Open predictions

Both live at the end of `controller.md`, recorded before the result so they can be wrong in
public.

- Sim-to-sim transfer costs 1 to 2 training runs from Newton and 5 to 10 from IsaacLab.
- A 500 iteration steering run finishes in 15 to 20 minutes on the 4090.

## Apparatus

Unless an entry says otherwise:

- **Desk**: Ryzen 7 3800X, 8 cores, Linux. Every entry before "On the platform" ran here.
- **Platform**: Fly `performance-2x`, 2 vCPU, 4 GB, region `sjc`, host reports "AMD EPYC".
- MuJoCo 3.11.0 through the Python bindings. The physics is C; the loop is Python.
- The benches are in `../../bench/`.
