"""Which motion may train a controller, and which may not.

A corpus decision is easy to make once and then lose. The clips sit in a directory, somebody
adds a directory beside them, and six weeks later nobody can say what a shipped policy
learned from. So the rule lives here as data, and `test_corpus.py` fails if it is broken.

Blocked sources are blocked for provenance, not for quality. weft ships a trained policy,
which means the corpus travels inside the weights. A source whose terms cover use inside a
project does not automatically cover that.

Return values are `("ok", value)` or `("error", reason)`. Nothing here raises.
"""
import os

# Where a corpus lives on a machine that has one. It is on `/` and not on `/tmp`, because a
# session scratchpad is tmpfs and a corpus that only exists in RAM is one reboot from gone.
ROOT = "/opt/weft-motion"

# Blocked, with the reason attached. A name without a reason is a name nobody can re-argue.
BLOCKED = {
    "mixamo": "Terms cover use of the animations in a project. A trained policy carries the "
              "corpus in its weights and is redistributed, which is not the same thing.",
    # The next three are one restriction wearing three names. SMPL's licence says, in its own
    # words, that it "prohibits the use of the Software to train methods/algorithms/neural
    # networks/etc. for commercial use of any kind". AMASS carries the identical sentence.
    # Anything built on either inherits it, whatever licence the builder puts on top.
    "smpl": "Max Planck body model. Its licence bans training a network for commercial use "
            "of any kind, in those words. SMPL-X and SMPL+H are the same licence.",
    "amass": "Max Planck motion corpus, same clause as SMPL. HumanML3D is derived from it, "
             "so every model trained on HumanML3D inherits the ban: MDM, MoMask, MotionGPT, "
             "T2M-GPT, MotionLCM, StableMoFusion.",
    "humenv": "Meta HumEnv and Meta Motivo, CC BY-NC 4.0. The body is SMPL-derived and the "
              "motions are AMASS, so the non-commercial term is inherited and Meta could not "
              "have granted otherwise. Closest match to our topology and still unusable.",
    "cmu": "CMU Graphics Lab motion capture. Its terms permit inclusion in a commercial "
           "product but forbid reselling the data directly, even in converted form. A "
           "shipped policy carries the corpus in its weights, and whether that is the data "
           "in converted form is not a question to answer optimistically. Blocked.",
    "lafan": "Ubisoft La Forge Animation dataset, CC BY-NC-ND 4.0. NoDerivatives is stricter "
             "than the SMPL clause: a retarget is a derivative. Most of the motion matching "
             "ecosystem is built on it under an MIT badge that covers only the code, "
             "including orangeduck/Motion-Matching and bevy_motion_matching.",
    "ubisoft": "Same corpus as lafan, under the name it is usually shipped as. "
               "`assets/ubisoft_bvh` inside an MIT repository is still CC BY-NC-ND.",
    "bandai": "Bandai Namco Research motion datasets 1 and 2, CC BY-NC 4.0. Only the Blender "
              "visualisation utility beside them is MIT.",
    "easy-locomotion-toolkit": "Unreal Engine Blueprint locomotion system, CC BY 4.0 and "
        "free. Blocked on CATEGORY and not on licence, which makes it the first entry here "
        "that is not a licensing decision. It ships no motion: it is the logic that decides "
        "which animation to play, which is the thing weft is training a policy to do. It "
        "surfaced in a Fab search under a locomotion keyword the same way a theatre chair "
        "surfaced under `sitting`, and it was briefly reported as a find. Blocking it keeps "
        "the next reader from repeating that.",
    "sam": "Meta SAM-3D-Body, under the custom SAM License. It carries no non-commercial "
           "clause, so it is not blocked for that. It is blocked because the licence is "
           "bespoke and not OSI approved, and it adds trade control and ITAR terms, a "
           "patent grant that terminates on litigation, and an obligation to indemnify "
           "Meta. Those travel with anything built on it.",
}

