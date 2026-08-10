// The crowd plane. A native process, C++, outside the BEAM.
//
// Every avatar is in one MuJoCo model, so contact between people is solved once and everybody
// agrees on it. That is the product: bodies that push each other.
//
// This process renders nothing and terminates no transport. It simulates, it encodes fabric
// entity packets, and it hands them to whatever is listening. An edge is a separate process
// with networking; a plane has none. See CLAUDE.md.
//
//   weft-crowd-plane [model.xml] [bodies]
//
// Environment:
//   CROWD_BODIES   how many avatars           (default 40)
//   CROWD_SPACING  metres between them        (default 0.9)
//   CROWD_HZ       simulation rate            (default 60)
//   CROWD_RTT_MS   round trip to a neighbour, which sets the step cap (default 0)
//   CROWD_SECONDS  run for this long, 0 for forever (default 10)

#include <mujoco/mujoco.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include "crowd/packet.hpp"
#include "crowd/tick.hpp"

namespace {

// One 16.7 ms step for one 16.7 ms frame. Two steps of a 16.7 ms model advance the world
// at twice real time, which is what stepping twice here did.
constexpr int kSubsteps = 1;

double env_double(const char* name, double fallback) {
  const char* v = std::getenv(name);
  return v ? std::atof(v) : fallback;
}

int env_int(const char* name, int fallback) {
  const char* v = std::getenv(name);
  return v ? std::atoi(v) : fallback;
}

// Build a venue by repeating one avatar on a grid. Each copy needs unique names, so the
// model is assembled as text and compiled once.
std::string venue_xml(const std::string& avatar_path, int n, double spacing) {
  FILE* f = std::fopen(avatar_path.c_str(), "rb");
  if (!f) {
    std::fprintf(stderr, "cannot open %s\n", avatar_path.c_str());
    return {};
  }
  std::string src;
  char buf[8192];
  std::size_t got;
  while ((got = std::fread(buf, 1, sizeof(buf), f)) > 0) src.append(buf, got);
  std::fclose(f);

  const std::size_t b0 = src.find("<body name=\"pelvis\"");
  const std::size_t b1 = src.find("</worldbody>");
  const std::size_t a0 = src.find("<actuator>") + std::strlen("<actuator>");
  const std::size_t a1 = src.find("</actuator>");
  if (b0 == std::string::npos || b1 == std::string::npos) return {};
  const std::string body = src.substr(b0, b1 - b0);
  const std::string act = src.substr(a0, a1 - a0);

  auto suffix = [](std::string s, int i) {
    // Append _i to every name= and joint= value so the copies do not collide.
    for (const char* key : {"name=\"", "joint=\""}) {
      std::size_t p = 0;
      const std::size_t klen = std::strlen(key);
      while ((p = s.find(key, p)) != std::string::npos) {
        const std::size_t start = p + klen;
        const std::size_t end = s.find('"', start);
        if (end == std::string::npos) break;
        const std::string ins = "_" + std::to_string(i);
        s.insert(end, ins);
        p = end + ins.size() + 1;
      }
    }
    return s;
  };

  const int side = static_cast<int>(std::ceil(std::sqrt(static_cast<double>(n))));
  std::string bodies, acts;
  for (int i = 0; i < n; ++i) {
    std::string b = suffix(body, i);
    char pos[128];
    std::snprintf(pos, sizeof(pos), "pos=\"%.3f %.3f 0.95\"",
                  (i % side) * spacing, (i / side) * spacing);
    const std::size_t at = b.find("pos=\"0 0 0.95\"");
    if (at != std::string::npos) b.replace(at, std::strlen("pos=\"0 0 0.95\""), pos);
    bodies += b;
    acts += suffix(act, i);
  }

  return "<mujoco model=\"venue\"><compiler angle=\"radian\"/>"
         "<option timestep=\"0.016666\" solver=\"Newton\" iterations=\"10\">"
         "<flag island=\"enable\"/></option>"
         "<default><geom type=\"capsule\" condim=\"3\" friction=\"0.9 0.005 0.0001\" "
         "density=\"985\"/><joint type=\"hinge\" damping=\"2\" armature=\"0.02\"/>"
         "<motor ctrlrange=\"-300 300\"/></default>"
         "<worldbody><geom name=\"floor\" type=\"plane\" size=\"200 200 0.1\" density=\"0\"/>" +
         bodies + "</worldbody><actuator>" + acts + "</actuator></mujoco>";
}

}  // namespace

