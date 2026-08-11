#!/usr/bin/env python3
"""Kimodo output to OpenUSD, in metres.

USD is the intermediate here, not BVH and not FBX. BVH carries a skeleton and Euler angles
with no unit and no agreed axis, so every reader guesses; FBX is a closed format that needs a
vendor SDK. A `UsdSkel` file states its unit in `metersPerUnit`, states its up axis, and
carries the rest pose and the animation in one place that a plain text diff can read.

The skeleton is `somaskel77`, taken from the T-pose BVH that ships with the model rather than
retyped, so it cannot drift from what the model actually emits.

Kimodo already emits metres, unlike the Anny rig which is centimetres. The converter checks
that rather than trusting it, because the two sources disagree and only one of them says so.

    python kimodo_to_usd.py in.npz out.usda
"""
import os
import sys

import numpy as np

MIN_HUMAN_M, MAX_HUMAN_M = 0.5, 2.5
TPOSE_BVH = "/opt/weft-motion/kimodo-src/kimodo/assets/skeletons/somaskel77/somaskel77_standard_tpose.bvh"


def parse_bvh_hierarchy(path):
    """Names, parents, and rest offsets from the BVH the model ships. Hierarchy only."""
    if not os.path.exists(path):
        return ("error", "no skeleton at %s" % path)
    names, parents, offsets = [], [], []
    stack = []
    with open(path) as fh:
        for raw in fh:
            t = raw.split()
            if not t:
                continue
            if t[0] in ("ROOT", "JOINT"):
                names.append(t[1])
                parents.append(stack[-1] if stack else -1)
                stack.append(len(names) - 1)
            elif t[0] == "End":
                stack.append(None)                  # End Site owns no joint
            elif t[0] == "OFFSET":
                if stack and stack[-1] is not None and len(offsets) < len(names):
                    offsets.append([float(x) for x in t[1:4]])
            elif t[0] == "}":
                if stack:
                    stack.pop()
            elif t[0] == "MOTION":
                break
    off = np.array(offsets, dtype=np.float64)

    # The BVH is a ROOT node plus 77 JOINTs, and the model emits the 77. Drop the ROOT and
    # reparent, so index 0 is Hips and lines up with the motion.
    names, parents, off = names[1:], [p - 1 for p in parents[1:]], off[1:]

    # The offsets are CENTIMETRES while the motion this drives is METRES. The two halves of
    # one model disagree, so the skeleton is converted and the motion is not.
    off = off / 100.0
    return ("ok", (names, parents, off))


def rot_to_quat(m):
    """Rotation matrices (..,3,3) to (w,x,y,z), the order USD's Quatf takes."""
    t = np.trace(m, axis1=-2, axis2=-1)
    q = np.zeros(m.shape[:-2] + (4,))
    big = t > 0
    s = np.sqrt(np.maximum(t[big] + 1.0, 1e-12)) * 2
    q[big, 0] = 0.25 * s
    q[big, 1] = (m[big, 2, 1] - m[big, 1, 2]) / s
    q[big, 2] = (m[big, 0, 2] - m[big, 2, 0]) / s
    q[big, 3] = (m[big, 1, 0] - m[big, 0, 1]) / s
    for i, (a, b, c) in enumerate(((0, 1, 2), (1, 2, 0), (2, 0, 1))):
        sel = (~big) & (np.argmax(np.diagonal(m, axis1=-2, axis2=-1), axis=-1) == i)
        if not sel.any():
            continue
        mm = m[sel]
        s = np.sqrt(np.maximum(1.0 + mm[:, a, a] - mm[:, b, b] - mm[:, c, c], 1e-12)) * 2
        q[sel, 0] = (mm[:, c, b] - mm[:, b, c]) / s
        q[sel, 1 + a] = 0.25 * s
        q[sel, 1 + b] = (mm[:, b, a] + mm[:, a, b]) / s
        q[sel, 1 + c] = (mm[:, c, a] + mm[:, a, c]) / s
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / np.maximum(n, 1e-12)


def joint_paths(names, parents):
    out = []
    for i in range(len(names)):
        chain, j = [], i
        while j >= 0:
            chain.append(names[j])
            j = parents[j]
        out.append("/".join(reversed(chain)))
    return out


