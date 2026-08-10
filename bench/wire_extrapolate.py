#!/usr/bin/env python3
"""What extrapolation buys, and what it costs in error.

The fabric packet carries a velocity at offset 28 for a reason: a client that knows where a
joint is and how fast it is going can carry it forward between updates. That turns the send
rate into a choice rather than a constant.

This measures the trade directly. Send at 20 Hz, 10, 5, 2. Between sends, hold the last
position, or carry it forward with the velocity. Report the position error a viewer would
actually see.
"""
import os, sys
import numpy as np, mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B, SIM_HZ = 600, 6, 60


def main():
    m = mujoco.MjModel.from_xml_path(XML); m.opt.timestep = 1 / SIM_HZ
    ds = [mujoco.MjData(m) for _ in range(B)]
    rng = np.random.default_rng(0)
    ph = rng.uniform(0, 6.28, (B, m.nu)); fr = rng.uniform(0.4, 1.4, (B, m.nu))
    nb = m.nbody - 1
    pos = np.zeros((F, B, nb, 3)); vel = np.zeros((F, B, nb, 3))
    prev = None
    for i in range(F + 60):
        for b, d in enumerate(ds):
            d.ctrl[:] = 120 * np.sin(2 * np.pi * fr[b] * i / SIM_HZ + ph[b])
            mujoco.mj_step(m, d)
        if i >= 60:
            cur = np.stack([d.xpos[1:] for d in ds])
            pos[i - 60] = cur
            vel[i - 60] = (cur - prev) * SIM_HZ if prev is not None else 0.0
            prev = cur
        elif i == 59:
            prev = np.stack([d.xpos[1:] for d in ds])

    print(f"{nb} joints, {B} bodies, {F} frames. Error is what a viewer sees, in millimetres.")
    print(f"{'send rate':>10} {'hold, mean':>12} {'hold, p99':>10} "
          f"{'extrap, mean':>13} {'extrap, p99':>12} {'kB/s a body':>12}")
    for hz in (20, 10, 5, 2):
        step = SIM_HZ // hz
        hold_e, ext_e = [], []
        for k in range(0, F - step, step):
            for j in range(1, step):
                t = j / SIM_HZ
                truth = pos[k + j]
                hold_e.append(np.linalg.norm(truth - pos[k], axis=-1))
                ext_e.append(np.linalg.norm(truth - (pos[k] + vel[k] * t), axis=-1))
        h = np.concatenate([e.ravel() for e in hold_e]) * 1000
        x = np.concatenate([e.ravel() for e in ext_e]) * 1000
        kbs = 108 * hz / 1000
        print(f"{hz:>8} Hz {h.mean():>12.1f} {np.percentile(h,99):>10.1f} "
              f"{x.mean():>13.1f} {np.percentile(x,99):>12.1f} {kbs:>12.2f}")


if __name__ == "__main__":
    main()
