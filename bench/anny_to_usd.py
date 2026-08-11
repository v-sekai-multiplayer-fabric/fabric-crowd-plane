#!/usr/bin/env python3
"""Write the Anny SOMA rig as OpenUSD, in metres.

Two things silently corrupt this conversion, and both produce a file that opens without
complaint.

**The rig is in centimetres.** Anny's `t_pose_world` puts the head at y=161 and a foot at
y=7.2. Read as metres that is a 154 metre skeleton, and every downstream length, mass, and
inertia is wrong by a hundred. USD carries the unit in `metersPerUnit`, so the file says what
it means instead of relying on a convention nobody reads.

**USD multiplies a row vector on the left.** `Gf.Matrix4d` therefore holds a translation in
its last row, and numpy holds it in the last column. A matrix passed across without a
transpose still loads, still animates, and is wrong. `verify` reads the positions back out of
the stage and compares them against the source, so the transpose cannot be silently dropped.

    python bench/anny_to_usd.py [out.usda]
"""
import os
import sys

import numpy as np

CM_PER_M = 100.0

# The 23 bodies the controller drives. The rig carries 78, and the rest are fingers and face.
SOMA23 = [
    "Hips", "Spine1", "Spine2", "Chest", "Neck1", "Neck2", "Head",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightLeg", "RightShin", "RightFoot", "RightToeBase",
    "LeftLeg", "LeftShin", "LeftFoot", "LeftToeBase",
]

DEFAULT_RIG = "/opt/weft-motion/anny/src/anny/data/soma/soma_rig.pt"

# A human skeleton, in metres. Anything outside this means the unit was read wrong, which is
# the whole failure this module exists to prevent.
MIN_HUMAN_M, MAX_HUMAN_M = 0.5, 2.5


def load_rig(path=DEFAULT_RIG):
    """Read the rig. Returns labels, parents, and world transforms in METRES."""
    if not os.path.exists(path):
        return ("error", "no rig at %s" % path)
    import torch
    d = torch.load(path, map_location="cpu", weights_only=False)
    labels = list(d["bone_labels"])
    parents = list(d["bone_parents"])
    world = np.asarray(d["t_pose_world"], dtype=np.float64).copy()
    # The only place the scale is applied. Rotation is unitless, so translation alone moves.
    world[:, :3, 3] /= CM_PER_M
    return ("ok", (labels, parents, world))


def joint_paths(labels, parents):
    """USD names a joint by its path from the root, which is how it encodes the hierarchy."""
    out = []
    for i in range(len(labels)):
        chain, j = [], i
        while j >= 0:
            chain.append(labels[j])
            j = parents[j]
        out.append("/".join(reversed(chain)))
    return out


def local_transforms(parents, world):
    """A rest transform is expressed in its parent, so undo the parent to get it."""
    out = np.zeros_like(world)
    for i in range(world.shape[0]):
        p = parents[i]
        out[i] = world[i] if p < 0 else np.linalg.inv(world[p]) @ world[i]
    return out


def write(out_path, labels, parents, world):
    from pxr import Usd, UsdGeom, UsdSkel, Gf

    stage = Usd.Stage.CreateNew(out_path)
    # The two pieces of metadata that make the file self-describing.
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    root = UsdSkel.Root.Define(stage, "/Anny")
    skel = UsdSkel.Skeleton.Define(stage, "/Anny/Skeleton")

    paths = joint_paths(labels, parents)
    local = local_transforms(parents, world)

    def to_gf(m):
        # numpy puts translation in the last column, USD in the last row.
        return Gf.Matrix4d(*m.T.flatten().tolist())

    skel.GetJointsAttr().Set(paths)
    skel.GetBindTransformsAttr().Set([to_gf(m) for m in world])
    skel.GetRestTransformsAttr().Set([to_gf(m) for m in local])
    stage.SetDefaultPrim(root.GetPrim())
    stage.GetRootLayer().Save()
    return ("ok", out_path)


def verify(out_path, labels, world):
    """Read the stage back and check the unit and the transpose against the source."""
    from pxr import Usd, UsdGeom, UsdSkel

    stage = Usd.Stage.Open(out_path)
    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    if abs(mpu - 1.0) > 1e-9:
        return ("error", "metersPerUnit is %r, not 1.0" % mpu)

    skel = UsdSkel.Skeleton(stage.GetPrimAtPath("/Anny/Skeleton"))
    binds = skel.GetBindTransformsAttr().Get()
    got = np.array([[m[3][0], m[3][1], m[3][2]] for m in binds])   # USD: translation is row 3
    want = world[:, :3, 3]
    err = float(np.abs(got - want).max())
    if err > 1e-9:
        return ("error", "positions do not survive the round trip, worst %.3g m "
                         "(a dropped transpose looks exactly like this)" % err)

    idx = {n: i for i, n in enumerate(labels)}
    height = float(got[idx["Head"], 1] - got[idx["LeftFoot"], 1])
    if not (MIN_HUMAN_M <= height <= MAX_HUMAN_M):
        return ("error", "skeleton is %.2f m tall, which is not a person. The rig is in "
                         "centimetres and the scale was not applied." % height)
    missing = [b for b in SOMA23 if b not in idx]
    if missing:
        return ("error", "missing SOMA bodies: %s" % missing)
    return ("ok", {"metersPerUnit": mpu, "height_m": height, "joints": len(binds),
                   "roundtrip_err_m": err})


def main(argv):
    out = argv[1] if len(argv) > 1 else "/opt/weft-motion/anny-soma-rig.usda"
    tag, val = load_rig()
    if tag == "error":
        print("error:", val); return 1
    labels, parents, world = val
    print("rig: %d bones, scaled by 1/%g" % (len(labels), CM_PER_M))
    tag, val = write(out, labels, parents, world)
    if tag == "error":
        print("error:", val); return 1
    tag, val = verify(out, labels, world)
    if tag == "error":
        print("VERIFY FAILED:", val); return 1
    print("wrote %s" % out)
    print("  metersPerUnit %.1f   height %.3f m   joints %d   round trip %.2g m"
          % (val["metersPerUnit"], val["height_m"], val["joints"], val["roundtrip_err_m"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
