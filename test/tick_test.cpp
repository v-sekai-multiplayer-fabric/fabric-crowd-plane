// The tick arithmetic, checked. The loop it came from starved an event loop and spiralled,
// so the fixes belong somewhere a test can hold them.
#include <cassert>
#include <cstdio>

#include "crowd/tick.hpp"

int main() {
  using crowd::TickClock;

  // The cap comes from the Lean spec, not from a preference: 100 ms at any tick rate.
  assert(crowd::latency_ticks_floor(60) == 6);
  assert(crowd::latency_ticks_floor(30) == 3);
  assert(crowd::latency_ticks_floor(5) == 1);          // never zero
  assert(crowd::per_neighbour_latency_ticks(60, 0) == 6);
  assert(crowd::per_neighbour_latency_ticks(60, 200) == 13);   // ceil(12) + 1 drain

  // Exactly one step for exactly one step of real time.
  TickClock c(60, 0);
  assert(c.advance(1.0 / 60) == 1);

  // Time that does not fill a step is kept, not lost.
  TickClock keep(60, 0);
  assert(keep.advance(1.0 / 120) == 0);
  assert(keep.advance(1.0 / 120) == 1);

  // A long stall is capped rather than turned into thousands of steps, and the debt is
  // dropped rather than chased. This is the spiral of death, and it must not happen.
  TickClock stall(60, 0);
  const int steps = stall.advance(10.0);
  assert(steps == stall.max_steps());
  assert(stall.accumulated() == 0.0);
  assert(stall.dropped_steps() > 0);

  // After saturating, the next pass is normal again.
  assert(stall.advance(1.0 / 60) == 1);

  // rest() is never negative, which is the bug that starved the event loop: a negative rest
  // meant no await at all, so nothing else ever ran.
  TickClock late(60, 0);
  late.advance(0.5);
  assert(late.rest() >= 0.0);

  std::printf("tick: all checks pass\n");
  return 0;
}
