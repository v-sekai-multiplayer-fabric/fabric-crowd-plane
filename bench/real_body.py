#!/usr/bin/env python3
"""Build the avatar from measured anatomy instead of from round numbers.

The body in `assets/tracked_avatar.xml` was written by hand. Its segment lengths are round
numbers, every joint carries the same 300 N m, and its joint ranges are wider than a person's.
That last pair is the expensive one: a controller with superhuman arms that can also reach
poses a human cannot will find a strategy that works in simulation and looks wrong, and it
will not learn the foot placement that generalises because it never has to.

Three sources, each used only for what it actually measures.

**Anny** gives segment lengths. Its SOMA rig is a real human rig with a real rest pose.

**MS-Human-700** gives segment masses and joint ranges. It is an anatomical model, so its mass
distribution and its limits are measured rather than assumed. It is NOT used as the body: at
700 muscles and a 2 ms timestep it runs 4 bodies to a core against about 200 for capsules,
which is a fiftyfold capacity loss and the end of the product.

**The biomechanics literature** gives peak joint torque. MS-Human-700's own muscle sum is not
used for this, because summing every muscle at peak isometric force counts antagonists that
in reality oppose each other, and it comes out 1.5 to 4 times above measured human maxima.

Nothing here is a tuning constant. Every number is a measurement or a ratio of two.
"""
import sys

# Anny SOMA rest pose, metres. The rig is centimetres; these are already divided.
ANNY = {
    "thigh": 0.4330, "shin": 0.4242, "foot": 0.1413,
    "upper_arm": 0.2892, "forearm": 0.2703, "clavicle": 0.1574,
    "spine1": 0.0513, "spine2": 0.0721, "chest": 0.0726,
    "neck": 0.2635, "head": 0.0666, "hip_offset": 0.1317,
    "height": 1.538,
}

# MS-Human-700 segment mass as a fraction of body mass. Paired segments are halved here.
# Counted so the fractions close to 1.000. An earlier pass grouped by name and reached only
# 0.73, because the trunk is 50 separate bodies whose names match no obvious pattern. The
# trunk is therefore the remainder, which is the only way to be sure nothing is dropped.
# Paired segments are the pair, so a single limb is half.
MASS_FRACTION = {
    "trunk": 0.262, "pelvis": 0.139, "neck": 0.091, "head": 0.061,
    "thigh": 0.208 / 2, "shin": 0.096 / 2, "foot": 0.029 / 2,
    "upper_arm": 0.064 / 2, "forearm": 0.037 / 2, "hand": 0.013 / 2,
}
PAIRED = ("thigh", "shin", "foot", "upper_arm", "forearm", "hand")

# MS-Human-700 joint ranges, degrees. Measured limits, not guesses.
RANGE_DEG = {
    "hip_flex": (-30, 115), "hip_abd": (-49, 29), "hip_rot": (-37, 37),
    "knee": (0, 138), "ankle": (-39, 30), "subtalar": (-19, 19),
    "spine_ext": (-29, 29), "spine_bend": (-17, 17), "spine_rot": (-17, 17),
    "neck": (-29, 29),
    # The model names its shoulder chain differently and no limited joint matched, so these
    # two come from the literature range of motion rather than from the model.
    "shoulder": (-90, 90), "elbow": (0, 126),
}

# Peak isometric torque for a 70 kg adult, N m, from the biomechanics literature. Where a
# source gives N m/kg it is multiplied by MASS. These are maxima, not gait-cycle torques.
MASS = 70.0
TORQUE = {
    "hip": 3.0 * MASS / 1.0,      # ~210
    "knee": 3.1 * MASS / 1.0,     # ~217
    "ankle": 2.0 * MASS / 1.0,    # ~140
    "spine": 300.0,               # trunk extension, the strongest joint in the body
    "shoulder": 80.0,
    "elbow": 55.0,
    "neck": 30.0,
}
# The old body used one number for all of them.
OLD_FLAT = 300.0


def report():
    print("segment lengths, Anny SOMA rest pose against the hand written body")
    old = {"thigh": 0.40, "shin": 0.39, "upper_arm": 0.28, "forearm": 0.26}
    print("   %-12s %8s %8s %8s" % ("segment", "anny", "old", "change"))
    for k, v in old.items():
        a = ANNY[k]
        print("   %-12s %8.3f %8.3f %+7.1f%%" % (k, a, v, 100 * (a - v) / v))
    print()
    print("segment masses from MS-Human-700, for a %.1f kg body" % MASS)
    tot = 0.0
    for k, f in MASS_FRACTION.items():
        n = 2 if k in PAIRED else 1
        tot += f * MASS * n
        print("   %-12s %6.2f kg%s" % (k, f * MASS, "  x2" if n == 2 else ""))
    print("   %-12s %6.2f kg total  (target %.1f)" % ("", tot, MASS))
    print()
    print("joint torque, measured human maxima against the single flat number")
    print("   %-10s %8s %8s %10s" % ("joint", "real", "old", "factor"))
    for k, v in TORQUE.items():
        r = OLD_FLAT / v
        if abs(r - 1.0) < 0.05:
            note = "same"
        else:
            note = "old %.1fx too strong" % r if r > 1 else "old %.1fx too weak" % (1 / r)
        print("   %-10s %8.0f %8.0f %14s" % (k, v, OLD_FLAT, note))
    print()
    print("joint range, MS-Human-700 against the hand written body, degrees")
    oldr = {"hip_flex": (-109, 34), "knee": (0, 137), "ankle": (-46, 46),
            "spine_ext": (-34, 34), "shoulder": (-115, 115), "elbow": (-149, 0)}
    print("   %-12s %16s %16s" % ("joint", "measured", "old"))
    for k, (lo, hi) in oldr.items():
        a, b = RANGE_DEG[k]
        span_new, span_old = b - a, hi - lo
        flag = "  old is %.1fx wider" % (span_old / span_new) if span_old > span_new * 1.05 else ""
        print("   %-12s %7.0f to %5.0f %7.0f to %5.0f%s" % (k, a, b, lo, hi, flag))


if __name__ == "__main__":
    report()
    sys.exit(0)
