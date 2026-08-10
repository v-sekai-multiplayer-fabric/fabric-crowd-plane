#!/usr/bin/env python3
"""Crossing a machine boundary with no delay and no doorway.

An earlier design put an airlock at the seam, because a stopped room takes 3.4 seconds to wake
and a player must not stand in the dark waiting for it. That was solving the wrong problem.
The wake does not have to be on the critical path.

`lean-fabric-protocol/core/WaypointBound.lean` derives a migration budget from
`maxTravelTicks = ceil(simDiameter / vMaxPhysical)`: an entity cannot move faster than
vMaxPhysical, so there is always a bound on the earliest it can possibly reach a boundary.
That is a prediction, and a prediction is a warning.

So: watch who is approaching, wake the far side while they are still walking, and hand them
over when they arrive. The crossing costs a flush. There is no doorway, because there is
nothing to hide.
"""
import asyncio, math, os, time
from dataclasses import dataclass, field

WAKE_S = float(os.environ.get("WAKE_S", "3.4"))      # measured, stopped machine to first tick
FLUSH_S = float(os.environ.get("FLUSH_S", "0.15"))   # a planned flush, not a crash
SAFETY = float(os.environ.get("SAFETY", "1.5"))      # wake this many times earlier than needed
SCALE = float(os.environ.get("SCALE", "10"))         # run the demo faster than real time
V_MAX_UM_TICK = 500_000                              # lean-entity-packet, PBVH_V_MAX_PHYSICAL
SIM_HZ = 60


@dataclass
class Entity:
    eid: str
    pos: tuple           # metres
    vel: tuple           # metres a second
    room: str


@dataclass
class Boundary:
    """A plane a player can cross into another machine's room."""
    name: str
    axis: int
    at: float
    beyond: str          # the room on the other side


def time_to_cross(e: Entity, b: Boundary):
    """Seconds until this entity reaches the boundary at its current velocity.

    Returns None if it is not heading there. The bound from WaypointBound is the worst case;
    this is the expected case, and the difference is what makes speculative waking affordable.
    """
    gap = b.at - e.pos[b.axis]
    v = e.vel[b.axis]
    if abs(v) < 1e-6 or gap * v <= 0:
        return None
    return gap / v


class Placer:
    """Wakes rooms before they are needed and hands entities over when they arrive.

    `wake` defaults to a sleep for the measured duration. Pass `fly_rooms.wake` to start a
    real stopped machine: three cold starts on shared-cpu-1x came back in 2.64, 2.79 and 2.77
    seconds, against the 3.4 budgeted here, so the budget holds with margin.
    """

    def __init__(self, wake=None, flush=None):
        self.wake = wake or self._sleep_wake
        self.flush = flush or self._sleep_flush
        self.ready = {}          # room -> asyncio.Task, started early
        self.log = []

    async def _sleep_wake(self, room):
        await asyncio.sleep(WAKE_S / SCALE)

    async def _sleep_flush(self, eid):
        await asyncio.sleep(FLUSH_S / SCALE)

    def note(self, t0, what):
        self.log.append((time.perf_counter() - t0, what))

    def observe(self, t0, entities, boundaries):
        """Called every tick. Wakes any room somebody is about to need."""
        horizon = WAKE_S * SAFETY
        for e in entities:
            for b in boundaries:
                tt = time_to_cross(e, b)
                if tt is not None and tt <= horizon and b.beyond not in self.ready:
                    self.ready[b.beyond] = asyncio.create_task(self.wake(b.beyond))
                    self.note(t0, f"{e.eid} is {tt:.1f}s from {b.name}, waking {b.beyond}")

    async def cross(self, t0, e: Entity, b: Boundary):
        """The crossing itself. Whatever the far side still needs, plus a flush."""
        task = self.ready.get(b.beyond)
        if task is None:
            self.note(t0, f"{e.eid} arrived at {b.name} with nothing woken, cold start")
            task = asyncio.create_task(self.wake(b.beyond))
            self.ready[b.beyond] = task
        t = time.perf_counter()
        await asyncio.gather(task, self.flush(e.eid))
        waited = time.perf_counter() - t
        e.room = b.beyond
        self.note(t0, f"{e.eid} crossed into {b.beyond}, waited {waited*1000:.0f} ms")
        return waited


async def main():
    print(f"wake {WAKE_S}s, flush {FLUSH_S}s, horizon {WAKE_S*SAFETY:.1f}s "
          f"(vMax {V_MAX_UM_TICK/1e6*SIM_HZ:.0f} m/s is the hard bound)")
    print(f"times below are simulated seconds; the demo runs {SCALE:.0f}x faster than real")
    print()
    b = Boundary("north wall", axis=1, at=10.0, beyond="room-07")
    for label, speed in (("walking", 1.4), ("running", 3.0)):
        placer = Placer()
        e = Entity("ada", (0.0, 0.0, 0.0), (0.0, speed, 0.0), "room-00")
        t0 = time.perf_counter()
        print(f"{label} at {speed} m/s, {b.at:.0f} m to the boundary "
              f"({b.at/speed:.1f}s away)")
        dt = 1.0 / 60.0                                   # one simulation tick
        while e.pos[1] < b.at:
            placer.observe(t0, [e], [b])
            await asyncio.sleep(dt / SCALE)               # everything runs on the same clock
            e.pos = (e.pos[0], e.pos[1] + speed * dt, e.pos[2])
        waited = await placer.cross(t0, e, b)
        for t, what in placer.log:
            print(f"   {t*SCALE:5.2f}s  {what}")
        print(f"   -> the player waited {waited*SCALE*1000:.0f} ms at the seam\n")


if __name__ == "__main__":
    asyncio.run(main())
