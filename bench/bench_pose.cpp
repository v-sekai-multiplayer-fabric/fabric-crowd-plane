// Posing a tracked body, measured.
//
// Six-point tracking reports head, two hands, waist, and two feet. Those six transforms
// determine the pose, so the limbs between them are solved and not simulated. Each limb is
// a two-bone chain with one hinge, and a two-bone chain has a closed form: the law of
// cosines gives the knee or elbow angle, and a swivel angle around the root-to-end axis
// fixes the remaining freedom.
//
// This measures the whole body, for a whole venue, on one core.

#include <cmath>
#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

namespace {

struct V3 {
  float x, y, z;
};

inline V3 operator-(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline V3 operator+(V3 a, V3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline V3 operator*(V3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
inline float dot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline V3 cross(V3 a, V3 b) {
  return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
inline float len(V3 a) { return std::sqrt(dot(a, a)); }
inline V3 norm(V3 a) {
  float l = len(a);
  return l > 1e-6f ? a * (1.0f / l) : V3{0, 0, 1};
}

// One two-bone chain. `root` and `end` are known, the joint between them is solved.
// `swivel` picks where the elbow or knee points, which tracking does not report.
inline V3 solveTwoBone(V3 root, V3 end, float upper, float lower, V3 swivel) {
  V3 axis = end - root;
  float d = len(axis);
  float reach = upper + lower;
  if (d > reach - 1e-4f) d = reach - 1e-4f;
  if (d < 1e-4f) d = 1e-4f;
  axis = norm(axis);

  // Law of cosines: how far along the axis the joint sits, and how far off it.
  float along = (d * d + upper * upper - lower * lower) / (2.0f * d);
  float offSq = upper * upper - along * along;
  float off = offSq > 0.0f ? std::sqrt(offSq) : 0.0f;

  V3 perp = swivel - axis * dot(swivel, axis);
  perp = norm(perp);
  return root + axis * along + perp * off;
}

// One body: the six tracked transforms in, fourteen joint positions out.
struct Tracked {
  V3 head, handL, handR, pelvis, footL, footR;
};

struct Pose {
  V3 joint[14];
};

// Segment lengths, matching `assets/tracked_avatar.xml`.
constexpr float kUpperArm = 0.28f, kLowerArm = 0.26f;
constexpr float kThigh = 0.40f, kShin = 0.39f;

void poseBody(const Tracked& t, Pose& p) {
  // The spine runs from the waist tracker to the head tracker. Nothing between them is
  // reported, so the chest sits on that line at a fixed fraction.
  V3 spine = t.head - t.pelvis;
  V3 chest = t.pelvis + spine * 0.62f;
  V3 up = norm(spine);

  // Facing comes from the line between the hands, made perpendicular to the spine.
  V3 across = norm(t.handL - t.handR);
  V3 fwd = norm(cross(across, up));

  V3 shoulderL = chest + across * 0.19f;
  V3 shoulderR = chest - across * 0.19f;
  V3 hipL = t.pelvis + across * 0.09f;
  V3 hipR = t.pelvis - across * 0.09f;

  // Elbows swivel outward and back, knees forward. This is the one part tracking cannot
  // determine, and a constant is the honest placeholder for it.
  V3 elbowHint = norm(fwd * -1.0f + up * -0.3f);
  V3 kneeHint = fwd;

  p.joint[0] = t.pelvis;
  p.joint[1] = chest;
  p.joint[2] = t.head;
  p.joint[3] = shoulderL;
  p.joint[4] = solveTwoBone(shoulderL, t.handL, kUpperArm, kLowerArm, elbowHint);
  p.joint[5] = t.handL;
  p.joint[6] = shoulderR;
  p.joint[7] = solveTwoBone(shoulderR, t.handR, kUpperArm, kLowerArm, elbowHint);
  p.joint[8] = t.handR;
  p.joint[9] = hipL;
  p.joint[10] = solveTwoBone(hipL, t.footL, kThigh, kShin, kneeHint);
  p.joint[11] = t.footL;
  p.joint[12] = hipR;
  p.joint[13] = solveTwoBone(hipR, t.footR, kThigh, kShin, kneeHint);
}

}  // namespace

int main() {
  const int people = 1000;
  std::vector<Tracked> in(people);
  std::vector<Pose> out(people);

  for (int i = 0; i < people; ++i) {
    float x = static_cast<float>(i % 32) * 0.6f;
    float y = static_cast<float>(i / 32) * 0.6f;
    in[i] = {{x, y, 1.62f},  {x + 0.3f, y + 0.2f, 1.10f}, {x - 0.3f, y + 0.2f, 1.10f},
             {x, y, 0.95f},  {x + 0.1f, y, 0.06f},        {x - 0.1f, y, 0.06f}};
  }

  for (int w = 0; w < 200; ++w)
    for (int i = 0; i < people; ++i) poseBody(in[i], out[i]);

  double best = 1e30;
  for (int run = 0; run < 9; ++run) {
    auto t0 = std::chrono::steady_clock::now();
    const int reps = 200;
    for (int r = 0; r < reps; ++r) {
      // Move every tracker, so nothing is loop-invariant and everyone is walking.
      float phase = static_cast<float>(r) * 0.01f;
      for (int i = 0; i < people; ++i) {
        in[i].handL.z = 1.10f + 0.2f * std::sin(phase + static_cast<float>(i));
        in[i].footL.x += 0.001f;
        poseBody(in[i], out[i]);
      }
    }
    auto t1 = std::chrono::steady_clock::now();
    double us = std::chrono::duration<double, std::micro>(t1 - t0).count() / reps;
    if (us < best) best = us;
  }

  // Keep the result observable so the optimiser cannot drop the work.
  double sink = 0;
  for (int i = 0; i < people; ++i) sink += out[i].joint[10].z;

  std::printf("pose %d bodies: %.1f us/frame, %.3f us/body/frame  (sink %.3f)\n", people,
              best, best / people, sink);
  return 0;
}
