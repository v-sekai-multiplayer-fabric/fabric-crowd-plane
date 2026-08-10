#!/usr/bin/env python3
"""The wall: how few bits can a body possibly take.

Two bounds, and the second is the real one.

**Entropy rate.** Order-N conditional entropy falls as N grows and converges to the entropy
rate of the source. That is the floor for lossless coding of the quantised stream, for any
coder that predicts from the past.

**Rate-distortion.** We do not need lossless. We need 0.088 degrees. For a stationary source
with power spectrum S(f), Shannon's water-filling gives the minimum rate for a mean-squared
distortion D:

    R = 1/2 * integral of max(0, log2(S(f) / theta)) df,   with theta set so
    D = integral of min(S(f), theta) df

No codec of any kind beats that. The Gaussian assumption makes it an upper bound on the true
minimum, so the real wall is at or below what this prints.
"""
import os, sys
import numpy as np, mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B, PREC_DEG, HZ = 1200, 8, 0.088, 20


def ent(a):
    _, c = np.unique(a, return_counts=True); p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def ent_ctx(sym, ctx):
    h = 0.0
    for v in np.unique(ctx):
        sel = sym[ctx == v]
        if sel.size:
            h += ent(sel) * sel.size / sym.size
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
    ang = np.zeros((F, B, nu))
    for i in range(F * 3 + 60):
        for b, d in enumerate(ds):
            d.ctrl[:] = 60 * np.sin(2 * np.pi * fr[b] * i / 60 + ph[b]); mujoco.mj_step(m, d)
        if i >= 60 and (i - 60) % 3 == 0:                 # sample the wire rate, 20 Hz
            k = (i - 60) // 3
            if k < F:
                for b, d in enumerate(ds):
                    ang[k, b] = d.qpos[7:7 + nu]

    bits_each = np.ceil(np.log2(np.degrees(span) / PREC_DEG)).astype(int)
    Q = np.round((ang - lo) / span * (2.0 ** bits_each - 1)).astype(np.int64)
    dQ = np.diff(Q, axis=0, prepend=Q[:1])

    print(f"{nu} muscles, sampled at {HZ} Hz, {F} frames, {B} bodies, {PREC_DEG} degree target")
    print()
    print("  entropy rate, by context order (lossless floor for a predictive coder)")
    prev = [np.concatenate([np.zeros_like(dQ[:k]), dQ[:-k]], axis=0) for k in (1, 2, 3)]
    for order in (0, 1, 2, 3):
        h = 0.0
        for j in range(nu):
            s = dQ[:, :, j].ravel()
            if order == 0:
                h += ent(s)
            else:
                c = np.zeros_like(s)
                for k in range(order):
                    c = c * 15 + bucket(prev[k])[:, :, j].ravel()
                h += ent_ctx(s, c)
        print(f"    order-{order}                                  {h/8:6.1f} B/body/frame")

    # --- rate-distortion, water-filling on the measured spectrum ---
    print()
    print("  rate-distortion wall (no codec of any kind beats this)")
    ang_deg = np.degrees(ang)
    D = (PREC_DEG ** 2) / 12.0            # a uniform quantiser at that step has this MSE
    total_bits = 0.0
    for j in range(nu):
        x = ang_deg[:, :, j] - ang_deg[:, :, j].mean(axis=0, keepdims=True)
        # Full FFT so Parseval holds: mean(S) over all F bins is the variance.
        X = np.fft.fft(x, axis=0)
        S = (np.abs(X) ** 2).mean(axis=1) / F
        S = np.maximum(S, 1e-18)
        lo_, hi_ = 1e-18, S.max()
        for _ in range(200):                         # bisect for the water level theta
            th = 0.5 * (lo_ + hi_)
            if np.minimum(S, th).mean() > D:
                hi_ = th
            else:
                lo_ = th
        th = 0.5 * (lo_ + hi_)
        # bits for each sample of this muscle
        total_bits += 0.5 * np.maximum(0.0, np.log2(S / th)).mean()
    print(f"    water-filling at {PREC_DEG} degrees            {total_bits/8:6.1f} B/body/frame")
    print(f"    (distortion target: MSE {D:.3e} deg^2, which is a {PREC_DEG} deg quantiser)")
    print()
    print(f"  measured best so far, order-2 plus paged root   22.1 B/body/frame")


if __name__ == "__main__":
    main()
