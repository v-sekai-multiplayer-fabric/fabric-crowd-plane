#!/usr/bin/env python3
# Is real human pose low rank? Measured, not asserted.
#
# sinew-mocap's calibrator set (github.com/sinew-mocap/mount-drift, calibrator-v1) carries
# 11794 real poses from 25 subjects across 11 AddBiomechanics studies. Each pose is 30 body
# segments in the 6D continuous rotation representation, which is two orthonormal columns of
# the rotation matrix.
#
# The earlier PCA measurement used a MuJoCo ragdoll driven by random torques and needed 25 of
# 26 components. This is the same question asked of real people.
import numpy as np, pyarrow.parquet as pq, sys

path = sys.argv[1] if len(sys.argv) > 1 else "../../mocap/caldata_test_jc.parquet"
t = pq.read_table(path)
Y = np.array(t.column("y").to_pylist(), dtype=np.float64)
S = Y.shape[1] // 6
print(f"{Y.shape[0]} real poses, {S} segments, 6D rotations, {Y.shape[1]} dims")

def to_R(y):                      # 6D -> rotation matrix, Gram-Schmidt
    a, b = y[..., :3], y[..., 3:6]
    e1 = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b - (e1 * b).sum(-1, keepdims=True) * e1
    e2 = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.stack([e1, e2, np.cross(e1, e2)], axis=-2)

def geodesic_deg(A, B):
    c = (np.einsum("...ij,...ij->...", A, B) - 1) / 2
    return np.degrees(np.arccos(np.clip(c, -1, 1)))

R_true = to_R(Y.reshape(-1, S, 6))
mu = Y.mean(0); Yc = Y - mu
U, Sv, Vt = np.linalg.svd(Yc, full_matrices=False)
var = np.cumsum(Sv**2) / np.sum(Sv**2)
print(f"components for 90/95/99% variance: "
      f"{np.searchsorted(var,0.90)+1} / {np.searchsorted(var,0.95)+1} / {np.searchsorted(var,0.99)+1}"
      f"  of {Y.shape[1]}")
print(f"\n{'k':>4} {'median deg':>11} {'p95 deg':>9} {'worst deg':>10}")
for k in (4, 8, 12, 16, 24, 32, 48):
    rec = (Yc @ Vt[:k].T) @ Vt[:k] + mu
    e = geodesic_deg(R_true, to_R(rec.reshape(-1, S, 6)))
    print(f"{k:>4} {np.median(e):>11.2f} {np.percentile(e,95):>9.2f} {np.max(e):>10.2f}")

# --- root-relative: strip the global heading, which linear PCA cannot represent ---
print("\nroot-relative (every segment premultiplied by the root's inverse)")
Rroot = R_true[:, :1]                               # N x 1 x 3 x 3
Rrel = np.einsum("nkji,nsjk->nsik", Rroot, R_true) if False else \
       np.matmul(np.transpose(Rroot, (0,1,3,2)), R_true)
Yrel = Rrel[..., :2, :].reshape(len(Rrel), -1)      # back to 6D, first two rows
mu2 = Yrel.mean(0); Yc2 = Yrel - mu2
U2, S2, V2 = np.linalg.svd(Yc2, full_matrices=False)
var2 = np.cumsum(S2**2)/np.sum(S2**2)
print(f"components for 90/95/99% variance: "
      f"{np.searchsorted(var2,0.90)+1} / {np.searchsorted(var2,0.95)+1} / {np.searchsorted(var2,0.99)+1}"
      f"  of {Yrel.shape[1]}")
print(f"{'k':>4} {'median deg':>11} {'p95 deg':>9} {'worst deg':>10}")
for k in (4, 8, 12, 16, 24, 32, 48):
    rec = (Yc2 @ V2[:k].T) @ V2[:k] + mu2
    e = geodesic_deg(Rrel, to_R(rec.reshape(-1, S, 6)))
    print(f"{k:>4} {np.median(e):>11.2f} {np.percentile(e,95):>9.2f} {np.max(e):>10.2f}")
