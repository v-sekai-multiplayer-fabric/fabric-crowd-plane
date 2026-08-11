#!/usr/bin/env python3
"""Recover the motors for a body Anny sampled.

Anny gives a shape: height, mass, proportions, muscularity. It does not give actuators, and a
1.5 m 50 kg body cannot be driven by the numbers that fit a 1.9 m 95 kg one. Torque limits,
armature, and PD gains all have to move with the body or the controller is driving something
that is not there.

None of this is fitted. Each quantity follows from dimensional analysis, anchored on the one
body whose numbers were measured.

**Torque scales with mass.** Muscle force follows physiological cross-sectional area, and the
torque it makes follows that force times a moment arm. Under isometric scaling area goes as
L^2 and the arm as L, so torque goes as L^3, and mass goes as L^3 too. Torque per kilogram is
therefore constant, which is why the literature reports it that way. The result survives
non-isometric scaling as well: hold height and vary mass, and area goes as m/L while the arm
still goes as L, so torque goes as m again.

**Muscularity modulates it at fixed mass.** Anny carries a muscle parameter, and two bodies of
equal mass do not have equal cross-section. It multiplies the torque and nothing else.

**Inertia scales as m L^2**, so armature does, and so do the gains. The stability bound found
in `body.md` is kp < 4I/dt^2, so kp follows inertia. Critical damping puts kd at
2*sqrt(kp*I), which follows inertia too.

    python motors.py                 # the reference body, then a range of sampled ones
"""
import sys

# The one body whose numbers were measured. Torques are peak isometric maxima for a 70 kg
# adult from the biomechanics literature; see body.md for each source and for why
# MS-Human-700's own muscle sums are not used.
REF_MASS = 70.0
REF_HEIGHT = 1.70
REF_TORQUE = {
    "hip": 210.0, "knee": 217.0, "ankle": 140.0, "spine": 300.0,
    "shoulder": 80.0, "elbow": 55.0, "neck": 30.0,
}
REF_ARMATURE = 0.02          # kg m^2, the value the hand written body carries
TIMESTEP = 1.0 / 60


def motors(mass, height, muscle=1.0, timestep=TIMESTEP):
    """Actuator limits, armature, and gains for one sampled body.

    `muscle` is Anny's muscularity around 1.0, where 1.0 is the reference build.
    Returns ("ok", dict) or ("error", reason).
    """
    if not (20.0 <= mass <= 200.0):
        return ("error", "mass %.1f kg is not a person" % mass)
    if not (0.9 <= height <= 2.3):
        return ("error", "height %.2f m is not a person" % height)
    if not (0.5 <= muscle <= 1.6):
        return ("error", "muscularity %.2f is outside what Anny samples" % muscle)

    m_ratio = mass / REF_MASS
    l_ratio = height / REF_HEIGHT
    inertia_ratio = m_ratio * l_ratio ** 2

    torque = {k: v * m_ratio * muscle for k, v in REF_TORQUE.items()}
    armature = REF_ARMATURE * inertia_ratio

    # The joint the gains must not destabilise is the lightest one, so the bound is taken
    # against the smallest effective inertia rather than the median.
    kp_ceiling = 4.0 * armature / (timestep ** 2)
    kp = 0.6 * kp_ceiling               # a ratio to the bound, not a number picked to feel right
    kd = 2.0 * (kp * armature) ** 0.5   # critically damped

    return ("ok", {
        "mass": mass, "height": height, "muscle": muscle,
        "torque": torque, "armature": armature,
        "kp": kp, "kd": kd, "kp_ceiling": kp_ceiling,
        "inertia_ratio": inertia_ratio,
    })


def main():
    print("reference body, which must reproduce the measured numbers")
    tag, r = motors(REF_MASS, REF_HEIGHT)
    if tag == "error":
        print("  error:", r); return 1
    for k in ("hip", "knee", "elbow"):
        got, want = r["torque"][k], REF_TORQUE[k]
        ok = "ok" if abs(got - want) < 1e-9 else "MISMATCH"
        print("   %-8s %7.1f N m  (measured %7.1f)  %s" % (k, got, want, ok))
    print("   armature %.4f   kp %.0f of a %.0f ceiling   kd %.1f"
          % (r["armature"], r["kp"], r["kp_ceiling"], r["kd"]))

    print("\nbodies across the range Anny samples")
    print("%-26s %7s %7s %7s %7s %9s %7s"
          % ("body", "hip", "knee", "elbow", "armat", "kp", "kd"))
    for label, mass, height, muscle in (
        ("small, light", 48.0, 1.52, 0.85),
        ("small, muscular", 55.0, 1.55, 1.25),
        ("reference", 70.0, 1.70, 1.00),
        ("tall, light", 78.0, 1.88, 0.85),
        ("tall, heavy", 95.0, 1.90, 1.15),
    ):
        tag, b = motors(mass, height, muscle)
        if tag == "error":
            print("%-26s %s" % (label, b)); continue
        print("%-26s %7.0f %7.0f %7.1f %7.4f %9.0f %7.1f"
              % ("%s %.0fkg %.2fm" % (label, mass, height),
                 b["torque"]["hip"], b["torque"]["knee"], b["torque"]["elbow"],
                 b["armature"], b["kp"], b["kd"]))

    print("\nthe spread the controller has to cover")
    lo = motors(48.0, 1.52, 0.85)[1]
    hi = motors(95.0, 1.90, 1.15)[1]
    print("   hip torque    %.0f to %.0f N m, a factor of %.1f"
          % (lo["torque"]["hip"], hi["torque"]["hip"], hi["torque"]["hip"] / lo["torque"]["hip"]))
    print("   armature      %.4f to %.4f, a factor of %.1f"
          % (lo["armature"], hi["armature"], hi["armature"] / lo["armature"]))
    print("   A single set of motors is wrong at both ends by roughly that much.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
