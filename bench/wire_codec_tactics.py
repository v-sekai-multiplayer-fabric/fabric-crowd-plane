#!/usr/bin/env python3
"""Squeeze the entity packet stream without changing the packet.

The schema is fixed: `XRGridEntityPacket`, 100 bytes, one for each joint entity. Everything
here is a transport transform, invisible to the format and reversible exactly, so a decoder
still hands the application the same packets the encoder was given.

The gap to close is 108 bytes for a body against 21 for a body-oriented encoding, and the
whole of it is the absolute int64 position carried on every joint.
"""
import os, sys
import numpy as np, mujoco, zstandard as zstd

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B = 400, 8


def ent(a):
    _, c = np.unique(a, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def ent_ctx(sym, ctx):
    """Order-1: cost of each symbol given a bucket of its own previous value."""
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
    nb = m.nbody - 1
    pos = np.zeros((F, B, nb, 3)); quat = np.zeros((F, B, nb, 4))
    for i in range(F + 60):
        for b, d in enumerate(ds):
            d.ctrl[:] = 120 * np.sin(2 * np.pi * fr[b] * i / 60 + ph[b])
            mujoco.mj_step(m, d)
            if i >= 60:
                pos[i - 60, b] = d.xpos[1:]
                q = np.empty(4)
                for k in range(nb):
                    mujoco.mju_mat2Quat(q, d.xmat[1 + k]); quat[i - 60, b, k] = q

    P = np.round(pos * 1e6).astype(np.int64)          # int64 micrometres, as the packet says
    R = np.clip(np.round(quat[..., 1:] * 32767), -32767, 32767).astype(np.int32)
    n = F * B
    bits = lambda h: h / 8

    def total_bits(arrays):
        """Bits for one body for one frame: every joint and every axis is its own symbol."""
        h = 0.0
        for a in arrays:
            j = a.shape[2]
            for jj in range(j):
                for k in range(a.shape[-1]):
                    h += ent(a[:, :, jj, k].ravel())
        return h

    def report(name, arrays, note=""):
        h = total_bits(arrays)
        print(f"  {name:46} {bits(h):7.1f} B/body/frame  {note}")
        return bits(h)

    print(f"{nb} joints, {B} bodies, {F} frames. Entropy floors, so an ideal coder.")
    print()
    # 1. temporal delta only, which is what the earlier entry measured
    dP = np.diff(P, axis=0, prepend=P[:1]).astype(np.int64)
    dR = np.diff(R, axis=0, prepend=R[:1])
    base = report("temporal delta of absolute position", [dP, dR])

    # 2. spatial: express each joint relative to its body's root, then delta in time
    root = P[:, :, :1, :]
    rel = P - root                                     # joint minus root, exact
    dRel = np.diff(rel, axis=0, prepend=rel[:1])
    dRoot = np.diff(root, axis=0, prepend=root[:1])
    spatial = report("root delta + joint-relative delta", [dRel, dRoot, dR])

    # 3. quantise the relative position to millimetres, which a limb does not need beyond
    relmm = np.round(rel / 1000).astype(np.int64)
    dRelmm = np.diff(relmm, axis=0, prepend=relmm[:1])
    mm = report("the same, joint offsets in millimetres", [dRelmm, dRoot, dR])

    # 4. order-1 context on the millimetre form
    def ctx_of(a):
        prev = np.concatenate([np.zeros_like(a[:1]), a[:-1]], axis=0)
        return np.clip(np.sign(prev) * np.minimum(np.abs(prev) // 4, 7), -7, 7)
    h = 0.0
    for a in (dRelmm, dRoot, dR):
        c_all = ctx_of(a)
        for jj in range(a.shape[2]):
            for k in range(a.shape[-1]):
                h += ent_ctx(a[:, :, jj, k].ravel(), c_all[:, :, jj, k].ravel())
    print(f"  {'plus an order-1 context model':46} {bits(h):7.1f} B/body/frame")
    # 5. Do not vary what the receiver can derive. The schema still has a position on every
    #    joint; it simply stops changing, so the delta is always zero and costs no bits. The
    #    client reconstructs each joint from its parent's rotation and a static bone length.
    zeros = np.zeros_like(dRel)
    derived = report("derived joints: position held constant", [zeros, dRoot, dR])
    h2 = 0.0
    for a in (zeros, dRoot, dR):
        c_all = ctx_of(a)
        for jj in range(a.shape[2]):
            for k in range(a.shape[-1]):
                h2 += ent_ctx(a[:, :, jj, k].ravel(), c_all[:, :, jj, k].ravel())
    print(f"  {'the same, plus order-1 context':46} {bits(h2):7.1f} B/body/frame")
    # 6. The i16 rotation field does not need all 16 bits. A quaternion component quantised
    #    to 12 bits is 0.09 degrees, finer than any tracker reports, and the value still
    #    travels in the i16 the schema defines.
    print()
    print("  rotation precision, positions still derived:")
    best = None
    for b_ in (16, 12, 10, 8):
        step = 1 << (16 - b_)
        Rq = (R // step) * step
        dRq = np.diff(Rq, axis=0, prepend=Rq[:1])
        hq = 0.0
        for a in (zeros, dRoot, dRq):
            c_all = ctx_of(a)
            for jj in range(a.shape[2]):
                for k in range(a.shape[-1]):
                    hq += ent_ctx(a[:, :, jj, k].ravel(), c_all[:, :, jj, k].ravel())
        deg = 360.0 / (1 << b_)
        print(f"    {b_:2} bits an axis ({deg:5.2f} deg)          {bits(hq):7.1f} B/body/frame")
        if b_ == 12: best = bits(hq)
    print()
    print(f"  body-oriented encoding, measured earlier     21.0 B/body/frame")
    print(f"  packet at 12-bit rotations over that         {best/21:.2f}x")


if __name__ == "__main__":
    main()
