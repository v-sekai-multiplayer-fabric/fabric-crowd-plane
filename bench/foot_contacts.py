#!/usr/bin/env python3
"""Derive foot contacts for motion that does not carry them.

Motion matching uses foot contact as a feature, and so does every physics tracker: it is what
tells a controller when a foot may be trusted to bear load. Kimodo emits contacts. The O3DE
clips, 100STYLE, and the Fab USDZ do not, so the whole corpus disagrees about whether the
information exists at all.

The heuristic is NVIDIA's, from `kimodo/motion_rep/feet.py`, Apache-2.0: a foot is in contact
when it is low and slow. Their call uses 0.15 and 0.10 as thresholds. Two bare numbers is
exactly what this repo does not keep, so both are derived here instead:

- **Height.** A planted ankle sits at whatever height the skeleton's own rest pose puts it,
  so the threshold is that rest height plus a margin taken from the same skeleton, not from a
  constant. A short body and a tall one get different thresholds because they have different
  ankles.
- **Speed.** A foot is stationary when it is slow relative to the body's own motion, so the
  threshold is a fraction of the median root speed over the clip. A clip of someone standing
  and a clip of someone sprinting are then judged on their own terms.

The derivation is checked rather than trusted: Kimodo's clips carry contacts the model itself
produced, so running this over them and comparing is a measurement of how far the heuristic is
from the thing it approximates.

    python foot_contacts.py --usd FILE [--write]     one file, report or write back
    python foot_contacts.py --validate               against Kimodo's own contacts
"""
import argparse
import glob
import os
import sys

import numpy as np

# Which joints are feet, by the names the corpora actually use.
FOOT_NAMES = ("foot", "toe", "ankle", "heel", "ball", "calcn", "talus")


def joint_world_positions(usd_path):
    """World-space joint positions per frame, from a UsdSkel stage."""
    from pxr import Usd, UsdGeom, UsdSkel

    stage = Usd.Stage.Open(usd_path)
    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    skels = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
    if not skels:
        return ("error", "no skeleton in %s" % os.path.basename(usd_path))
    cache = UsdSkel.Cache()
    q = cache.GetSkelQuery(UsdSkel.Skeleton(skels[0]))
    if not q:
        return ("error", "no skel query")
    joints = [str(j).split("/")[-1] for j in q.GetJointOrder()]
    t0, t1 = int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode())
    fps = stage.GetTimeCodesPerSecond() or 30.0
    out = []
    for f in range(t0, t1 + 1):
        x = q.ComputeJointSkelTransforms(Usd.TimeCode(f))
        if not x:
            return ("error", "no transforms at frame %d" % f)
        out.append([[m[3][0], m[3][1], m[3][2]] for m in x])
    P = np.asarray(out, dtype=np.float64) * (mpu if mpu else 1.0)
    return ("ok", (P, joints, float(fps)))


def foot_indices(joints):
    idx = [i for i, n in enumerate(joints) if any(k in n.lower() for k in FOOT_NAMES)]
    left = [i for i in idx if "l" == joints[i].lower()[0] or "left" in joints[i].lower()
            or joints[i].lower().endswith("_l")]
    right = [i for i in idx if i not in left]
    return left[:2], right[:2], idx


