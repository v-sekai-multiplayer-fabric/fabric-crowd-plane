"""The corpus rule, enforced.

A comment saying "do not train on Mixamo" is a comment. This is the thing that fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import admissible, classify, filter_corpus, BLOCKED, ALLOWED


def test_mixamo_is_refused():
    for p in ("/home/x/motion/mixamo/T-Pose/walk.bvh",
              "/data/Mixamo/run.bvh",
              "motion/mixamo_conversions/soma23/clip.pt"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted" % p
        assert "mixamo" in why


def test_addb_is_admitted():
    for p in ("/home/x/motion/addb/train/With_Arm/Han2023/subject1.b3d",
              "motion/addb/test/No_Arm/Li2021/s3.b3d"):
        tag, val = admissible(p)
        assert tag == "ok", why_failed(p)
        assert val == "addb"


def why_failed(p):
    return "%s: %s" % (p, admissible(p)[1])


def test_o3de_locomotion_is_admitted():
    """The motion matching clips are the turning and button data addb has none of."""
    for p in ("scratchpad/mmdemo/animation/animations/WalkTurns1.res",
              "/data/o3de/MotionMatching/Jumps1.res"):
        assert admissible(p)[0] == "ok", why_failed(p)


def test_unknown_provenance_is_refused():
    """A clip from nowhere is not admitted by default. Silence is not consent."""
    tag, why = admissible("/tmp/some_download/clip.bvh")
    assert tag == "error"
    assert "unknown provenance" in why


def test_a_near_name_is_not_a_false_positive():
    """`maximo` is a person's name, not the blocked source."""
    tag, _ = classify("/home/maximo/addb/train/x.b3d")
    assert admissible("/home/maximo/addb/train/x.b3d")[0] == "ok"


def test_every_blocked_name_carries_a_reason():
    for name, reason in BLOCKED.items():
        assert reason.strip(), "%s is blocked with no reason recorded" % name
    for name, reason in ALLOWED.items():
        assert reason.strip(), "%s is allowed with no provenance recorded" % name


def test_filter_reports_what_it_dropped():
    keep, drop = filter_corpus([
        "motion/addb/train/a.b3d",
        "motion/mixamo/b.bvh",
        "motion/addb/train/c.b3d",
    ])[1]
    assert len(keep) == 2
    assert len(drop) == 1
    assert "mixamo" in drop[0][1]


def test_the_real_corpus_on_this_machine_is_clean():
    """If the motion directory exists here, nothing blocked may be inside the training set."""
    root = os.path.expanduser("~/motion/addb")
    if not os.path.isdir(root):
        return                      # not this machine, and that is not a failure
    bad = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            if not f.endswith(".b3d"):
                continue
            if admissible(os.path.join(dirpath, f))[0] != "ok":
                bad.append(os.path.join(dirpath, f))
    assert not bad, "blocked clips inside the training corpus: %s" % bad[:5]


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
    print("\n%s" % ("all corpus checks pass" if not fails else "%d FAILED" % fails))
    sys.exit(1 if fails else 0)
