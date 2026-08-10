#!/usr/bin/env python3
"""Render the crowd to frames, offscreen.

The first attempt captured the screen with x11grab and produced black stills: this is a
Wayland session, so the X root window it grabbed has nothing on it. Screen capture was the
wrong tool anyway. MuJoCo renders offscreen through EGL, which needs no display, no browser,
and no compositor, and it gives clean frames at whatever resolution is asked for.

    MUJOCO_GL=egl python deploy/render.py out.mp4
"""
import os, subprocess, sys

os.environ.setdefault("MUJOCO_GL", "egl")

import mujoco
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from touchable import venue

N = int(os.environ.get("BODIES", "40"))
SPACING = float(os.environ.get("SPACING", "0.9"))
SECS = float(os.environ.get("SECS", "30"))
FPS = int(os.environ.get("FPS", "30"))
W = int(os.environ.get("W", "1280"))
H = int(os.environ.get("H", "720"))
PUSH = float(os.environ.get("PUSH", "2500"))


def main(out):
    m = mujoco.MjModel.from_xml_string(venue(N, SPACING))
    m.opt.timestep = 1 / 60
    d = mujoco.MjData(m)
    roots = np.array([b for b in range(1, m.nbody) if m.body_parentid[b] == 0])
    for _ in range(60):
        mujoco.mj_step(m, d)

    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(cam)
    cam.lookat[:] = [N ** 0.5 * SPACING / 2, N ** 0.5 * SPACING / 2, 0.6]
    cam.distance = 11.0
    cam.elevation = -14.0

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "ffv1", "-level", "3", out],           # lossless intermediate
        stdin=subprocess.PIPE)

    with mujoco.Renderer(m, height=H, width=W) as r:
        total = int(SECS * FPS)
        for f in range(total):
            # One body shoves into the crowd so the contact is visible rather than implied.
            for _ in range(60 // FPS):
                d.xfrc_applied[:] = 0.0
                d.xfrc_applied[roots[0], 0] = PUSH
                d.xfrc_applied[roots[0], 1] = PUSH * 0.4
                mujoco.mj_step(m, d)
            cam.azimuth = 35.0 + 40.0 * f / total       # a slow orbit
            r.update_scene(d, camera=cam)
            ff.stdin.write(r.render().astype(np.uint8).tobytes())
            if f % (FPS * 5) == 0:
                print(f"  {f/FPS:5.1f}s / {SECS:.0f}s", flush=True)

    ff.stdin.close()
    ff.wait()
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/crowd_raw.mkv")