# Allowed, with what makes the provenance checkable.
ALLOWED = {
    "addb": "AddBiomechanics. Per-study provenance, each subject traceable to its paper.",
    "o3de": "Open 3D Engine motion matching demo data, Linux Foundation, Apache-2.0. "
            "Reached weft through godot-motion-matching-demo, which credits it.",
    "mmdemo": "godot-motion-matching-demo. Carries the o3de clips and nothing else. "
              "Confirm against the Gem's own licence header before shipping a policy.",
    "anny": "Anny, NAVER, Apache-2.0. Not motion but the SOMA rig and rest pose. It is "
            "declared here because a retarget built on it carries it into the output, so "
            "its terms travel with a shipped policy exactly as a clip's do.",
    "kimodo": "Kimodo, NVIDIA. Apache-2.0 code, NVIDIA Open Model Licence weights, trained "
              "on commercially-friendly capture and emitting somaskel77. Covers the "
              "checkout, the generated clips, and the corpus built from them.",
    "text-encoders": "Llama-3-8B-Instruct weights from an ungated mirror plus the open "
                     "LLM2Vec adapters. Meta's Llama 3 Community Licence applies. It "
                     "conditions generation, so its terms reach the output.",
    "hf-cache": "Hugging Face download cache. Holds copies of the above and nothing whose "
                "terms are not already recorded here.",
    "gem-x": "NVIDIA GEM-X, Apache-2.0. A TOOL and not a corpus: it turns video we hold "
             "rights to into 77-joint SOMA motion, so nothing about it is a source of "
             "motion by itself. It is kept and it is usable. What it cannot do quietly is "
             "launder its dependency: its model takes video features from SAM-3D-Body as a "
             "required input, so motion it produces carries the SAM License terms, and that "
             "needs reading before any of it trains a policy weft ships. `sam` stays "
             "blocked so the features and checkpoints cannot become training data by "
             "accident.",
    "fab": "Fab.com CC-BY listings only. Unlike a marketplace with free-text author terms, "
           "Fab exposes a machine readable licence on each listing, so the filter is "
           "checkable rather than trusted: `licenses=cc-by` on `/i/listings/search`, and the "
           "listing carries `licenses[].name` and `isCc0`. Note the plural. `license=cc-by` "
           "is accepted and silently ignored, which returns the unfiltered catalogue looking "
           "like a filtered one. Downloads need an Epic account.",
    "quaternius": "Quaternius Universal Animation Library, CC0 1.0. Public domain, so there "
                  "is nothing to inherit and nothing to attribute. 120+ animations at 30 fps "
                  "on a retargetable humanoid rig, with root motion on all locomotion. Its "
                  "rig is described as compatible with other rigs including Mixamo, which is "
                  "a naming convention and not a source: the animations are original.",
}


# A video is admissible only when TWO independent things say so. The licence field that the
# search filter reads is one, and the uploader's own description is the other. Either alone
# is a single self-assertion by someone who may not hold the rights, and a mismarked tag is
# worse than no tag because it looks like consent. Requiring both does not make the uploader
# right, but it makes a careless tag much less likely to be the only evidence.
#
# The performer is a separate question from the recording. A licence on the video is granted
# by whoever uploaded it, and the people in it did not sign it. Extracting joint angles is
# not a likeness, but that is reasoning and not settled ground, so the check records what was
# relied on rather than pretending the question was answered.
VIDEO_SIGNALS = ("license_field", "description")

# A marketplace is not a source. Booth.pm is ten thousand authors who each wrote their own
# terms, usually in Japanese, usually forbidding redistribution. There is no blanket licence
# to check and so no entry in either dict above can be right: a rule that blanket-allowed it
# would admit items that forbid this, and one that blanket-blocked it would refuse an author
# who explicitly permits it. Items from a marketplace are admissible only one at a time, by a
# person who read that item's terms, and the reading gets recorded.
PER_ITEM = {
    "booth": "Booth.pm. Per-item author-written terms. Predominantly avatars and clothing "
             "rather than motion, so it is unlikely to be the answer to a corpus question "
             "even where an item permits use.",
}


def motion_admissible(name, frames=0, fps=0, joints=0, has_animation=False):
    """Whether a candidate is motion at all, before anyone asks whose it is.

    A licence filter answers who owns a thing. It does not answer what the thing is, and the
    Fab sweep showed how far apart those are: under a CC-BY filter, `sitting` returned benches
    and theatre chairs, `strafe` returned an 8 ball and a door, `push` returned a hand truck
    and a police car. Eighty hits, almost none of them motion. The filter matched the licence
    and the keyword matched the title, and nothing checked the middle.

    Enumerating props is unwinnable, so this defaults to no. A candidate is motion when it
    demonstrates motion: animation tracks, a frame count, a rate, and joints. Anything that
    cannot show those is refused whatever its name suggests.
    """
    if not has_animation:
        return ("error", "%s declares no animation, so it is a model and not motion" % name)
    if frames < 2:
        return ("error", "%s has %d frames; a pose is not a motion" % (name, frames))
    if fps <= 0:
        return ("error", "%s states no frame rate, so its duration is unknown" % name)
    if joints < 8:
        return ("error", "%s has %d joints, too few to be a body" % (name, joints))
    return ("ok", {"name": name, "seconds": frames / float(fps), "joints": joints})


