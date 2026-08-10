#!/usr/bin/env python3
"""Waking a real room on a real machine.

`handoff.py` predicts who is approaching a boundary and wakes the far side while they walk.
Its `wake` was a sleep for the measured 3.4 seconds. This is the same seam wired to Fly.

A room is a stopped machine. Waking it is `flyctl machine start`, which was measured at 3.2
to 3.6 seconds to the first tick over three restarts. Stopping it is what makes the price:
an empty room bills nothing.

    python proto/fly_rooms.py list
    python proto/fly_rooms.py wake  <machine-id>
    python proto/fly_rooms.py sleep <machine-id>
    python proto/fly_rooms.py time  <machine-id>    # wake it and time it, then stop it
"""
import asyncio, json, os, subprocess, sys, time

APP = os.environ.get("FLY_APP", "weft-crowd-bench")


async def _fly(*args):
    p = await asyncio.create_subprocess_exec(
        "flyctl", *args, "--app", APP,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await p.communicate()
    return p.returncode, out.decode(), err.decode()


async def rooms():
    rc, out, err = await _fly("machine", "list", "--json")
    if rc != 0:
        raise RuntimeError(err.strip())
    return [{"id": m["id"], "name": m.get("name", ""), "state": m["state"],
             "region": m.get("region", ""),
             "size": (m.get("config", {}).get("guest", {}) or {}).get("cpu_kind", "")}
            for m in json.loads(out or "[]")]


async def wake(machine_id):
    """Start a stopped room. This is what runs while a player is still walking."""
    t0 = time.perf_counter()
    rc, out, err = await _fly("machine", "start", machine_id)
    if rc != 0:
        raise RuntimeError(err.strip())
    return time.perf_counter() - t0


async def sleep_room(machine_id):
    """Stop a room. An empty room costs nothing, which is the whole economic argument."""
    rc, out, err = await _fly("machine", "stop", machine_id)
    if rc != 0:
        raise RuntimeError(err.strip())


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for r in await rooms():
            print(f"  {r['id']:16} {r['name']:14} {r['state']:9} {r['region']:5} {r['size']}")
        return
    mid = sys.argv[2]
    if cmd == "wake":
        print(f"woke {mid} in {await wake(mid):.2f}s")
    elif cmd == "sleep":
        await sleep_room(mid); print(f"stopped {mid}")
    elif cmd == "time":
        rs = {r["id"]: r for r in await rooms()}
        if rs.get(mid, {}).get("state") != "stopped":
            print("stopping it first so the measurement is a cold wake")
            await sleep_room(mid)
            for _ in range(30):
                await asyncio.sleep(1)
                if (await rooms()) and [r for r in await rooms() if r["id"] == mid][0]["state"] == "stopped":
                    break
        dt = await wake(mid)
        print(f"wake {mid}: {dt:.2f}s to the API returning")
        await sleep_room(mid)
        print("stopped again, so it bills nothing")


if __name__ == "__main__":
    asyncio.run(main())
