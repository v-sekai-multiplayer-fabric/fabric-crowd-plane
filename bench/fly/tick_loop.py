#!/usr/bin/env python3
# A 60 Hz tick loop, held for a long time, on the machine that will actually run it.
#
# Every earlier number is a microbenchmark: fifteen samples over a few seconds. That measures
# how fast the work is. It does not measure whether a deadline survives a shared-tenancy
# hypervisor for an hour, and a venue misses frames for the second reason long before the
# first.
#
# So this runs the real shape: N bodies stepped once for each tick, a fixed 60 Hz schedule,
# and a count of every tick that did not make it.
import json, os, statistics, time

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TICK_NS = 1_000_000_000 // 60           # 16666666
BODIES = int(os.environ.get("BODIES", "301"))
MINUTES = float(os.environ.get("MINUTES", "10"))


def main():
    m = mujoco.MjModel.from_xml_path(os.path.join(HERE, "tracked_avatar.xml"))
    m.opt.timestep = 1 / 60
    m.opt.iterations = 10
    ds = [mujoco.MjData(m) for _ in range(BODIES)]
    for d in ds:
        for _ in range(30):
            mujoco.mj_step(m, d)

    ticks = int(MINUTES * 60 * 60)
    work = np.zeros(ticks, dtype=np.int64)
    late = np.zeros(ticks, dtype=np.int64)
    misses = 0
    start = time.perf_counter_ns()

    for i in range(ticks):
        target = start + i * TICK_NS
        t0 = time.perf_counter_ns()
        late[i] = t0 - target                      # how late the tick began
        for d in ds:
            mujoco.mj_step(m, d)
        t1 = time.perf_counter_ns()
        work[i] = t1 - t0
        if work[i] > TICK_NS:
            misses += 1
        rest = (start + (i + 1) * TICK_NS) - time.perf_counter_ns()
        if rest > 0:
            time.sleep(rest / 1e9)

    def p(a, q):
        return float(np.percentile(a, q)) / 1000.0

    res = {
        "cpu": next((l.split(":",1)[1].strip() for l in open("/proc/cpuinfo")
                     if l.startswith("model name")), "?"),
        "cores": os.cpu_count(),
        "region": os.environ.get("FLY_REGION"),
        "bodies": BODIES, "minutes": MINUTES, "ticks": ticks,
        "work_p50_us": p(work,50), "work_p90_us": p(work,90),
        "work_p99_us": p(work,99), "work_p999_us": p(work,99.9),
        "work_max_us": float(work.max())/1000.0,
        "late_p99_us": p(late,99), "late_max_us": float(late.max())/1000.0,
        "misses": misses, "miss_rate": misses/ticks,
        "budget_us": TICK_NS/1000.0,
    }
    print(f"host {res['cpu']}  cores {res['cores']}  region {res['region']}")
    print(f"{BODIES} bodies, {ticks} ticks at 60 Hz, budget {TICK_NS/1000:.0f} us\n")
    print(f"  work  p50 {res['work_p50_us']:8.0f} us")
    print(f"        p90 {res['work_p90_us']:8.0f}")
    print(f"        p99 {res['work_p99_us']:8.0f}")
    print(f"      p99.9 {res['work_p999_us']:8.0f}")
    print(f"        max {res['work_max_us']:8.0f}")
    print(f"  start lateness  p99 {res['late_p99_us']:8.0f} us   max {res['late_max_us']:8.0f}")
    print(f"\n  MISSED TICKS {misses} of {ticks}  ({res['miss_rate']*100:.3f}%)")
    print("JSON " + json.dumps(res))


if __name__ == "__main__":
    main()
