#pragma once
// The tick loop's arithmetic, kept apart from the loop so it can be tested.
//
// A fixed-timestep accumulator: real time goes in, whole steps come out, and the number of
// steps one pass may take is capped. Past the cap the remaining time is dropped rather than
// chased, so a plane under load runs visibly slower than real time instead of falling further
// behind on every pass.
//
// The cap is not a chosen number. `lean-spatial-oracle/core/Resources.lean` derives
//
//     latencyTicksFloor = max (simTickHz / 10) 1
//     perNeighborLatencyTicks rtt = max (ceil(rtt*hz/1000) + drainMargin) latencyTicksFloor
//
// which is the lateness a migration is allowed before it is called failed, with a one-tick
// drain margin proved sufficient. Inside it the rest of the fabric absorbs the delay. Outside
// it the ghost bounds and waypoint periods stop holding, so continuing would simulate a world
// nothing else agrees with.

#include <algorithm>
#include <cstdint>

namespace crowd {

constexpr int latency_ticks_floor(int sim_tick_hz) {
  return std::max(sim_tick_hz / 10, 1);
}

constexpr int per_neighbour_latency_ticks(int sim_tick_hz, int rtt_ms) {
  const int drain_margin = 1;   // proved: a queue drains in one tick
  const int rtt_ticks = (rtt_ms * sim_tick_hz + 999) / 1000;
  return std::max(rtt_ticks + drain_margin, latency_ticks_floor(sim_tick_hz));
}

class TickClock {
 public:
  TickClock(int sim_tick_hz, int rtt_ms)
      : step_(1.0 / sim_tick_hz),
        max_steps_(per_neighbour_latency_ticks(sim_tick_hz, rtt_ms)) {}

  double step() const { return step_; }
  int max_steps() const { return max_steps_; }
  double accumulated() const { return accum_; }
  std::uint64_t dropped_steps() const { return dropped_; }

  // Take real elapsed time, return how many fixed steps to run now.
  int advance(double elapsed) {
    accum_ += std::min(elapsed, step_ * max_steps_);
    int steps = 0;
    while (accum_ >= step_ && steps < max_steps_) {
      accum_ -= step_;
      ++steps;
    }
    if (steps == max_steps_ && accum_ >= step_) {
      dropped_ += static_cast<std::uint64_t>(accum_ / step_);
      accum_ = 0.0;                 // saturated: drop the debt rather than chase it
    }
    return steps;
  }

  // How long to sleep before the next pass.
  double rest() const { return std::max(0.0, step_ - accum_); }

 private:
  double step_;
  int max_steps_;
  double accum_ = 0.0;
  std::uint64_t dropped_ = 0;
};

}  // namespace crowd
