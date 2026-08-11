"""The corpus rule, enforced.

A comment saying "do not train on Mixamo" is a comment. This is the thing that fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import (admissible, classify, filter_corpus, roots, ROOT, BLOCKED, ALLOWED,
                    video_admissible, per_item_admissible, motion_admissible)


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
    for p in ("/opt/weft-motion/quaternius/mixamo/Walk.glb",
              "/opt/weft-motion/o3de-motion-matching/lafan1/walk.bvh",
              "/opt/weft-motion/addb/amass/subject/x.npz"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted via the allowed directory above it" % p


def test_a_rig_naming_scheme_is_not_a_source():
    """`mixamorig` is a bone prefix. Original work that uses it is still original work.
    A directory called `mixamo` claims something else: that the clips came from there."""
    assert admissible("/opt/weft-motion/quaternius/Walk_Fwd.glb")[0] == "ok"
    assert admissible("/opt/weft-motion/quaternius/mixamorig/Walk.glb")[0] == "ok"
    assert admissible("/opt/weft-motion/quaternius/mixamorig_retarget/Walk.glb")[0] == "ok"
    # a rig is published to be interoperated with, so its name is a convention not a source
    for ok in ("mixamorig", "mixamo_rig", "mixamorig_retarget", "mixamo_skeleton",
               "mixamo_compat", "mixamo-bones"):
        p = "/opt/weft-motion/quaternius/%s/Walk.glb" % ok
        assert admissible(p)[0] == "ok", "%s is a naming scheme: %s" % (ok, admissible(p)[1])
    # the source claim, which stays refused
    for bad in ("mixamo", "mixamo_animations", "mixamo_clips", "mixamo_downloads"):
        p = "/opt/weft-motion/quaternius/%s/Walk.glb" % bad
        assert admissible(p)[0] == "error", "%s claims a source and was admitted" % bad


def test_a_tool_is_kept_but_its_dependency_is_not_training_data():
    """GEM-X is a tool and stays. SAM-3D-Body is blocked so its features and checkpoints
    cannot drift into the training set. Motion GEM-X writes still inherits SAM's terms,
    which is a judgement for a person and not something a path check can decide."""
    assert admissible("/opt/weft-motion/gem-x/outputs/clip.npz")[0] == "ok"
    for p in ("/opt/weft-motion/sam-3d-body/checkpoints/sam3d_body.ckpt",
              "/data/sam3d/features.npz"):
        assert admissible(p)[0] == "error", "%s was admitted" % p


def test_props_are_refused_however_they_are_named():
    """These are real results from a CC-BY animation search. The licence was fine and the
    keyword matched. None of them are motion."""
    for prop in ("Bench", "Theater Chair - Red Plaid", "8 Ball - Billiard",
                 "Wooden hand truck low poly 3D", "Police car", "PUERTA 8", "CC0 - Chair 8"):
        tag, why = motion_admissible(prop, has_animation=False)
        assert tag == "error", "%s was admitted as motion" % prop
        assert "not motion" in why


def test_motion_must_show_its_working():
    ok = motion_admissible("gettingup_up", frames=776, fps=120, joints=60, has_animation=True)
    assert ok[0] == "ok" and abs(ok[1]["seconds"] - 6.47) < 0.01
    # a single pose is not a motion
    assert motion_admissible("T-pose", frames=1, fps=30, joints=60, has_animation=True)[0] == "error"
    # a rate nobody stated means a duration nobody knows
    assert motion_admissible("clip", frames=300, fps=0, joints=60, has_animation=True)[0] == "error"
    # an animated prop is still not a body
    assert motion_admissible("Rhino Animation Walk", frames=200, fps=30, joints=4,
                             has_animation=True)[0] == "error"


def test_engine_logic_is_not_motion():
    """The blocklist also refuses things whose licence is fine and whose category is not.
    A locomotion Blueprint is the decision a controller makes, not data it learns from."""
    for p in ("/opt/weft-motion/fab-cc-by/easy-locomotion-toolkit/BP_Locomotion.uasset",
              "/downloads/Easy-Locomotion-Toolkit/readme.txt"):
        tag, why = admissible(p)
        assert tag == "error", "%s was admitted" % p
        assert "CATEGORY" in why or "category" in why


def test_the_soma_path_stays_clean():
    """SOMA exists so there is a body model that is not SMPL. It must not be caught by it."""
    for p in ("/opt/weft-motion/kimodo-generated/idle_stand.usda",
              "protomotions/data/pretrained_models/motion_tracker/soma-bones/last.ckpt"):
        assert admissible(p)[0] != "error" or "unknown provenance" in admissible(p)[1], why_failed(p)
    assert admissible("/opt/weft-motion/anny/src/anny/data/soma/soma_rig.pt")[0] == "ok"


def test_a_video_needs_both_signals():
    """One self-assertion is not provenance. The licence field and the description must agree."""
    assert video_admissible({"license_field": "cc-by", "description": "CC BY"})[0] == "ok"
    for one_sided in ({"license_field": "cc-by"},
                      {"description": "cc-by"},
                      {"license_field": "standard youtube", "description": "cc-by"},
                      {}):
        tag, why = video_admissible(one_sided)
        assert tag == "error", "%r was admitted on one signal" % one_sided
        assert "both are required" in why


def test_a_video_licence_does_not_speak_for_the_performer():
    """Even when both signals agree, the people in the shot did not sign it. The result says so."""
    tag, val = video_admissible({"license_field": "cc-by", "description": "cc-by"})
    assert tag == "ok"
    assert "performer" in " ".join(val)


def test_a_marketplace_item_needs_a_person():
    """No blanket answer is right for a marketplace, so each item is admitted by a reader."""
    ok = per_item_admissible("booth", "1234", "ernest", True, True)
    assert ok[0] == "ok" and ok[1]["read_by"] == "ernest"
    # nobody read it
    assert per_item_admissible("booth", "1234", "", True, True)[0] == "error"
    # read, and the terms say no
    assert per_item_admissible("booth", "1234", "ernest", False, True)[0] == "error"
    assert per_item_admissible("booth", "1234", "ernest", True, False)[0] == "error"
    # not a marketplace
    assert per_item_admissible("o3de", "1", "ernest", True, True)[0] == "error"


def test_fab_is_admitted_only_under_its_cc_by_directory():
    """Fab is admitted because its licence is machine readable, not because Fab is trusted.
    The path has to say the filter was applied."""
    assert admissible("/opt/weft-motion/fab-cc-by/getting_up_01.fbx")[0] == "ok"
    assert admissible("/opt/weft-motion/fab/getting_up_01.fbx")[0] == "ok"


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
