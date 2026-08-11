"""The corpus rule, enforced.

A comment saying "do not train on Mixamo" is a comment. This is the thing that fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import admissible, classify, filter_corpus, roots, ROOT, BLOCKED, ALLOWED


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


def test_a_delivery_may_extend_its_source_name():
    """`o3de-motion-matching` is o3de. This is how the corpus is laid out on disk."""
    for p, want in (("/opt/weft-motion/o3de-motion-matching/Walk1.res", "o3de"),
                    ("/opt/weft-motion/addb/train/x.b3d", "addb"),
                    ("/opt/weft-motion/addb_v2/x.b3d", "addb")):
        tag, val = admissible(p)
        assert tag == "ok", why_failed(p)
        assert val == want, "%s classified as %s" % (p, val)


def test_the_smpl_family_is_refused():
    """One restriction under several names. Each must be caught by the name it arrives under."""
    for p in ("/data/smpl/SMPL_NEUTRAL.pkl",
              "/data/amass/CMU/01/01_01_poses.npz",
              "models/humenv/assets/robot.xml",
              "protomotions/data/pretrained_models/motion_tracker/smpl/last.ckpt"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted" % p


def test_the_motion_matching_datasets_are_refused():
    """An MIT repository is not an MIT corpus. These all ship someone else's mocap."""
    for p in ("/data/lafan1/walk1_subject2.bvh",
              "Motion-Matching/resources/database.bin".replace("Motion-Matching", "lafan1_derived"),
              "bevy_motion_matching/assets/ubisoft_bvh/walk1_subject1.bvh",
              "/data/bandai-namco-research-motiondataset-1/walk.bvh",
              "/data/cmu/subjects/01/01_01.amc"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted" % p


def test_blocked_nested_inside_allowed_is_still_blocked():
    """The order the path is scanned in must not decide the answer."""
    for p in ("/opt/weft-motion/quaternius/mixamo_rig/Walk.glb",
              "/opt/weft-motion/o3de-motion-matching/lafan1/walk.bvh",
              "/opt/weft-motion/addb/amass/subject/x.npz"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted via the allowed directory above it" % p


def test_a_mixamo_compatible_rig_is_not_mixamo():
    """Quaternius says its rig is Mixamo-compatible. That is a bone naming scheme, not a
    source. But a path that names mixamo is still refused, because the rule matches on the
    path and a file that says mixamo cannot be told apart from one that is."""
    assert admissible("/opt/weft-motion/quaternius/Walk_Fwd.glb")[0] == "ok"
    assert admissible("/opt/weft-motion/quaternius/mixamo_rig/Walk.glb")[0] == "error"


def test_the_soma_path_stays_clean():
    """SOMA exists so there is a body model that is not SMPL. It must not be caught by it."""
    for p in ("/opt/weft-motion/kimodo-generated/idle_stand.usda",
              "protomotions/data/pretrained_models/motion_tracker/soma-bones/last.ckpt"):
        assert admissible(p)[0] != "error" or "unknown provenance" in admissible(p)[1], why_failed(p)
    assert admissible("/opt/weft-motion/anny/src/anny/data/soma/soma_rig.pt")[0] == "ok"


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


def test_nothing_blocked_lives_in_the_corpus_root():
    """The corpus directory is what a training run reads. Nothing blocked may be inside it."""
    if not os.path.isdir(ROOT):
        return
    for name, d in roots()[1]:
        assert admissible(os.path.join(d, "x"))[0] == "ok", "%s is a corpus root but not admitted" % d
    # __pycache__ is the interpreter's, not a corpus.
    bad = [e for e in os.listdir(ROOT)
           if os.path.isdir(os.path.join(ROOT, e)) and e != "__pycache__"
           and admissible(os.path.join(ROOT, e, "x"))[0] != "ok"]
    assert not bad, ("undeclared directories in the corpus root: %s. Every directory here "
                     "must name its source in corpus.py, because a policy trained from this "
                     "root carries all of it." % bad)


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
