// Generalized Centrifugal Force steering, in two dimensions.
//
// A force-based model, chosen over a velocity-based one because the force family is what
// reproduces pushing in a dense crowd: an arch that forms across a doorway and holds, and
// a flow through the gap that does not follow from how many people want through it.
//
// Each person carries an elliptical space requirement whose long axis grows with speed,
// which is the part that makes a walking crowd behave unlike a standing one.
//
// SPDX-License-Identifier: Apache-2.0
#ifndef CROWD_STEERING_HPP
#define CROWD_STEERING_HPP

#include <cstddef>
#include <vector>

namespace crowd {

struct Agent {
    float x, y;        // metres
    float vx, vy;      // metres each second
    float gx, gy;      // where this person is trying to get to
};

struct SteerParams {
    // From lean-shared-core: vMaxPhysical is 10 m/s. A person walks at about 1.34.
    float desiredSpeed = 1.34f;
    float maxSpeed = 10.0f;

    // The ellipse. The semi-axis along the direction of travel grows with speed, which is
    // what gives a moving crowd more room in front than beside.
    float restRadius = 0.18f;
    float speedStretch = 0.25f;

    float repulsionStrength = 3.0f;
    float wallStrength = 5.0f;
    float relaxTime = 0.5f;
    float cutoff = 2.0f;   // metres; beyond this the force is below noise
};

// A uniform grid over the venue. Linear in the number of agents, which is what makes a
// thousand of them affordable. lean-spatial-oracle has a Hilbert broadphase that would
// also serve, and it drags Mathlib in behind it for a job this size.
class Grid {
  public:
    Grid(float width, float height, float cell);
    void build(const std::vector<Agent>& agents);
    // Calls f(j) for every agent index in the cells touching (x, y).
    template <typename F> void neighbours(float x, float y, F&& f) const;

  private:
    float w_, h_, cell_;
    int nx_, ny_;
    std::vector<int> head_;   // first agent in each cell, or -1
    std::vector<int> next_;   // next agent in the same cell, or -1
    int cellOf(float x, float y) const;
};

// One step for every agent. Returns nothing: it writes velocities and positions in place.
void step(std::vector<Agent>& agents, const Grid& grid, const SteerParams& p, float dt);

}  // namespace crowd

#endif