int main(int argc, char** argv) {
  const std::string model_path =
      argc > 1 ? argv[1] : "assets/tracked_avatar.xml";
  const int n = argc > 2 ? std::atoi(argv[2]) : env_int("CROWD_BODIES", 40);
  const double spacing = env_double("CROWD_SPACING", 0.9);
  const int hz = env_int("CROWD_HZ", 60);
  const int rtt_ms = env_int("CROWD_RTT_MS", 0);
  const double seconds = env_double("CROWD_SECONDS", 10.0);

  const std::string xml = venue_xml(model_path, n, spacing);
  if (xml.empty()) return 1;

  char err[1024] = {0};
  mjModel* m = mj_loadXML(nullptr, nullptr, err, sizeof(err));
  if (!m) {
    // Compile from the string we built rather than a file on disk.
    mjVFS vfs;
    mj_defaultVFS(&vfs);
    mj_addBufferVFS(&vfs, "venue.xml", xml.data(), static_cast<int>(xml.size()));
    m = mj_loadXML("venue.xml", &vfs, err, sizeof(err));
    mj_deleteVFS(&vfs);
  }
  if (!m) {
    std::fprintf(stderr, "model did not compile: %s\n", err);
    return 1;
  }
  mjData* d = mj_makeData(m);

  const int nq_each = m->nq / n;
  const int nv_each = m->nv / n;
  const int nu_each = m->nu / n;

  std::vector<double> jlo(nu_each), jhi(nu_each);
  for (int j = 0; j < nu_each; ++j) {
    jlo[j] = m->jnt_range[2 * (1 + j)];
    jhi[j] = m->jnt_range[2 * (1 + j) + 1];
  }

  std::vector<crowd::Packet> frame(static_cast<std::size_t>(n) * nu_each);
  std::memset(frame.data(), 0, frame.size() * sizeof(crowd::Packet));

  crowd::TickClock clock(hz, rtt_ms);
  std::printf("[plane] %d bodies, %d muscles each, %d Hz, at most %d steps a pass "
              "(latencyTicks, %.0f ms)\n",
              n, nu_each, hz, clock.max_steps(), clock.max_steps() * clock.step() * 1000.0);

  using Clock = std::chrono::steady_clock;
  auto last = Clock::now();
  const auto started = last;
  std::uint64_t tick = 0, frames = 0, tick_at_report = 0;
  double worst_step_us = 0.0, worst_encode_us = 0.0, last_report = 0.0;
  // The periodic line reports the worst since the last line and then clears the two above.
  // The closing line reports the whole run, so it keeps its own pair. Sharing them printed
  // zero whenever a run ended on a report boundary, which every round CROWD_SECONDS does.
  double worst_step_all = 0.0, worst_encode_all = 0.0;

  for (;;) {
    const auto now = Clock::now();
    const double elapsed = std::chrono::duration<double>(now - last).count();
    last = now;

    const int steps = clock.advance(elapsed);
    for (int s = 0; s < steps; ++s) {
      const auto t0 = Clock::now();
      for (int k = 0; k < kSubsteps; ++k) mj_step(m, d);
      const double us = std::chrono::duration<double, std::micro>(Clock::now() - t0).count();
      if (us > worst_step_us) worst_step_us = us;
      if (us > worst_step_all) worst_step_all = us;
      ++tick;

      if (tick % 3 == 0) {                       // publish at a third of the sim rate
        const auto e0 = Clock::now();
        for (int i = 0; i < n; ++i) {
          const double* q = d->qpos + static_cast<std::size_t>(i) * nq_each;
          const double* v = d->qvel + static_cast<std::size_t>(i) * nv_each;
          for (int j = 0; j < nu_each; ++j) {
            crowd::Packet& p = frame[static_cast<std::size_t>(i) * nu_each + j];
            p.gid = (static_cast<std::uint32_t>(i) << 16) | static_cast<std::uint32_t>(j);
            p.sub_index = static_cast<std::uint32_t>(j);
            p.class_owner = (crowd::kClassSkeletonJoint << 24) | (i & 0xFFFFFF);
            p.hlc = static_cast<std::uint32_t>((tick / 3) << 8);

            // A muscle is one axis of one joint, normalised to that joint's own range, which
            // is what the packet's swing-twist field expects.
            const double span = jhi[j] - jlo[j];
            const double norm = span > 0 ? (q[7 + j] - jlo[j]) / span * 2.0 - 1.0 : 0.0;
            p.rot[0] = static_cast<std::int16_t>(std::fmax(-32767.0, std::fmin(32767.0,
                                                  norm * 32767.0)));
            p.vel[0] = static_cast<std::int16_t>(std::fmax(-32767.0, std::fmin(32767.0,
                                                  v[6 + j] / 30.0 * 32767.0)));

            // Only the root carries a position. Every other joint is derived by whoever reads
            // this, from a bone offset they already have, so the field stays zero and costs
            // nothing once the stream is delta coded.
            if (j == 0) {
              for (int k = 0; k < 3; ++k)
                p.pos[k] = static_cast<std::int64_t>(q[k] * 1e6);
            }
          }
        }
        const double eus = std::chrono::duration<double, std::micro>(Clock::now() - e0).count();
        if (eus > worst_encode_us) worst_encode_us = eus;
        if (eus > worst_encode_all) worst_encode_all = eus;
        ++frames;
      }
    }

    const double run = std::chrono::duration<double>(Clock::now() - started).count();

    // A plane that runs forever has to say how it is doing while it runs. Reporting only at
    // exit means a deployed plane is silent, which is what the first deployment did.
    if (run - last_report >= 10.0) {
      const std::uint64_t did = tick - tick_at_report;
      std::printf("[plane] %.0fs  %.1f Hz  %d bodies  %zu packets a frame  "
                  "worst step %.0f us, worst encode %.0f us, dropped %llu\n",
                  run, did / (run - last_report), n, frame.size(),
                  worst_step_us, worst_encode_us,
                  static_cast<unsigned long long>(clock.dropped_steps()));
      std::fflush(stdout);
      last_report = run;
      tick_at_report = tick;
      worst_step_us = 0.0;          // report the worst since the last report, not since boot
      worst_encode_us = 0.0;
    }

    if (seconds > 0 && run >= seconds) break;

    const double rest = clock.rest();
    if (rest > 0) {
      std::this_thread::sleep_for(std::chrono::duration<double>(rest));
    }
  }

  const double run = std::chrono::duration<double>(Clock::now() - started).count();
  std::printf("[plane] %llu ticks in %.2fs (%.1f Hz), %llu frames, %zu packets each\n",
              static_cast<unsigned long long>(tick), run, tick / run,
              static_cast<unsigned long long>(frames), frame.size());
  std::printf("[plane] worst step %.0f us, worst encode %.0f us, dropped %llu steps\n",
              worst_step_all, worst_encode_all,
              static_cast<unsigned long long>(clock.dropped_steps()));

  mj_deleteData(d);
  mj_deleteModel(m);
  return 0;
}
