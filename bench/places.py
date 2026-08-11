#!/usr/bin/env python3
"""Places to sit, stand on, and lean against, for physical training.

A generated sit is not trackable without something to sit on. Three of five sitting clips put
the pelvis at 0.54 to 0.55 m and held it there for seconds, which is a real chair height and
no chair: in simulation the body simply falls. The motion was never wrong, the world was
missing.

For physics a chair is a box. Nothing here needs art, because what a body needs from a chair
is a support surface at a height, with clearance for the legs and something to push off. That
also means these carry no licence at all, which is more than can be said for any mesh.

**The heights are not chosen.** Seat and step heights are ergonomic and building standards,
so each entry names the standard it comes from. A number here that cannot cite one is a bug.

    python places.py            # the catalogue, and what each one is for
    python places.py --mjcf     # emit MuJoCo bodies for the crowd plane
    python places.py --json     # emit protomotions BoxSceneObject entries
"""
import argparse
import json
import sys

# height, width, depth in metres, and the reason the height is that number.
# EN 1729 sets seating heights for work chairs. Building codes set stair risers: the
# International Residential Code allows a maximum 7.75 in, 0.197 m, and treads a minimum
# 10 in, 0.254 m. Table height follows EN 527. Counters and bar stools follow common
# millwork practice at 0.9 and 1.05 m surfaces with a footrest a third of the way down.
PLACES = {
    "chair": dict(h=0.45, w=0.45, d=0.45,
                  why="EN 1729 adult seat height, 0.43 to 0.46",
                  teaches="sit down, sit still, stand up"),
    "bench": dict(h=0.45, w=1.60, d=0.40,
                  why="same seat height, bench depth without a back",
                  teaches="sitting beside someone, sliding along, standing from an edge"),
    "sofa": dict(h=0.40, w=1.80, d=0.85,
                 why="lounge seating sits lower than a work chair, 0.38 to 0.43",
                 teaches="a deep low sit and the harder rise out of one"),
    "stool": dict(h=0.65, w=0.35, d=0.35,
                  why="counter stool for a 0.90 m surface, seat two thirds of surface height",
                  teaches="perching, feet unsupported, stepping down"),
    "step": dict(h=0.18, w=1.20, d=0.30,
                 why="IRC maximum riser 0.197 m, tread minimum 0.254 m",
                 teaches="stepping up and down, sitting on a kerb, the lowest useful sit"),
    "ledge": dict(h=0.30, w=1.20, d=0.35,
                  why="low wall, between a step and a seat",
                  teaches="perching without a backrest, pushing up with the hands"),
    "table": dict(h=0.74, w=1.40, d=0.80,
                  why="EN 527 work surface, 0.72 to 0.76",
                  teaches="leaning on, pushing off, an obstacle at waist height"),
    "floor": dict(h=0.0, w=0.0, d=0.0,
                  why="the one support surface every scene already has",
                  teaches="sitting cross legged, lying, and getting up, which is the gap"),
}

# Where a body's pelvis ends up when it sits on each. A sit is trackable when the reference
# pelvis and the support agree, so this is the number a generated clip is checked against.
PELVIS_ABOVE_SEAT = 0.06


def catalogue():
    print("%-8s %6s %6s %6s   %s" % ("place", "h", "w", "d", "why that height"))
    for k, v in PLACES.items():
        print("%-8s %6.2f %6.2f %6.2f   %s" % (k, v["h"], v["w"], v["d"], v["why"]))
    print()
    print("what each one is for")
    for k, v in PLACES.items():
        print("   %-8s %s" % (k, v["teaches"]))
    print()
    print("expected pelvis height when seated, which is what a clip is checked against")
    for k, v in PLACES.items():
        if v["h"] > 0:
            print("   %-8s %.2f m" % (k, v["h"] + PELVIS_ABOVE_SEAT))
    print()
    print("The three generated sitting clips that failed put the pelvis at 0.54 to 0.55 m,")
    print("which matches a chair at %.2f. The pose was right and the chair was absent."
          % (PLACES["chair"]["h"] + PELVIS_ABOVE_SEAT))


def as_mjcf():
    out = ['<mujoco model="places">', '  <worldbody>']
    x = 0.0
    for k, v in PLACES.items():
        if v["h"] <= 0:
            continue
        out.append('    <body name="%s" pos="%.2f 0 %.3f">' % (k, x, v["h"] / 2))
        out.append('      <geom type="box" size="%.3f %.3f %.3f" rgba="0.55 0.5 0.45 1"/>'
                   % (v["w"] / 2, v["d"] / 2, v["h"] / 2))
        out.append('    </body>')
        x += max(v["w"], 0.6) + 0.8
    out += ['  </worldbody>', '</mujoco>']
    return "\n".join(out)


def as_scene_json():
    objs = []
    x = 0.0
    for k, v in PLACES.items():
        if v["h"] <= 0:
            continue
        objs.append({"type": "box", "id": k,
                     "width": v["w"], "depth": v["d"], "height": v["h"],
                     "translation": [x, 0.0, v["h"] / 2], "is_static": True})
        x += max(v["w"], 0.6) + 0.8
    return json.dumps({"scenes": [{"id": "sitting_places", "objects": objs}]}, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mjcf", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.mjcf:
        print(as_mjcf())
    elif a.json:
        print(as_scene_json())
    else:
        catalogue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
