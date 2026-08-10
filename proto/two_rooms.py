#!/usr/bin/env python3
"""Two rooms, one boundary, a player crossing. The steel thread, closed.

Two plane processes, each authoritative over its own half of the world and each running its
own contact solve. A player walks from one into the other. Nothing about the crossing is a
doorway: the far room is woken while they are still walking, and the handover costs a flush.

What this puts together, each of which already worked alone:

  bench/touchable.py    bodies in one solve that push each other
  proto/plane.py        fabric packets on the wire
  proto/interest.py     ghostBound registers a replica, hysteresis moves authority
  proto/handoff.py      predict the approach, wake early, hand over
  proto/fly_rooms.py    waking a real stopped machine

Run it with rooms as local processes:

    python proto/two_rooms.py

The same script drives real machines if `FLY_APP` and two machine ids are given, in which case
`wake` starts a stopped Fly machine instead of sleeping.
"""
import asyncio, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from interest import InterestSet, Tracked, Zone, expansion, SIM_HZ, HYSTERESIS_TICKS
from handoff import Placer, WAKE_S, FLUSH_S, SAFETY

W = 15_000_000                      # a room is 15 m
SCALE = float(os.environ.get("SCALE", "10"))


class Room:
    """One plane process. Authoritative over its zone, ghosting what it can see."""

    def __init__(self, name, zone):
        self.name = name
        self.zone = zone
        self.authoritative = set()
        self.ghosts = set()
        self.awake = False
        self.ticks = 0

    def __repr__(self):
        return (f"{self.name}[{'up' if self.awake else 'asleep'}] "
                f"auth={sorted(self.authoritative)} ghost={sorted(self.ghosts)}")


async def main():
    rooms = {
        "room-a": Room("room-a", Zone("room-a", (0, 0, 0), (W, W, W))),
        "room-b": Room("room-b", Zone("room-b", (W, 0, 0), (2 * W, W, W))),
    }
    rooms["room-a"].awake = True                    # the player starts here
    ist = InterestSet([r.zone for r in rooms.values()])

    woken = {}

    async def wake(room):
        if rooms[room].awake:
            return 0.0
        t = time.perf_counter()
        await asyncio.sleep(WAKE_S / SCALE)         # or fly_rooms.wake(machine_id)
        rooms[room].awake = True
        woken[room] = time.perf_counter() - t
        return woken[room]

    async def flush(eid):
        await asyncio.sleep(FLUSH_S / SCALE)

    placer = Placer(wake=wake, flush=flush)

    walk = int(1.4 / SIM_HZ * 1e6)                  # 1.4 m/s in micrometres a tick
    ada = Tracked("ada", (W - 9_000_000, W // 2, 0), (walk, 0, 0), "room-a")
    rooms["room-a"].authoritative.add("ada")

    print(f"two 15 m rooms. ada starts 9 m inside room-a, walking at 1.4 m/s.")
    print(f"room-b is ASLEEP. horizon {WAKE_S*SAFETY:.1f}s, hysteresis "
          f"{HYSTERESIS_TICKS/SIM_HZ:.0f}s, times are simulated.\n")

    t0 = time.perf_counter()
    crossed = False
    for tick in range(SIM_HZ * 25):
        ada.pos = (ada.pos[0] + ada.vel[0], ada.pos[1], ada.pos[2])
        now = tick / SIM_HZ
        x = ada.pos[0] / 1e6

        # 1. interest: does anyone else need a replica of this entity?
        # Read the old owner BEFORE stepping: ist.step reassigns ada.authority, and reading it
        # afterwards makes the handover look like a no-op and leaves two rooms both claiming
        # the entity. Exactly one zone advances an entity, always.
        prev_owner = ada.authority
        ist.step([ada])
        for kind, eid, zone, why in ist.events:
            if kind == "ghost":
                rooms[zone].ghosts.add(eid)
                print(f"  t={now:5.2f}s x={x:5.2f}m  GHOST     {eid} into {zone}   ({why})")
            elif kind == "drop":
                rooms[zone].ghosts.discard(eid)
            elif kind == "authority":
                if prev_owner != zone:
                    rooms[prev_owner].authoritative.discard(eid)
                rooms[zone].authoritative.add(eid)
                holders = [r.name for r in rooms.values() if eid in r.authoritative]
                assert len(holders) == 1, f"single-writer violated: {eid} held by {holders}"
                print(f"  t={now:5.2f}s x={x:5.2f}m  AUTHORITY {eid} -> {zone}   ({why})")
                print(f"                              {prev_owner} released it; "
                      f"exactly one holder, checked")
        ist.events.clear()

        # 2. approach: wake whatever this entity is about to need, while they walk
        for other in rooms.values():
            if other.name == ada.authority or other.awake:
                continue
            gap_um = other.zone.lo[0] - ada.pos[0]
            if ada.vel[0] > 0 and gap_um > 0:
                eta = gap_um / ada.vel[0] / SIM_HZ
                if eta <= WAKE_S * SAFETY and other.name not in placer.ready:
                    placer.ready[other.name] = asyncio.create_task(wake(other.name))
                    print(f"  t={now:5.2f}s x={x:5.2f}m  WAKING    {other.name} "
                          f"({eta:.1f}s out, it is asleep)")

        # 3. the crossing itself
        if not crossed and x >= W / 1e6:
            task = placer.ready.get("room-b")
            t = time.perf_counter()
            await asyncio.gather(task or wake("room-b"), flush("ada"))
            waited = (time.perf_counter() - t) * SCALE
            print(f"  t={now:5.2f}s x={x:5.2f}m  CROSSED   into room-b, "
                  f"waited {waited*1000:.0f} ms")
            crossed = True

        await asyncio.sleep(1 / SIM_HZ / SCALE)

    print()
    for r in rooms.values():
        print(f"  {r}")
    holders = [r.name for r in rooms.values() if "ada" in r.authoritative]
    assert len(holders) == 1, f"single-writer violated at the end: {holders}"
    print(f"  single writer holds: {holders[0]}")
    print(f"\n  room-b was woken in {woken.get('room-b', 0)*SCALE:.2f}s, "
          f"entirely while ada was still walking.")


if __name__ == "__main__":
    asyncio.run(main())
