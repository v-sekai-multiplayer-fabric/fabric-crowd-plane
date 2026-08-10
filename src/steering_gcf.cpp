// SPDX-License-Identifier: Apache-2.0
#include "crowd/steering.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>

namespace crowd {

Grid::Grid(float width, float height, float cell)
    : w_(width), h_(height), cell_(cell),
      nx_(std::max(1, int(width / cell))), ny_(std::max(1, int(height / cell))),
      head_(size_t(nx_) * size_t(ny_), -1) {}

int Grid::cellOf(float x, float y) const {
    int cx = std::clamp(int(x / cell_), 0, nx_ - 1);
    int cy = std::clamp(int(y / cell_), 0, ny_ - 1);
    return cy * nx_ + cx;
}

void Grid::build(const std::vector<Agent>& agents) {
    std::fill(head_.begin(), head_.end(), -1);
    next_.assign(agents.size(), -1);
    // Backwards, so each cell's list comes out in ascending index order. It costs nothing
    // and it makes the neighbour walk read memory forwards.
    for (int i = int(agents.size()) - 1; i >= 0; --i) {
        int c = cellOf(agents[size_t(i)].x, agents[size_t(i)].y);
        next_[size_t(i)] = head_[size_t(c)];
        head_[size_t(c)] = i;
    }
}

template <typename F>
void Grid::neighbours(float x, float y, F&& f) const {
    int cx = std::clamp(int(x / cell_), 0, nx_ - 1);
    int cy = std::clamp(int(y / cell_), 0, ny_ - 1);
    for (int dy = -1; dy <= 1; ++dy) {
        int yy = cy + dy;
        if (yy < 0 || yy >= ny_) continue;
        for (int dx = -1; dx <= 1; ++dx) {
            int xx = cx + dx;
            if (xx < 0 || xx >= nx_) continue;
            for (int j = head_[size_t(yy * nx_ + xx)]; j != -1; j = next_[size_t(j)]) f(j);
        }
    }
}

void step(std::vector<Agent>& agents, const Grid& grid, const SteerParams& p, float dt) {
    const size_t n = agents.size();
    const float cut2 = p.cutoff * p.cutoff;

    for (size_t i = 0; i < n; ++i) {
        Agent& a = agents[i];

        // The driving term: relax towards the desired velocity, which points at the goal.
        float dgx = a.gx - a.x, dgy = a.gy - a.y;
        float dg = std::sqrt(dgx * dgx + dgy * dgy);
        float fx = 0.0f, fy = 0.0f;
        if (dg > 1e-4f) {
            fx = (p.desiredSpeed * dgx / dg - a.vx) / p.relaxTime;
            fy = (p.desiredSpeed * dgy / dg - a.vy) / p.relaxTime;
        }

        // The space this person needs, longer along the direction of travel.
        float sp = std::sqrt(a.vx * a.vx + a.vy * a.vy);
        float ra = p.restRadius + p.speedStretch * sp;

        grid.neighbours(a.x, a.y, [&](int j) {
            if (size_t(j) == i) return;
            const Agent& b = agents[size_t(j)];
            float dx = a.x - b.x, dy = a.y - b.y;
            float d2 = dx * dx + dy * dy;
            if (d2 > cut2 || d2 < 1e-8f) return;

            float d = std::sqrt(d2);
            float spb = std::sqrt(b.vx * b.vx + b.vy * b.vy);
            float rb = p.restRadius + p.speedStretch * spb;

            // Only the closing part of the relative velocity matters. Someone walking away
            // is not in the way, and treating them as if they were makes a crowd jitter.
            float rvx = a.vx - b.vx, rvy = a.vy - b.vy;
            float closing = -(rvx * dx + rvy * dy) / d;
            float ev = 0.5f * (closing + std::fabs(closing));

            float gap = d - ra - rb;
            if (gap < 1e-3f) gap = 1e-3f;
            float mag = p.repulsionStrength * (ev * ev + p.desiredSpeed) / (gap * gap);
            fx += mag * dx / d;
            fy += mag * dy / d;
        });

        a.vx += fx * dt;
        a.vy += fy * dt;

        float s = std::sqrt(a.vx * a.vx + a.vy * a.vy);
        if (s > p.maxSpeed) {
            a.vx *= p.maxSpeed / s;
            a.vy *= p.maxSpeed / s;
        }
        a.x += a.vx * dt;
        a.y += a.vy * dt;
    }
}

}  // namespace crowd
