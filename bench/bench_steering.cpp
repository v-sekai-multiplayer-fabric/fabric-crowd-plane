// What steering costs for a thousand people, which is the last assumed number in the
// budget. SPDX-License-Identifier: Apache-2.0
#include "crowd/steering.hpp"
#include <chrono>
#include <cstdio>
#include <random>
#include <cstdlib>
#include <vector>
#include <algorithm>
using namespace crowd;
int main(int argc, char** argv) {
    const int n = argc > 1 ? std::atoi(argv[1]) : 1000;
    const float side = 20.0f;
    std::mt19937 rng(1); std::uniform_real_distribution<float> u(0.5f, side - 0.5f);
    std::vector<Agent> a; a.resize(size_t(n));
    for (auto& x : a) x = {u(rng), u(rng), 0, 0, side * 0.5f, side};   // all head for the door
    Grid g(side, side, 2.0f);
    const float dt = 1.0f / 60.0f;
    for (int i = 0; i < 60; ++i) { g.build(a); step(a, g, {}, dt); }
    std::vector<double> runs;
    for (int r = 0; r < 7; ++r) {
        auto t0 = std::chrono::steady_clock::now();
        for (int i = 0; i < 100; ++i) { g.build(a); step(a, g, {}, dt); }
        auto t1 = std::chrono::steady_clock::now();
        runs.push_back(std::chrono::duration<double, std::micro>(t1 - t0).count() / 100.0);
    }
    std::sort(runs.begin(), runs.end());
    std::printf("%5d agents: %8.1f us/frame  (%.3f us each)\n", n, runs[3], runs[3] / n);
    return 0;
}