def per_item_admissible(source, item_id, terms_read_by, permits_training, permits_redistribution):
    """Admit one marketplace item, and record who read the terms.

    `terms_read_by` is a person. There is no default and no automatic pass, because the
    thing being checked is whether somebody actually read it.
    """
    if source not in PER_ITEM:
        return ("error", "%s is not a per-item source; use admissible()" % source)
    if not terms_read_by:
        return ("error", "nobody is recorded as having read the terms for %s/%s" % (source, item_id))
    if not permits_training:
        return ("error", "%s/%s does not permit training" % (source, item_id))
    if not permits_redistribution:
        return ("error", "%s/%s forbids redistribution, and a shipped policy carries its "
                         "corpus in the weights" % (source, item_id))
    return ("ok", {"source": source, "item": item_id, "read_by": terms_read_by})


def video_admissible(signals):
    """`signals` is what was actually observed, e.g. {"license_field": "cc-by", ...}."""
    seen = [k for k in VIDEO_SIGNALS if str(signals.get(k, "")).lower().replace(" ", "")
            in ("ccby", "cc-by", "creativecommons", "cc-by-4.0", "ccby4.0")]
    if len(seen) < len(VIDEO_SIGNALS):
        missing = [k for k in VIDEO_SIGNALS if k not in seen]
        return ("error", "CC-BY asserted by %s but not by %s; both are required"
                % (seen or ["nothing"], missing))
    return ("ok", {"signals": seen, "performer_rights": "not established by the video licence"})


def classify(path):
    """Name the source a path belongs to.

    Matching is on path components, not on a substring of the whole path. A directory called
    `mixamo_conversions` is the same source. A user called `maximo` is not.
    """
    parts = [p.lower() for p in os.path.normpath(path).split(os.sep) if p]

    # A naming scheme is not a source. `mixamorig` is a bone prefix, and a rig is published
    # precisely so other people interoperate with it, so its name appearing in a path says
    # which convention the bones follow, not where the motion came from. Blocking that would
    # refuse original work for speaking a standard, which is what a standard is for.
    #
    # A directory called `mixamo` or `mixamo_animations` is a different claim: that is where
    # the clips landed. The word after the source name is what separates the two.
    RIG_WORDS = ("rig", "rigged", "skeleton", "skel", "bones", "naming", "compat",
                 "compatible", "convention", "mapping", "retarget")

    def is_naming_scheme(component):
        for src in BLOCKED:
            if not component.startswith(src):
                continue
            tail = component[len(src):].lstrip("_-")
            if tail.startswith("rig"):            # mixamorig, mixamo_rig, mixamorig_retarget
                return True
            if tail in RIG_WORDS:
                return True
        return False

    parts = [p for p in parts if not is_naming_scheme(p)]

    # Blocked wins wherever it appears. Scanning for allowed first, component by component,
    # admitted `quaternius/mixamo_rig/Walk.glb`: the allowed directory matched before the
    # blocked one was ever reached. A blocked source nested inside an allowed one is exactly
    # how a corpus goes wrong, so the whole path is checked for blocked names first.
    for p in parts:
        for name in BLOCKED:
            if name in p:
                return ("ok", name)

    for p in parts:
        for name in ALLOWED:
            # A delivery names itself after its source and then adds to it, with either
            # separator: `o3de-motion-matching`, `addb_v2`. The bare name counts too.
            if p == name or p.startswith(name + "_") or p.startswith(name + "-"):
                return ("ok", name)
    return ("error", "no known source in %r" % path)


def admissible(path):
    """Whether a clip at this path may be used to train something weft ships."""
    tag, val = classify(path)
    if tag == "error":
        return ("error", "unknown provenance: %s" % val)
    if val in BLOCKED:
        return ("error", "%s is blocked: %s" % (val, BLOCKED[val]))
    return ("ok", val)


def roots():
    """The corpus directories on this machine, each with the source it holds."""
    found = []
    for name in sorted(ALLOWED):
        d = os.path.join(ROOT, name)
        if os.path.isdir(d):
            found.append((name, d))
    # o3de arrives under a directory naming its delivery, not the source.
    d = os.path.join(ROOT, "o3de-motion-matching")
    if os.path.isdir(d):
        found.append(("o3de", d))
    return ("ok", found)


def filter_corpus(paths):
    """Split paths into the ones that may train and the ones that may not, with reasons."""
    keep, drop = [], []
    for p in paths:
        tag, val = admissible(p)
        if tag == "ok":
            keep.append(p)
        else:
            drop.append((p, val))
    return ("ok", (keep, drop))
