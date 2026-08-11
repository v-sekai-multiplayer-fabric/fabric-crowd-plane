#!/usr/bin/env python3
"""What a controller can ask for, in the order it asks.

The corpus was being filled by what was interesting to generate rather than by what a
player can press, and those are not the same list. A gamepad emits a stick vector, a
look vector, and a few buttons. A VR rig emits a head pose and two hand poses. **Neither
has a button for getting up off the floor.** Rank by what the input surface can produce
and the list reorders hard.

    python rank.py            # the ranked surface and what covers each row
"""
import argparse
import glob
import os
import sys

# rank, name, what the player does, and why it is at that rank.
SURFACE = [
    (1, "stand idle", "stick centred",
     "the default. A social crowd stands still most of the time, so a body that cannot "
     "hold a still stand is broken in the most visible way possible"),
    (2, "walk, any heading", "stick partly deflected",
     "the single most pressed input in any social space"),
    (3, "turn in place", "look axis, stick centred",
     "constant in conversation, and the pose the camera sees most"),
    (4, "start, stop, change direction", "stick moving",
     "the transitions between 1 to 3. A crowd is judged on these, not on the steady states"),
    (5, "recover from a push", "no input at all",
     "THE product. `plane.cpp` says bodies that push each other, so this is the one "
     "behaviour the demo exists to show, and it is not a command"),
    (6, "run", "stick fully deflected",
     "same axis as walking, higher speed"),
    (7, "jump", "a button",
     "one button, and the landing matters more than the launch"),
    (8, "crouch", "a button",
     "held stance change, rare in social use"),
    (9, "sit down and stand up", "an interaction button, at a prop",
     "needs a prop in the scene to mean anything, and there is no seat in the deployed room"),
    (10, "get up off the floor", "NOTHING",
     "no controller has this input. It only happens after a fall, so it belongs to row 5 "
     "as a recovery, not to the command surface at all"),
]

# What each row is covered by today, and whether that source is on disk.
COVER = {
    1: [("100STYLE ID", "100style/usd/*_ID.usda"), ("generated idle_stand", None)],
    2: [("100STYLE FW", "100style/usd/*_FW.usda"), ("100STYLE BW", "100style/usd/*_BW.usda"),
        ("100STYLE SW", "100style/usd/*_SW.usda")],
    3: [("100STYLE TR", "100style/usd/*_TR*.usda")],
    4: [("100STYLE TR", "100style/usd/*_TR*.usda")],
    5: [("VR Balance Disturbance", "vr-balance/**/*")],
    6: [("100STYLE FR", "100style/usd/*_FR.usda"), ("100STYLE BR", "100style/usd/*_BR.usda"),
        ("100STYLE SR", "100style/usd/*_SR.usda")],
    7: [("generated jump", None)],
    8: [("generated crouch", None)],
    9: [("generated sit", None), ("props, built but not in a scene", "../weft-props/usd/*.usda")],
    10: [("Klian, real capture, 12.2 s", "fab-cc-by/*ettingup*")],
}

ROOT = "/opt/weft-motion"


def count(pattern):
    if pattern is None:
        return None
    return len(glob.glob(os.path.join(ROOT, pattern), recursive=True))


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print("%-4s %-28s %-34s %s" % ("rank", "what the player does", "the input", "on disk"))
    for r, name, inp, _why in SURFACE:
        cov = []
        for label, pat in COVER[r]:
            n = count(pat)
            cov.append("%s%s" % (label, "" if n is None else " (%d)" % n))
        print("%-4d %-28s %-34s %s" % (r, name, inp, ", ".join(cov)))
    print()
    print("why the order is this order")
    for r, name, _inp, why in SURFACE:
        print("  %2d %-26s %s" % (r, name, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
