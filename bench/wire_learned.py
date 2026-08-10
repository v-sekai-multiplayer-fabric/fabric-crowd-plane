#!/usr/bin/env python3
# Real motion, not synthetic, and what a learned model could take off it.
#
# The synthetic gait used earlier makes every muscle an independent sinusoid, so it has no
# inter-joint correlation at all. That is the one thing PCA and a learned model exploit, so
# measuring them on it would understate both. This drives the tracked avatar in MuJoCo under
# gravity and contact and records what the joints actually do.
import numpy as np, os, mujoco, zstandard as zstd
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

m = mujoco.MjModel.from_xml_path("assets/tracked_avatar.xml")
m.opt.timestep = 1/60
F, B, PREC = 900, 12, 0.088

def record(seed):
    d = mujoco.MjData(m)
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 6.28, m.nu); f = r.uniform(0.6, 1.6, m.nu); a = r.uniform(20, 90, m.nu)
    out = np.zeros((F, m.nu))
    for i in range(F + 120):
        t = i / 60.0
        d.ctrl[:] = a * np.sin(2*np.pi*f*t + ph)
        mujoco.mj_step(m, d)
        if i >= 120: out[i-120] = d.qpos[7:7+m.nu]
    return out

X = np.stack([record(s) for s in range(B)], axis=1)          # F x B x nu
D = X.shape[2]
flat = X.reshape(-1, D)
print(f"real motion: {F} frames, {B} bodies, {D} joints, range {flat.min():.2f}..{flat.max():.2f} rad")

def ent(sym):
    _, c = np.unique(sym, return_counts=True); p = c/c.sum()
    return float(-(p*np.log2(p)).sum())

step = np.deg2rad(PREC)
q = np.round(X/step).astype(np.int32)
d1 = np.diff(q, axis=0, prepend=q[:1])
H0 = sum(ent(d1[:,:,j].ravel()) for j in range(D))
print(f"\n  order-0 entropy of deltas          {H0/8:7.1f} B/body/frame")

# order-1: condition each joint on the sign/size bucket of its own previous delta
prev = np.concatenate([np.zeros((1,B,D),int), d1[:-1]], axis=0)
ctx = np.clip(np.sign(prev)*np.minimum(np.abs(prev)//8, 7), -7, 7)
H1 = 0.0
for j in range(D):
    s, c = d1[:,:,j].ravel(), ctx[:,:,j].ravel()
    for v in np.unique(c):
        sel = s[c==v]
        H1 += ent(sel)*len(sel)/len(s)
print(f"  order-1, context on own history    {H1/8:7.1f} B/body/frame")

# PCA on poses
mu = flat.mean(0); Xc = flat-mu
U,S,Vt = np.linalg.svd(Xc, full_matrices=False)
var = np.cumsum(S**2)/np.sum(S**2)
print(f"\n  PCA: components for 99% variance   {int(np.searchsorted(var,0.99))+1} of {D}")
for k in (8, 12, 16, 24):
    rec = (Xc@Vt[:k].T)@Vt[:k]+mu
    err = np.rad2deg(np.abs(rec-flat).max())
    coef = (Xc@Vt[:k].T).reshape(F,B,k)
    qc = np.round(coef/ (step)).astype(np.int32)
    dc = np.diff(qc, axis=0, prepend=qc[:1])
    Hk = sum(ent(dc[:,:,i].ravel()) for i in range(k))
    print(f"    k={k:2}  worst joint error {err:6.2f} deg   {Hk/8:6.1f} B/body/frame")
