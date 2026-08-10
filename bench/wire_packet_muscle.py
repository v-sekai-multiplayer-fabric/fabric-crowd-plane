#!/usr/bin/env python3
"""The packet carrying what we actually send: muscles, not quaternions.

Earlier measurements in this book packed raw quaternion components into the packet's rotation
field. That was wrong. The field is `i16 swing-twist x3`, and the pose representation this
project chose is the Mecanim muscle system from `godot-humanoid-project`: three scalars for a
joint, each normalised to an anatomical range. Swing-twist and muscles are the same
decomposition, so the field already fits.

That matters twice. The values are per-joint triples either way, but a muscle is bounded by
what a human joint can do rather than by a full turn, so the same angular precision costs
fewer bits, and the coder sees a narrower distribution.

Positions stay derived: the field is present and constant, and the client reconstructs each
joint from its parent and a static bone length.
"""
import os, sys
import numpy as np, mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B = 400, 8
PREC_DEG = 0.088


def ent(a):
    _, c = np.unique(a, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def ent_ctx(sym, ctx):
    h = 0.0
    for v in np.unique(ctx):
        sel = sym[ctx == v]
        h += ent(sel) * len(sel) / len(sym)
    return h


def main():
    m = mujoco.MjModel.from_xml_path(XML); m.opt.timestep = 1 / 60
    ds = [mujoco.MjData(m) for _ in range(B)]
    rng = np.random.default_rng(0)
    ph = rng.uniform(0, 6.28, (B, m.nu)); fr = rng.uniform(0.4, 1.4, (B, m.nu))

    # Joint angles ARE the muscle values here: one scalar for each hinge, bounded by its range.
    nu = m.nu
    lo = m.jnt_range[1:, 0].copy(); hi = m.jnt_range[1:, 1].copy()
    span = np.maximum(hi - lo, 1e-6)
    ang = np.zeros((F, B, nu)); root = np.zeros((F, B, 3))
    for i in range(F + 60):
        for b, d in enumerate(ds):
            d.ctrl[:] = 120 * np.sin(2 * np.pi * fr[b] * i / 60 + ph[b])
            mujoco.mj_step(m, d)
            if i >= 60:
                ang[i - 60, b] = d.qpos[7:7 + nu]
                root[i - 60, b] = d.xpos[1]

    # Per-muscle bit depth from its own anatomical range, at 0.088 degrees.
    bits_each = np.ceil(np.log2(np.degrees(span) / PREC_DEG)).astype(int)
    Q = np.round((ang - lo) / span * (2.0 ** bits_each - 1)).astype(np.int64)
    Rt = np.round(root * 1e6).astype(np.int64)
    dQ = np.diff(Q, axis=0, prepend=Q[:1])
    dR = np.diff(Rt, axis=0, prepend=Rt[:1])

    def ctx_of(a):
        prev = np.concatenate([np.zeros_like(a[:1]), a[:-1]], axis=0)
        return np.clip(np.sign(prev) * np.minimum(np.abs(prev) // 4, 7), -7, 7)

    h0 = sum(ent(dQ[:, :, j].ravel()) for j in range(nu)) + \
         sum(ent(dR[:, :, k].ravel()) for k in range(3))
    cq, cr = ctx_of(dQ), ctx_of(dR)
    h1 = sum(ent_ctx(dQ[:, :, j].ravel(), cq[:, :, j].ravel()) for j in range(nu)) + \
         sum(ent_ctx(dR[:, :, k].ravel(), cr[:, :, k].ravel()) for k in range(3))

    print(f"{nu} muscles a body, bit depth {bits_each.min()}-{bits_each.max()} from range")
    print(f"  packet, muscles in the rot field, delta      {h0/8:7.1f} B/body/frame")
    print(f"  the same, plus an order-1 context model      {h1/8:7.1f} B/body/frame")
    print()
    print(f"  what this book wrongly measured (quaternions)  53.5")
    print(f"  body-oriented encoding, measured earlier       21.0")


if __name__ == "__main__":
    main()
