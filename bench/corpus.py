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

# Blocked, with the reason attached. A name without a reason is a name nobody can re-argue.
BLOCKED = {
    "mixamo": "Terms cover use of the animations in a project. A trained policy carries the "
              "corpus in its weights and is redistributed, which is not the same thing.",
}

# Allowed, with what makes the provenance checkable.
ALLOWED = {
    "addb": "AddBiomechanics. Per-study provenance, each subject traceable to its paper.",
    "o3de": "Open 3D Engine motion matching demo data, Linux Foundation, Apache-2.0. "
            "Reached weft through godot-motion-matching-demo, which credits it.",
    "mmdemo": "godot-motion-matching-demo. Carries the o3de clips and nothing else. "
              "Confirm against the Gem's own licence header before shipping a policy.",
}


def classify(path):
    """Name the source a path belongs to.

    Matching is on path components, not on a substring of the whole path. A directory called
    `mixamo_conversions` is the same source. A user called `maximo` is not.
    """
    parts = [p.lower() for p in os.path.normpath(path).split(os.sep) if p]
    for p in parts:
        for name in BLOCKED:
            if name in p:
                return ("ok", name)
        for name in ALLOWED:
            if p == name or p.startswith(name + "_"):
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