def derive(P, joints, fps):
    """Contacts per frame, and the thresholds that produced them."""
    left, right, allf = foot_indices(joints)
    if not allf:
        return ("error", "no foot joints among %d named joints" % len(joints))

    # Height threshold from the skeleton's own resting ankle, not from a constant. The lowest
    # a foot joint ever gets is the floor for this body; a margin of one tenth of the body's
    # standing height covers the ankle sitting above the sole.
    ground = float(P[:, allf, 1].min())
    height = float(P[:, :, 1].max() - P[:, :, 1].min())
    h_thresh = ground + 0.10 * height

    # Speed threshold as a fraction of how fast this clip moves at all. A quarter of the
    # median joint speed separates a planted foot from a swinging one without naming a number
    # in metres per second, which would mean something different for a walk and a sprint.
    vel = np.linalg.norm(np.diff(P, axis=0), axis=-1) * fps          # (T-1, J)
    vel = np.vstack([vel, vel[-1:]])
    typical = float(np.median(vel[vel > 0])) if (vel > 0).any() else 1.0
    v_thresh = 0.25 * typical

    contacts = np.zeros((P.shape[0], 4), dtype=np.float32)
    for k, side in enumerate((left, right)):
        for j, ji in enumerate(side[:2]):
            low = P[:, ji, 1] < h_thresh
            slow = vel[:, ji] < v_thresh
            contacts[:, k * 2 + j] = np.logical_and(low, slow).astype(np.float32)
    return ("ok", (contacts, {"h_thresh": h_thresh, "v_thresh": v_thresh,
                              "ground": ground, "height": height,
                              "left": left, "right": right}))


def validate():
    """Compare the derivation against contacts Kimodo produced for the same motion."""
    files = sorted(glob.glob("/opt/weft-motion/kimodo-generated/*.npz"))
    if not files:
        print("  no kimodo clips to validate against")
        return 1
    print("%-18s %8s %8s %8s %8s" % ("clip", "agree", "theirs", "ours", "frames"))
    for f in files:
        d = np.load(f, allow_pickle=True)
        if "foot_contacts" not in d.files or "posed_joints" not in d.files:
            continue
        theirs = np.asarray(d["foot_contacts"], dtype=np.float32)
        if theirs.shape[-1] == 6:
            theirs = theirs[..., [0, 1, 3, 4]]
        P = np.asarray(d["posed_joints"], dtype=np.float64)
        # somaskel77 foot joints, by index: the converter's own name list gives them
        sys.path.insert(0, "/opt/weft-motion")
        from kimodo_to_usd import parse_bvh_hierarchy, TPOSE_BVH
        tag, val = parse_bvh_hierarchy(TPOSE_BVH)
        if tag == "error":
            print("  ", val); return 1
        names = val[0]
        tag, val = derive(P, names, 30.0)
        if tag == "error":
            print("  %-18s %s" % (os.path.basename(f), val)); continue
        ours = val[0]
        n = min(len(ours), len(theirs))
        agree = float((ours[:n] == theirs[:n]).mean())
        print("%-18s %7.1f%% %7.2f %7.2f %8d"
              % (os.path.basename(f)[:18], 100 * agree,
                 theirs[:n].mean(), ours[:n].mean(), n))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usd")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    if a.validate:
        return validate()
    if not a.usd:
        print(__doc__); return 2
    tag, val = joint_world_positions(a.usd)
    if tag == "error":
        print("  error:", val); return 1
    P, joints, fps = val
    tag, val = derive(P, joints, fps)
    if tag == "error":
        print("  error:", val); return 1
    contacts, info = val
    print("  %-34s %d frames  %.0f fps" % (os.path.basename(a.usd), len(contacts), fps))
    print("     feet: left %s right %s" % (info["left"], info["right"]))
    print("     height threshold %.3f m, speed threshold %.3f m/s, both derived"
          % (info["h_thresh"], info["v_thresh"]))
    print("     in contact: %.0f%% of frames, at least one foot down %.0f%%"
          % (100 * contacts.mean(), 100 * (contacts.max(axis=1) > 0).mean()))
    if a.write:
        from pxr import Usd, UsdSkel, Sdf, Vt
        stage = Usd.Stage.Open(a.usd)
        skel = [p for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)][0]
        attr = skel.CreateAttribute("weft:footContacts", Sdf.ValueTypeNames.FloatArray)
        for f in range(len(contacts)):
            attr.Set(Vt.FloatArray(contacts[f].tolist()), Usd.TimeCode(f))
        stage.GetRootLayer().Save()
        print("     written back as weft:footContacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
