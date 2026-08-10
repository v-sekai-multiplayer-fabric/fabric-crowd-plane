#!/usr/bin/env python3
# The numbers the budget rests on, re-measured on whatever host this runs on.
#
# Every figure in spec/CrowdBudget.lean was measured on one developer machine. The plane is
# sized from the body cost at the ninetieth percentile, so that one number decides whether
# three vCPU hold a thousand people. This re-measures it, and prints the same shape of table,
# so a run here and a run there can be put side by side.
import json, os, platform, statistics, subprocess, time

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "tracked_avatar.xml")
TICK_NS = 16666 * 1000
CONTACT_NS, PUBLISH_NS, STEER_NS = 2433, 45, 280


def cpu_model():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def body_cost():
    m = mujoco.MjModel.from_xml_path(XML)
    m.opt.timestep = 1 / 60
    m.opt.iterations = 10
    out = {}
    for n in (14, 28, 56):
        ds = [mujoco.MjData(m) for _ in range(n)]
        for d in ds:
            for _ in range(60):
                mujoco.mj_step(m, d)
        runs = []
        for _ in range(15):
            t0 = time.perf_counter_ns()
            for _ in range(20):
                for d in ds:
                    mujoco.mj_step(m, d)
            runs.append((time.perf_counter_ns() - t0) / 20 / n / 1000.0)
        out[n] = (statistics.median(runs), float(np.percentile(runs, 90)))
    return out


def people_on(body_us, cores):
    per = PUBLISH_NS + STEER_NS + int(body_us * 1000)
    return TICK_NS // (CONTACT_NS + per // cores)


def main():
    print(f"host   {cpu_model()}")
    print(f"cores  {os.cpu_count()}   fly_region={os.environ.get('FLY_REGION','-')} "
          f"machine={os.environ.get('FLY_MACHINE_ID','-')}")
    print()
    cost = body_cost()
    print(f"{'batch':>6} {'median us':>10} {'p90 us':>8}")
    for n, (med, p90) in cost.items():
        print(f"{n:>6} {med:>10.2f} {p90:>8.2f}")

    worst_med = max(v[0] for v in cost.values())
    worst_p90 = max(v[1] for v in cost.values())
    print()
    print(f"{'cores':>6} {'people at median':>17} {'people at p90':>14}")
    for c in (1, 2, 3, 4):
        print(f"{c:>6} {people_on(worst_med, c):>17} {people_on(worst_p90, c):>14}")
    print()
    ok = people_on(worst_p90, 3) >= 1000
    print(f"three vCPU hold a thousand at the tail: {'YES' if ok else 'NO'}")
    print("JSON " + json.dumps({
        "cpu": cpu_model(), "cores": os.cpu_count(),
        "region": os.environ.get("FLY_REGION"),
        "median_us": worst_med, "p90_us": worst_p90,
        "people_3core_p90": people_on(worst_p90, 3),
    }))


if __name__ == "__main__":
    main()
