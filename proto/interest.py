#!/usr/bin/env python3
"""Who sees whom, from the org spec rather than from a guess.

`lean-interest-mgmt/core/AuthorityInterest.lean` separates two things this prototype had been
running together:

  authority   the zone that advances an entity's physics. Exactly one, always.
  interest    a read-only ghost held by a neighbouring zone. Many, and cheap.

The registration rule is not a radius. An entity enters a zone's interest when its **k-tick
kinematic expansion** overlaps that zone's volume, where the expansion is the proved formula
from `lean-spatial-oracle/core/Formula.lean`:

    ghostBound v a_half k = v*k + a_half*k*k

That is the same predictive bound that took the machine wake off the critical path in
`handoff.py`, applied to visibility instead of to migration. A ghost is registered early
enough that it is already there when it is needed.

Two consequences the spec states and this implements:

  * ghosts do not consume authority slots, so a zone holds hundreds of border entities while
    keeping its migration headroom free. That matches the measurement in the logbook: an
    interest replica is about a hundredth of an authoritative body.
  * authority transfers only after `hysteresisThreshold` ticks of continuous presence, which
    is separate from interest registration. An entity that brushes a boundary is ghosted at
    once and never migrates.
"""
import os
from dataclasses import dataclass, field

SIM_HZ = int(os.environ.get("SIM_HZ", "60"))
HYSTERESIS_TICKS = SIM_HZ * 4          # Types.lean: simTickHz * 4
GHOST_TICKS = int(os.environ.get("GHOST_TICKS", "30"))   # k, the expansion horizon
V_MAX_UM_TICK = 500_000                # lean-entity-packet


def expansion(v_um_tick, a_half_um_tick2, k):
    """ghostBound: how far an entity can travel in k ticks. Micrometres.

    Monotone in v, a and k, which is what makes it safe to use as a bound: a ghost registered
    on this number is registered no later than one registered on the truth.
    """
    return v_um_tick * k + a_half_um_tick2 * k * k


@dataclass
class Zone:
    """One server process owning a spatial partition."""
    name: str
    lo: tuple            # micrometres
    hi: tuple

    def overlaps(self, centre, radius):
        return all(centre[i] + radius >= self.lo[i] and centre[i] - radius <= self.hi[i]
                   for i in range(3))

    def contains(self, p):
        return all(self.lo[i] <= p[i] <= self.hi[i] for i in range(3))


@dataclass
class Tracked:
    eid: str
    pos: tuple           # micrometres
    vel: tuple           # micrometres a tick
    authority: str
    inside_since: dict = field(default_factory=dict)   # zone -> ticks of continuous presence


class InterestSet:
    """Registers ghosts, and separately decides when authority moves."""

    def __init__(self, zones, ghost_ticks=GHOST_TICKS, hysteresis=HYSTERESIS_TICKS):
        self.zones = {z.name: z for z in zones}
        self.k = ghost_ticks
        self.hysteresis = hysteresis
        self.ghosts = {z.name: set() for z in zones}
        self.events = []

    def speed(self, e):
        return int(max(abs(v) for v in e.vel))

    def step(self, entities):
        """One tick. Register ghosts by kinematic expansion, migrate by hysteresis."""
        for e in entities:
            reach = expansion(self.speed(e), 0, self.k)
            for name, z in self.zones.items():
                if name == e.authority:
                    continue
                if z.overlaps(e.pos, reach):
                    if e.eid not in self.ghosts[name]:
                        self.ghosts[name].add(e.eid)
                        self.events.append(("ghost", e.eid, name,
                                            f"reach {reach/1e6:.1f} m overlaps {name}"))
                elif e.eid in self.ghosts[name]:
                    self.ghosts[name].discard(e.eid)
                    self.events.append(("drop", e.eid, name, "no longer reachable"))

                # Authority is a different question, and a slower one.
                if z.contains(e.pos):
                    e.inside_since[name] = e.inside_since.get(name, 0) + 1
                    if e.inside_since[name] >= self.hysteresis:
                        self.events.append(("authority", e.eid, name,
                                            f"{self.hysteresis} ticks inside"))
                        e.authority = name
                        e.inside_since.clear()
                else:
                    e.inside_since[name] = 0

    def load(self):
        """What each zone is carrying. Authority is the expensive column."""
        return {n: len(g) for n, g in self.ghosts.items()}


def main():
    W = 15_000_000            # a 15 m zone
    zones = [Zone("zone-a", (0, 0, 0), (W, W, W)),
             Zone("zone-b", (W, 0, 0), (2 * W, W, W))]
    ist = InterestSet(zones)

    walk = int(1.4 / SIM_HZ * 1e6)      # 1.4 m/s in micrometres a tick
    e = Tracked("ada", (W - 8_000_000, W // 2, 0), (walk, 0, 0), "zone-a")

    print(f"two 15 m zones, k = {ist.k} ticks, hysteresis = {ist.hysteresis} ticks")
    print(f"ada walks at 1.4 m/s from 8 m inside zone-a toward the border")
    print(f"  ghostBound at that speed over {ist.k} ticks = "
          f"{expansion(walk, 0, ist.k)/1e6:.2f} m")
    print(f"  the same at vMaxPhysical            = "
          f"{expansion(V_MAX_UM_TICK, 0, ist.k)/1e6:.1f} m  (the hard bound)")
    print()
    for tick in range(SIM_HZ * 12):
        e.pos = (e.pos[0] + e.vel[0], e.pos[1], e.pos[2])
        ist.step([e])
        while ist.events:
            kind, eid, zone, why = ist.events.pop(0)
            x = e.pos[0] / 1e6
            print(f"  t={tick/SIM_HZ:5.2f}s  x={x:5.2f}m  {kind.upper():9} {eid} -> {zone}   ({why})")


if __name__ == "__main__":
    main()