def convert(npz_path, usd_path):
    from pxr import Usd, UsdGeom, UsdSkel, Gf, Vt, Sdf

    tag, val = parse_bvh_hierarchy(TPOSE_BVH)
    if tag == "error":
        return ("error", val)
    names, parents, offsets = val

    # The rest pose must also be a person once converted, or the centimetre divide is wrong.
    rest_h = float(offsets[:, 1].max() - offsets[:, 1].min())
    if rest_h > MAX_HUMAN_M:
        return ("error", "rest skeleton spans %.1f m; the offsets are not in the unit assumed" % rest_h)

    d = np.load(npz_path, allow_pickle=True)
    local = np.asarray(d["local_rot_mats"], dtype=np.float64)      # (T, J, 3, 3)
    posed = np.asarray(d["posed_joints"], dtype=np.float64)        # (T, J, 3)
    T, J = local.shape[0], local.shape[1]
    if len(names) != J:
        return ("error", "skeleton has %d joints, motion has %d" % (len(names), J))

    # The unit check. Kimodo is metres; a height outside a person means it is not.
    height = float(posed[:, :, 1].max() - posed[:, :, 1].min())
    if not (MIN_HUMAN_M <= height <= MAX_HUMAN_M):
        return ("error", "motion spans %.2f in y, which is not a person in metres" % height)

    root_t = posed[:, 0, :]                                        # root translation per frame

    stage = Usd.Stage.CreateNew(usd_path)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(T - 1)
    stage.SetTimeCodesPerSecond(30.0)

    root = UsdSkel.Root.Define(stage, "/Motion")
    skel = UsdSkel.Skeleton.Define(stage, "/Motion/Skeleton")
    paths = joint_paths(names, parents)
    skel.GetJointsAttr().Set(paths)

    # Rest pose from the shipped T-pose: each joint sits at its offset inside its parent.
    rest = []
    for i in range(J):
        m = Gf.Matrix4d(1.0)
        m.SetTranslateOnly(Gf.Vec3d(*offsets[i].tolist()))
        rest.append(m)
    skel.GetRestTransformsAttr().Set(rest)

    # Bind transforms are the world rest pose, so accumulate down the chain.
    world = []
    for i in range(J):
        m = Gf.Matrix4d(rest[i])
        p = parents[i]
        if p >= 0:
            m = m * world[p]
        world.append(m)
    skel.GetBindTransformsAttr().Set(world)

    anim = UsdSkel.Animation.Define(stage, "/Motion/Skeleton/Anim")
    anim.GetJointsAttr().Set(paths)
    quats = rot_to_quat(local)                                     # (T, J, 4) as w,x,y,z

    for f in range(T):
        t = Usd.TimeCode(f)
        rots = Vt.QuatfArray([Gf.Quatf(float(q[0]), Gf.Vec3f(float(q[1]), float(q[2]), float(q[3])))
                              for q in quats[f]])
        anim.GetRotationsAttr().Set(rots, t)
        # Gf takes Python floats. A numpy scalar picks no overload and fails here.
        trans = [Gf.Vec3f(*offsets[i].tolist()) for i in range(J)]
        trans[0] = Gf.Vec3f(*root_t[f].tolist())                   # only the root travels
        anim.GetTranslationsAttr().Set(Vt.Vec3fArray(trans), t)
        anim.GetScalesAttr().Set(Vt.Vec3hArray([Gf.Vec3h(1.0, 1.0, 1.0)] * J), t)

    UsdSkel.BindingAPI.Apply(skel.GetPrim()).CreateAnimationSourceRel().SetTargets([anim.GetPath()])
    stage.SetDefaultPrim(root.GetPrim())

    # Contacts ride along as custom data. They are measured, not derived, and the O3DE clips
    # have no equivalent, so losing them here would mean deriving them again later.
    if "foot_contacts" in d.files:
        fc = np.asarray(d["foot_contacts"]).astype(np.float32)
        a = skel.GetPrim().CreateAttribute("weft:footContacts", Sdf.ValueTypeNames.FloatArray)
        for f in range(T):
            a.Set(Vt.FloatArray(fc[f].tolist()), Usd.TimeCode(f))

    stage.GetRootLayer().Save()
    return ("ok", {"frames": T, "joints": J, "height_m": height})


def verify(usd_path, npz_path):
    """Read the stage back and check the unit, the frame count, and the root path."""
    from pxr import Usd, UsdGeom, UsdSkel

    stage = Usd.Stage.Open(usd_path)
    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    if abs(mpu - 1.0) > 1e-9:
        return ("error", "metersPerUnit is %r" % mpu)

    skel = UsdSkel.Skeleton(stage.GetPrimAtPath("/Motion/Skeleton"))
    anim = UsdSkel.Animation(stage.GetPrimAtPath("/Motion/Skeleton/Anim"))
    if not skel or not anim:
        return ("error", "skeleton or animation missing")

    d = np.load(npz_path, allow_pickle=True)
    posed = np.asarray(d["posed_joints"])
    T = posed.shape[0]
    if int(stage.GetEndTimeCode()) != T - 1:
        return ("error", "stage covers %d frames, motion has %d" % (int(stage.GetEndTimeCode()) + 1, T))

    # The root translation must survive exactly; it is what carries the character.
    got = np.array([list(anim.GetTranslationsAttr().Get(Usd.TimeCode(f))[0]) for f in (0, T // 2, T - 1)])
    want = posed[[0, T // 2, T - 1], 0, :]
    err = float(np.abs(got - want).max())
    if err > 1e-4:
        return ("error", "root translation off by %.3g m" % err)

    travel = float(np.linalg.norm(want[-1][[0, 2]] - want[0][[0, 2]]))
    return ("ok", {"metersPerUnit": mpu, "frames": T, "joints": len(skel.GetJointsAttr().Get()),
                   "root_err_m": err, "travel_m": travel})


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    src = argv[1]
    dst = argv[2] if len(argv) > 2 else src.replace(".npz", ".usda")
    if os.path.exists(dst):
        os.remove(dst)
    tag, val = convert(src, dst)
    if tag == "error":
        print("  convert FAILED: %s" % val)
        return 1
    tag, v = verify(dst, src)
    if tag == "error":
        print("  VERIFY FAILED: %s" % v)
        return 1
    print("  %-34s %4d frames  %d joints  height %.2f m  travel %.2f m  root err %.1g"
          % (os.path.basename(dst), v["frames"], v["joints"], val["height_m"], v["travel_m"], v["root_err_m"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
