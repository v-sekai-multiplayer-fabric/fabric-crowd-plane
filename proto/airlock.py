#!/usr/bin/env python3
"""The doorway: the seam where the machine running you changes.

Not a way to make a venue bigger. A room stops when it is empty, because that is what makes
the price, and a room that stops is a room players are moved into and out of. The doorway is
what turns a 3.4 second machine wake into a walk.

A crossing is planned, so it is not a crash: the actor flushes and then hands off, and the
lazy replica underneath is not what carries it. That distinction is the whole reason this is
cheap. See docs/logbook/crowd.md.

    the transit                what happens
    -----------                ------------
    enter, doors close         the player stops being simulated by this room
    while inside               the destination is chosen and woken, state is flushed
    far door opens             the player is admitted there and simulation resumes

The far side is late-bound: the destination is decided while the batch is inside, so a room
needs one doorway rather than one for each place it connects to.
"""
import asyncio, json, os, time
from dataclasses import dataclass, field
from enum import Enum

WAKE_S = float(os.environ.get("WAKE_S", "3.4"))     # measured: stopped machine to first tick
FLUSH_S = float(os.environ.get("FLUSH_S", "0.15"))  # a planned flush, not a crash
MIN_TRANSIT_S = float(os.environ.get("TRANSIT_S", "5.0"))


class Phase(Enum):
    OPEN = "open"                # players may enter
    SEALED = "sealed"            # both doors shut, destination being prepared
    ARRIVING = "arriving"        # far door opening


@dataclass
class Crossing:
    players: list
    origin: str
    destination: str = ""
    phase: Phase = Phase.OPEN
    t0: float = field(default_factory=time.perf_counter)
    log: list = field(default_factory=list)

    def note(self, what):
        self.log.append((time.perf_counter() - self.t0, what))


class Airlock:
    """One doorway. It holds a batch, wakes the far side, and hands the batch over."""

    def __init__(self, room_id, capacity=60, place=None, wake=None, flush=None):
        self.room_id = room_id
        self.capacity = capacity
        self.place = place or self._default_place
        self.wake = wake or self._default_wake
        self.flush = flush or self._default_flush
        self.current = None

    async def _default_place(self, players):
        """The control plane decides where they go. Late-bound, hence infinite travel."""
        return f"room-{abs(hash(tuple(players))) % 97:02d}"

    async def _default_wake(self, room):
        await asyncio.sleep(WAKE_S)

    async def _default_flush(self, players):
        await asyncio.sleep(FLUSH_S)

    def enter(self, player):
        if self.current is None or self.current.phase is not Phase.OPEN:
            self.current = Crossing(players=[], origin=self.room_id)
        if len(self.current.players) >= self.capacity:
            return False
        self.current.players.append(player)
        self.current.note(f"{player} entered")
        return True

    async def cycle(self):
        """Seal, prepare the far side, hand over. Returns the finished crossing."""
        c = self.current
        if c is None or not c.players:
            return None
        c.phase = Phase.SEALED
        c.note(f"sealed with {len(c.players)}")

        # The destination is chosen now, not when the doorway was built.
        c.destination = await self.place(c.players)
        c.note(f"bound to {c.destination}")

        # Wake the far side and flush the state at the same time. Neither waits for the other.
        t = time.perf_counter()
        await asyncio.gather(self.wake(c.destination), self.flush(c.players))
        c.note(f"far side ready and state flushed in {time.perf_counter()-t:.2f}s")

        # A transit that finishes before the walk does would show the seam.
        left = MIN_TRANSIT_S - (time.perf_counter() - c.t0)
        if left > 0:
            await asyncio.sleep(left)
            c.note(f"held {left:.2f}s so the walk covers the wake")

        c.phase = Phase.ARRIVING
        c.note(f"{len(c.players)} admitted to {c.destination}")
        self.current = None
        return c


async def main():
    lock = Airlock("room-00", capacity=60)
    for p in ("ada", "grace", "alan"):
        lock.enter(p)
    print(f"transit floor: wake {WAKE_S}s, flush {FLUSH_S}s, walk {MIN_TRANSIT_S}s")
    c = await lock.cycle()
    print(f"\n{c.origin} -> {c.destination}, {len(c.players)} players")
    for t, what in c.log:
        print(f"  {t:5.2f}s  {what}")
    print(f"\ntotal {time.perf_counter()-c.t0:.2f}s, and the seam is hidden by the walk")


if __name__ == "__main__":
    asyncio.run(main())
