#!/usr/bin/env python3
"""How much motion is missing, derived from what the corpus already covers well.

A target of "enough data" is a guess unless something fixes the scale. The thing that fixes
it here is the O3DE corpus itself: it covers walking and turning well enough that a motion
matching demo built on it works, and it covers everything else badly. So the minutes it
spends on its *weakest well-covered* behaviour is a measured floor for what one behaviour
costs, and every gap is measured against that rather than against an opinion.

All shares below are measured, not assumed. `render_motion.py` and the Godot decode produced
them: 22 clips, 1681 s, and the per-behaviour percentages in `corpus.md`.
"""
import sys

O3DE_SECONDS = 1681.0          # measured across 22 clips
KIMODO_SECONDS = 26.0 + 12.0   # idle_stand 8 s, get_up 10 s, sit_stand2 12 s, after discards

# Measured shares of the O3DE corpus. Strafe is a share of MOVING frames, the rest of all.
SHARE = {
    "idle": 0.093, "walk": 0.761, "run": 0.146, "crouch": 0.088, "air": 0.008,
}
STRAFE_OF_MOVING = 0.101
MOVING = 1.0 - SHARE["idle"]

# Turning is the weakest behaviour the corpus still does well: seven clips that a motion
# matching demo actually turns with. Their measured total is the unit of "one behaviour
# covered", and it is a floor, not a target.
TURNING_CLIPS_S = 85.8 + 95.8 + 47.0 + 70.3 + 62.9 + 52.9 + 35.8   # the seven, measured


def covered():
    """Seconds the corpus already spends on each behaviour we need."""
    return {
        # TurnOnSpot is 60% of all idle frames and it is turning, not standing still.
        "standing still": O3DE_SECONDS * SHARE["idle"] * 0.4 + 8.0,
        "sitting": 12.0,                       # sit_stand2 only
        "getting up": 10.0,                    # get_up only
        "being pushed": 74.3,                  # Pushes1, the whole clip
        "strafing": O3DE_SECONDS * MOVING * STRAFE_OF_MOVING,
    }


def main():
    unit = TURNING_CLIPS_S
    print("what one covered behaviour costs, measured: %.0f s (%.1f min)" % (unit, unit / 60))
    print("  the seven O3DE turning clips, its weakest behaviour that still works\n")

    have = covered()
    print("%-16s %10s %10s %10s" % ("behaviour", "have", "target", "missing"))
    total = 0.0
    for k, v in have.items():
        miss = max(unit - v, 0.0)
        total += miss
        print("%-16s %8.0f s %8.0f s %8.0f s" % (k, v, unit, miss))
    print("%-16s %10s %10s %8.0f s = %.0f min" % ("", "", "", total, total / 60))

    print("\ncost to generate it")
    # measured: 240 frames took about 2 s on the 4090, plus a model load per invocation
    clip_s = 10.0
    clips = total / clip_s
    gen_s = clips * 2.5
    print("  %.0f clips of %.0f s" % (clips, clip_s))
    print("  about %.0f s of diffusion, so under %.0f min of compute" % (gen_s, gen_s / 60 + 5))
    print("  the encoder loads once per prompt, so batch with --num_samples")

    print("\nwho the 32 minutes is of")
    print("  A corpus generated at one default body is 32 minutes of ONE morphology. Gait is")
    print("  not scale invariant: step length and cadence follow leg length, and the torque a")
    print("  hip needs follows mass. A controller trained on one body learns balance tuned to")
    print("  those proportions, and a venue is not one body.")
    print()
    print("  Anny carries conditional distributions over height, weight, muscle, proportions,")
    print("  and a morphological age mapping, so a body can be SAMPLED from a stated")
    print("  population rather than defaulted to. The axes that matter here are anthropometric")
    print("  and not appearance: limb length, mass distribution, age, and mobility.")
    print()
    print("  Most of the variation belongs in training as randomisation over the body, which")
    print("  costs no extra motion. What does not is gait itself, so the clips are stratified")
    print("  rather than multiplied:")
    strata = 5
    print("    %d strata sampled across the distribution, %.0f s each, still %.0f min total"
          % (strata, total / strata, total / 60))
    print("    multiplying instead would cost %.0f min and buy far less" % (total * strata / 60))
    print("  The population sampled from must be written down. A distribution nobody states is")
    print("  a default nobody chose.")

    print("\nfor scale")
    print("  usable on disk now      %6.2f h" % ((O3DE_SECONDS + KIMODO_SECONDS) / 3600))
    print("  after backfill          %6.2f h" % ((O3DE_SECONDS + KIMODO_SECONDS + total) / 3600))
    print("  the mini set all three failed runs used   %6.2f h" % (12629 / 30 / 3600))
    print("  AddBiomechanics, treadmill, unusable for control   7.70 h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
