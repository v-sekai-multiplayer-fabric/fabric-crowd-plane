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
    "quaternius": "Quaternius Universal Animation Library, CC0 1.0. Public domain, so there "
                  "is nothing to inherit and nothing to attribute. 120+ animations at 30 fps "
                  "on a retargetable humanoid rig, with root motion on all locomotion. Its "
                  "rig is described as compatible with other rigs including Mixamo, which is "
                  "a naming convention and not a source: the animations are original.",
}


def classify(path):
    """Name the source a path belongs to.

    Matching is on path components, not on a substring of the whole path. A directory called
    `mixamo_conversions` is the same source. A user called `maximo` is not.
    """
    parts = [p.lower() for p in os.path.normpath(path).split(os.sep) if p]

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
