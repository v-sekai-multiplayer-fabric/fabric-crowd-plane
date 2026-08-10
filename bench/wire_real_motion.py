#!/usr/bin/env python3
"""The entropy of real human motion, not a driven ragdoll.

Every wire measurement in this book used a MuJoCo avatar driven by sinusoidal torques. That
is physically real and behaviourally meaningless: every joint moves all the time, which is the
worst case for a coder and not what a person does.

These are Mixamo's motion-capture-derived clips, 2457 of them, as BVH: a hierarchy of joints
with Euler rotation channels for each frame. Real motion, from real people, doing nameable
things.

The order-3 estimate on the old data was an artefact of three samples for each context. With
thousands of clips there is enough motion to say whether the entropy rate converges.
"""
import glob, os, sys
import numpy as np

CLIPS = os.environ.get("CLIPS", os.path.expanduser("~/motion/mixamo"))
PREC_DEG = 0.088
TARGET_HZ = 20


def parse_bvh(path):
    """Return (channel names, frames array, frame time). Only what is needed."""
    with open(path, "r", errors="ignore") as fh:
        text = fh.read()
    head, _, motion = text.partition("MOTION")
    names, stack = [], []
    for line in head.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] in ("ROOT", "JOINT"):
            stack.append(t[1])
        elif t[0] == "End":
            stack.append("End")
        elif t[0] == "}":
            if stack:
                stack.pop()
        elif t[0] == "CHANNELS":
            for c in t[2:]:
                names.append(f"{stack[-1]}.{c}")
    lines = [l for l in motion.splitlines() if l.strip()]
    ft = 1 / 30.0
    start = 0
    for i, l in enumerate(lines[:3]):
        if l.startswith("Frame Time"):
            ft = float(l.split(":")[1]); start = i + 1
    data = np.array([[float(v) for v in l.split()] for l in lines[start:] if l[0].isdigit() or l[0] == "-"])
    return names, data, ft


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
    files = sorted(glob.glob(os.path.join(CLIPS, "**", "*.bvh"), recursive=True))
    limit = int(os.environ.get("N", "400"))
    files = files[:limit]
    print(f"{len(files)} clips from {CLIPS}")

    rot_deltas, nrot, total_frames = [], None, 0
    for f in files:
        try:
            names, data, ft = parse_bvh(f)
        except Exception:
            continue
        if data.ndim != 2 or data.shape[0] < 20:
            continue
        step = max(1, int(round((1 / TARGET_HZ) / ft)))
        d = data[::step]
        idx = [i for i, n in enumerate(names) if "rotation" in n.lower()]
        if nrot is None:
            nrot = len(idx)
        if len(idx) != nrot:
            continue
        q = np.round(((d[:, idx] + 180.0) % 360.0) / PREC_DEG).astype(np.int64)
        rot_deltas.append(np.diff(q, axis=0))
        total_frames += len(q) - 1

    D = np.concatenate(rot_deltas, axis=0)
    print(f"{nrot} rotation channels, {total_frames} frames at ~{TARGET_HZ} Hz, "
          f"{D.shape[0]*nrot/1e6:.1f} M symbols")
    print()
    print(f"{'order':>7} {'contexts':>9} {'samples each':>13} {'B/body/frame':>14} {'gain':>7}")
    prev = [np.concatenate([np.zeros((k, nrot), np.int64), D[:-k]], axis=0) for k in (1, 2, 3)]
    last = None
    for order in (0, 1, 2, 3):
        h = 0.0
        for j in range(nrot):
            s = D[:, j]
            if order == 0:
                h += ent(s)
            else:
                c = np.zeros_like(s)
                for k in range(order):
                    c = c * 15 + bucket(prev[k][:, j])
                h += ent_ctx(s, c)
        b = h / 8
        ctxn = 15 ** order
        g = "" if last is None else f"{last-b:+.1f}"
        print(f"{order:>7} {ctxn:>9} {D.shape[0]/ctxn:>13.0f} {b:>14.1f} {g:>7}")
        last = b


if __name__ == "__main__":
    main()
