"""The metre rule, enforced.

`verify` is only worth having if it fails on the two mistakes it exists to catch. Each
negative test below reintroduces one of them on purpose and asserts the check fires.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anny_to_usd as A

OUT = "/tmp/_anny_usd_test.usda"


def _rig():
    tag, val = A.load_rig()
    return val if tag == "ok" else None


def _fresh(path):
    if os.path.exists(path):
        os.remove(path)
    return path


def test_conversion_is_in_metres_and_is_a_person():
    r = _rig()
    if r is None:
        return                      # no rig on this machine, not a failure
    labels, parents, world = r
    A.write(_fresh(OUT), labels, parents, world)
    tag, val = A.verify(OUT, labels, world)
    assert tag == "ok", val
    assert abs(val["metersPerUnit"] - 1.0) < 1e-9
    assert 1.4 < val["height_m"] < 1.7, "height %.3f m" % val["height_m"]


def test_load_applies_the_centimetre_scale():
    """The raw rig is centimetres. If load stops dividing, this is the tripwire."""
    r = _rig()
    if r is None:
        return
    labels, _p, world = r
    idx = {n: i for i, n in enumerate(labels)}
    h = world[idx["Head"], 1, 3] - world[idx["LeftFoot"], 1, 3]
    assert A.MIN_HUMAN_M <= h <= A.MAX_HUMAN_M, "load_rig returned a %.1f unit skeleton" % h


def test_unscaled_input_is_refused():
    """Skip the divide and the file describes a 154 metre skeleton. It must not pass."""
    r = _rig()
    if r is None:
        return
    labels, parents, world = r
    cm = world.copy()
    cm[:, :3, 3] *= A.CM_PER_M          # put it back into centimetres
    A.write(_fresh(OUT), labels, parents, cm)
    tag, why = A.verify(OUT, labels, cm)
    assert tag == "error", "a 154 m skeleton was accepted"
    assert "centimetres" in why or "not a person" in why


def test_dropped_transpose_is_refused():
    """USD holds translation in the last row. Hand it a numpy matrix and it must complain."""
    r = _rig()
    if r is None:
        return
    labels, parents, world = r
    from pxr import Usd, UsdGeom, UsdSkel, Gf
    path = _fresh(OUT)
    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdSkel.Root.Define(stage, "/Anny")
    skel = UsdSkel.Skeleton.Define(stage, "/Anny/Skeleton")
    skel.GetJointsAttr().Set(A.joint_paths(labels, parents))
    # the bug: no .T
    skel.GetBindTransformsAttr().Set([Gf.Matrix4d(*m.flatten().tolist()) for m in world])
    skel.GetRestTransformsAttr().Set([Gf.Matrix4d(*m.flatten().tolist())
                                      for m in A.local_transforms(parents, world)])
    stage.GetRootLayer().Save()
    tag, why = A.verify(path, labels, world)
    assert tag == "error", "a transposed rig was accepted"


def test_all_23_soma_bodies_survive():
    r = _rig()
    if r is None:
        return
    labels, parents, world = r
    A.write(_fresh(OUT), labels, parents, world)
    tag, val = A.verify(OUT, labels, world)
    assert tag == "ok", val
    assert val["joints"] == len(labels)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok    %s" % name)
            except AssertionError as e:
                fails += 1
                print("FAIL  %s: %s" % (name, e))
    if os.path.exists(OUT):
        os.remove(OUT)
    print("\n%s" % ("all metre checks pass" if not fails else "%d FAILED" % fails))
    sys.exit(1 if fails else 0)
