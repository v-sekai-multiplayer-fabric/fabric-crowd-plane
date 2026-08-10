#!/usr/bin/env python3
# The nasty wire, in muscle space, with entropy coding.
#
# A pose is not 36 joints x 3 axes. V-Sekai's godot-humanoid-project (Apache-2.0, Lyuma and
# lox9973) carries the Mecanim humanoid representation: 95 scalar muscles, each one axis of
# one joint, normalised to [-1, 1] over an anatomical range held in MuscleDefaultMin and
# MuscleDefaultMax. Dropping the fingers, eyes, and jaw leaves 49 for a body in a crowd.
#
# Two things follow. There are fewer numbers, and each number spans tens of degrees rather
# than a full turn, so the same angular precision costs fewer bits.
import numpy as np, zstandard as zstd

# Ranges from human_trait.gd, body muscles only: spine/chest/upperchest/neck/head, legs, arms.
MAXD = np.array([40,40,40, 40,40,40, 20,20,20, 40,40,40, 40,40,40,
                 50,60,60,80,90,50,30,50,  50,60,60,80,90,50,30,50,
                 30,15,100,100,90,80,90,80,40,  30,15,100,100,90,80,90,80,40], float)
MIND = np.array([-40,-40,-40,-40,-40,-40,-20,-20,-20,-40,-40,-40,-40,-40,-40,
                 -90,-60,-60,-80,-90,-50,-30,-50, -90,-60,-60,-80,-90,-50,-30,-50,
                 -15,-15,-60,-100,-90,-80,-90,-80,-40, -15,-15,-60,-100,-90,-80,-90,-80,-40], float)
M = len(MAXD)
F, B = 400, 16
PREC = 0.088          # degrees, matching 12 bits over a full turn

def entropy_bits(sym):
    _, c = np.unique(sym, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())

def gait(seed):
    r = np.random.default_rng(seed)
    t = np.arange(F) / 20.0
    ph = r.uniform(0, 6.28, M); amp = r.uniform(0.1, 0.7, M); f = r.uniform(0.4, 1.4, M)
    a = np.sin(2*np.pi*f[None]*t[:,None] + ph[None]) * amp[None]
    a[:, r.random(M) < 0.35] *= 0.02        # many muscles barely move in a walk
    return np.clip(a, -1, 1)

mus = np.stack([gait(s) for s in range(B)], axis=1)          # F x B x M, normalised
span = MAXD - MIND
bits = np.ceil(np.log2(span / PREC)).astype(int)             # bits each muscle needs
print(f"{M} body muscles, {bits.min()}-{bits.max()} bits each, {bits.sum()} bits/body = {bits.sum()/8:.1f} B")
print(f"  vs 36 joints x 3 axes x 12 bits = {36*3*12/8:.1f} B\n")

q = np.round((mus + 1) / 2 * (2**bits - 1)).astype(np.int32)  # per-muscle bit depth
d = np.diff(q, axis=0, prepend=q[:1])
c = zstd.ZstdCompressor(level=3)
root = 12  # bytes, root position

per = lambda bitsum: bitsum/8 + root
raw_bits = float(bits.sum())
H_abs = sum(entropy_bits(q[:,:,m].ravel()) for m in range(M))
H_del = sum(entropy_bits(d[:,:,m].ravel()) for m in range(M))
rle_run = float((d == 0).mean())

print(f"{'form':38} {'B/body/frame':>13}")
print(f"{'  packed, per-muscle bit depth':38} {per(raw_bits):13.1f}")
print(f"{'  + zstd on the packed stream':38} {len(c.compress(q.astype(np.int16).tobytes()))/F/B + root:13.1f}")
print(f"{'  + delta, then zstd':38} {len(c.compress(d.astype(np.int16).tobytes()))/F/B + root:13.1f}")
print(f"{'  entropy floor, absolute':38} {per(H_abs):13.1f}")
print(f"{'  entropy floor, delta (THE FLOOR)':38} {per(H_del):13.1f}")
print(f"\n  {rle_run*100:.0f}% of muscle deltas are exactly zero, so a zero-run token pays.")
