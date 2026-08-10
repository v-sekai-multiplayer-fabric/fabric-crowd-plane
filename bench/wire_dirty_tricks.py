#!/usr/bin/env python3
"""Four more tricks on the muscle packet stream, three borrowed from Godot.

  page bounds     quantise inside a local range for each page, not a global one
  octahedral      Godot's axis encoding, checked against swing-twist by arithmetic
  key dropping    do not send a muscle until its held value drifts past a threshold
  order-2 context condition a symbol on two previous deltas rather than one
"""
import os, sys
import numpy as np, mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B, PREC_DEG, PAGE = 600, 8, 0.088, 120


def ent(a):
    _, c = np.unique(a, return_counts=True); p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def ent_ctx(sym, ctx):
    h = 0.0
    for v in np.unique(ctx):
        sel = sym[ctx == v]
        h += ent(sel) * len(sel) / len(sym)
    return h


def bucket(a, w=4, cap=7):
    return np.clip(np.sign(a) * np.minimum(np.abs(a) // w, cap), -cap, cap)


def main():
    m = mujoco.MjModel.from_xml_path(XML); m.opt.timestep = 1 / 60
    ds = [mujoco.MjData(m) for _ in range(B)]
    rng = np.random.default_rng(0)
    ph = rng.uniform(0, 6.28, (B, m.nu)); fr = rng.uniform(0.4, 1.4, (B, m.nu))
    nu = m.nu
    lo = m.jnt_range[1:, 0].copy(); hi = m.jnt_range[1:, 1].copy()
    span = np.maximum(hi - lo, 1e-6)
    ang = np.zeros((F, B, nu)); root = np.zeros((F, B, 3))
    for i in range(F + 60):
        for b, d in enumerate(ds):
            d.ctrl[:] = 120 * np.sin(2 * np.pi * fr[b] * i / 60 + ph[b]); mujoco.mj_step(m, d)
            if i >= 60:
                ang[i - 60, b] = d.qpos[7:7 + nu]; root[i - 60, b] = d.xpos[1]

    bits_each = np.ceil(np.log2(np.degrees(span) / PREC_DEG)).astype(int)
    Q = np.round((ang - lo) / span * (2.0 ** bits_each - 1)).astype(np.int64)
    dQ = np.diff(Q, axis=0, prepend=Q[:1])
    n = F * B

    # --- baseline: absolute-micrometre root, order-1 on everything ---
    Rt = np.round(root * 1e6).astype(np.int64)
    dR = np.diff(Rt, axis=0, prepend=Rt[:1])
    hq1 = sum(ent_ctx(dQ[:, :, j].ravel(), bucket(np.diff(Q, axis=0, prepend=Q[:1]))[:, :, j].ravel())
              for j in range(nu))
    hr_abs = sum(ent_ctx(dR[:, :, k].ravel(), bucket(dR)[:, :, k].ravel()) for k in range(3))
    print(f"{nu} muscles, {bits_each.min()}-{bits_each.max()} bits each, {F} frames, {B} bodies")
    print(f"  baseline: muscles order-1 + root as int64 um   "
          f"{(hq1 + hr_abs)/8:6.1f} B/body/frame   (root is {hr_abs/8:.1f} of it)")

    # --- 1. page bounds on the root ---
    npages = F // PAGE
    hr_page = 0.0
    for p in range(npages):
        seg = Rt[p * PAGE:(p + 1) * PAGE]
        loc = seg - seg.min(axis=0, keepdims=True)          # local to this page
        rngp = np.maximum(loc.max(axis=(0, 1)) - loc.min(axis=(0, 1)), 1)
        q = np.round(loc / rngp[None, None, :] * 65535).astype(np.int64)   # Godot: 16 bit in bounds
        dq = np.diff(q, axis=0, prepend=q[:1])
        hr_page += sum(ent_ctx(dq[:, :, k].ravel(), bucket(dq)[:, :, k].ravel())
                       for k in range(3)) / npages
    print(f"  1. root in per-page bounds, 16 bit             "
          f"{(hq1 + hr_page)/8:6.1f} B/body/frame   (root now {hr_page/8:.1f})")

    # --- 2. octahedral, by arithmetic ---
    print()
    print("  2. octahedral against swing-twist, per joint:")
    print(f"       octahedral: axis 2 x 16 + angle 16      = 48 bits, uniform over a sphere")
    print(f"       swing-twist with anatomical ranges      = {bits_each[:3].sum()} bits "
          f"({bits_each.min()}-{bits_each.max()} each)")
    print(f"       -> swing-twist is smaller by {48 - int(bits_each[:3].sum())} bits a joint. "
          f"Octahedral buys uniform error, not size.")

    # --- 3. error-bounded key dropping ---
    print()
    print("  3. dropping keys until the held value drifts:")
    print(f"     {'threshold':>12} {'sent':>8} {'B/body/frame':>14} {'mean err':>10} {'p99 err':>9}")
    for thr_deg in (0.0, 0.2, 0.5, 1.0, 2.0):
        thr = thr_deg / PREC_DEG
        sent = np.zeros_like(Q, dtype=bool); held = Q[0].copy()
        errs = []
        for t in range(F):
            drift = np.abs(Q[t] - held)
            need = drift > thr
            if t == 0:
                need[:] = True
            sent[t] = need
            held = np.where(need, Q[t], held)
            errs.append(np.abs(Q[t] - held))
        frac = sent.mean()
        # only sent symbols cost bits; a skipped muscle costs its share of a presence mask
        hq = 0.0
        for j in range(nu):
            s = dQ[:, :, j][sent[:, :, j]]
            if s.size:
                hq += ent(s) * s.size / n
        mask = ent(sent.reshape(-1, nu).view(np.uint8).ravel()) * nu / 8
        e = np.concatenate([x.ravel() for x in errs]) * np.repeat(
            np.degrees(span) / (2.0 ** bits_each - 1), 1)[None, :].repeat(1, 0).ravel()[:1].mean()
        err_deg = np.concatenate([x.ravel() for x in errs]).mean() * PREC_DEG
        err99 = np.percentile(np.concatenate([x.ravel() for x in errs]), 99) * PREC_DEG
        print(f"     {thr_deg:>10.1f} deg {frac*100:>7.0f}% {(hq + mask + hr_page)/8:>14.1f} "
              f"{err_deg:>9.2f}d {err99:>8.2f}d")

    # --- 4. order-2 context ---
    print()
    prev1 = np.concatenate([np.zeros_like(dQ[:1]), dQ[:-1]], axis=0)
    prev2 = np.concatenate([np.zeros_like(dQ[:2]), dQ[:-2]], axis=0)
    c1 = bucket(prev1)
    c2 = bucket(prev1) * 15 + bucket(prev2)
    h0 = sum(ent(dQ[:, :, j].ravel()) for j in range(nu))
    hA = sum(ent_ctx(dQ[:, :, j].ravel(), c1[:, :, j].ravel()) for j in range(nu))
    hB = sum(ent_ctx(dQ[:, :, j].ravel(), c2[:, :, j].ravel()) for j in range(nu))
    print("  4. context order on the muscle deltas (muscles only, root excluded):")
    print(f"       order-0                                 {h0/8:6.1f} B/body/frame")
    print(f"       order-1, own previous delta             {hA/8:6.1f}   ({(1-hA/h0)*100:.0f}% better)")
    print(f"       order-2, two previous deltas            {hB/8:6.1f}   ({(1-hB/hA)*100:.0f}% better than order-1)")


if __name__ == "__main__":
    main()
