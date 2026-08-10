#!/usr/bin/env python3
# A room: starts, holds 60 Hz while anybody is in it, and stops itself when empty.
#
# The room is the unit of cost, failure, and placement. It is a whole Fly machine, and a
# machine that is stopped bills nothing, so an empty room is free. What that costs is the
# time it takes to wake one, and an airlock has to be at least that long.
import json, os, sys, time

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TICK_NS = 1_000_000_000 // 60
OCCUPANTS = int(os.environ.get("OCCUPANTS", "60"))
EMPTY_AFTER_S = float(os.environ.get("EMPTY_AFTER_S", "20"))
BOOT_NS = time.perf_counter_ns()


def main():
    # Time to first tick is what an airlock has to hide.
    m = mujoco.MjModel.from_xml_path(os.path.join(HERE, "tracked_avatar.xml"))
    m.opt.timestep = 1 / 60
    m.opt.iterations = 10
    ds = [mujoco.MjData(m) for _ in range(OCCUPANTS)]
    for d in ds:
        for _ in range(20):
            mujoco.mj_step(m, d)
    ready_ms = (time.perf_counter_ns() - BOOT_NS) / 1e6
    print(f"ROOM READY  occupants={OCCUPANTS}  warmup_ms={ready_ms:.0f} "
          f"region={os.environ.get('FLY_REGION','-')} machine={os.environ.get('FLY_MACHINE_ID','-')}",
          flush=True)

    # Hold the tick, and watch the load ratio rather than a capacity constant.
    deadline = time.time() + EMPTY_AFTER_S
    start = time.perf_counter_ns()
    i = 0
    work = []
    while time.time() < deadline:
        t0 = time.perf_counter_ns()
        for d in ds:
            mujoco.mj_step(m, d)
        w = time.perf_counter_ns() - t0
        work.append(w)
        i += 1
        rest = (start + (i + 1) * TICK_NS) - time.perf_counter_ns()
        if rest > 0:
            time.sleep(rest / 1e9)

    w = np.array(work)
    load_p99 = float(np.percentile(w, 99)) / TICK_NS
    res = {
        "region": os.environ.get("FLY_REGION"), "machine": os.environ.get("FLY_MACHINE_ID"),
        "occupants": OCCUPANTS, "warmup_ms": ready_ms, "ticks": i,
        "load_p50": float(np.median(w)) / TICK_NS, "load_p99": load_p99,
        "misses": int((w > TICK_NS).sum()),
    }
    print(f"ROOM EMPTY, STOPPING  ticks={i}  load_p50={res['load_p50']:.2f} "
          f"load_p99={load_p99:.2f}  misses={res['misses']}", flush=True)
    print("JSON " + json.dumps(res), flush=True)
    # Exit is the shutdown. The platform bills nothing for a stopped machine.
    sys.exit(0)


if __name__ == "__main__":
    main()
