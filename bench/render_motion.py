#!/usr/bin/env python3
"""Draw a generated motion so a person can look at it.

A prompt is not a guarantee. `get_up` could contain a person who never leaves the floor and
every number in the pipeline would still be green, because the numbers check units and
continuity, not whether the motion is the motion that was asked for. So this draws it.

Two outputs. A contact sheet, which is one PNG holding evenly spaced frames, for a quick read.
And an FFV1 matroska, which is lossless and is the intermediate the repo already uses for
recordings, for anything that needs to watch it move.

    python render_motion.py clip.npz [--sheet out.png] [--video out.mkv]
"""
import argparse
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, "/opt/weft-motion")
from kimodo_to_usd import parse_bvh_hierarchy, TPOSE_BVH

W, H = 320, 400


def bone_list():
    tag, val = parse_bvh_hierarchy(TPOSE_BVH)
    if tag == "error":
        return ("error", val)
    names, parents, _off = val
    # Fingers and face are noise at this size; keep the bones that carry a pose.
    drop = ("Thumb", "Index", "Middle", "Ring", "Little", "Eye", "Jaw", "End")
    keep = [i for i, n in enumerate(names) if not any(d in n for d in drop)]
    kept = set(keep)
    bones = [(p, i) for i, p in enumerate(parents) if p >= 0 and i in kept and p in kept]
    return ("ok", (names, bones))


def project(pts, lo, hi):
    """Orthographic side-on view: x across, y up. World metres to pixels."""
    span = max(hi[0] - lo[0], hi[1] - lo[1], 1e-3)
    s = (min(W, H) - 40) / span
    x = (pts[:, 0] - lo[0]) * s + 20
    y = H - 20 - (pts[:, 1] - lo[1]) * s
    return np.stack([x, y], axis=1)


def draw(frame_pts, bones, lo, hi, ground_y):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)
    p = project(frame_pts, lo, hi)
    gy = H - 20 - (ground_y - lo[1]) * ((min(W, H) - 40) / max(hi[0] - lo[0], hi[1] - lo[1], 1e-3))
    d.line([(0, gy), (W, gy)], fill=(60, 60, 70), width=1)
    for a, b in bones:
        d.line([tuple(p[a]), tuple(p[b])], fill=(210, 220, 235), width=2)
    for i in range(len(p)):
        d.ellipse([p[i][0] - 1.5, p[i][1] - 1.5, p[i][0] + 1.5, p[i][1] + 1.5], fill=(120, 190, 255))
    return img


def render(npz_path, sheet_path=None, video_path=None, sample_index=0, cols=8):
    from PIL import Image, ImageDraw
    tag, val = bone_list()
    if tag == "error":
        return ("error", val)
    _names, bones = val

    d = np.load(npz_path, allow_pickle=True)
    pj = np.asarray(d["posed_joints"], dtype=np.float64)
    if pj.ndim == 4:                       # (samples, T, J, 3)
        pj = pj[sample_index]
    T = pj.shape[0]

    lo = np.array([pj[:, :, 0].min(), pj[:, :, 1].min()])
    hi = np.array([pj[:, :, 0].max(), pj[:, :, 1].max()])
    pad = 0.15 * max(hi - lo)
    lo, hi = lo - pad, hi + pad
    ground = float(pj[:, :, 1].min())

    if sheet_path:
        idx = np.linspace(0, T - 1, cols).astype(int)
        sheet = Image.new("RGB", (W * cols, H), (18, 18, 22))
        for k, f in enumerate(idx):
            im = draw(pj[f], bones, lo, hi, ground)
            ImageDraw.Draw(im).text((8, 8), "%.1fs" % (f / 30.0), fill=(160, 170, 190))
            sheet.paste(im, (k * W, 0))
        sheet.save(sheet_path)

    if video_path:
        tmp = video_path + ".frames"
        os.makedirs(tmp, exist_ok=True)
        for f in range(T):
            draw(pj[f], bones, lo, hi, ground).save(os.path.join(tmp, "%05d.png" % f))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30",
               "-i", os.path.join(tmp, "%05d.png"),
               "-c:v", "ffv1", "-level", "3", "-pix_fmt", "rgb24", video_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
        if r.returncode != 0:
            return ("error", "ffmpeg: %s" % r.stderr[-200:])

    return ("ok", {"frames": T, "height_m": float(pj[:, :, 1].max() - pj[:, :, 1].min()),
                   "travel_m": float(np.linalg.norm(pj[-1, 0, [0, 2]] - pj[0, 0, [0, 2]]))})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--sheet")
    ap.add_argument("--video")
    ap.add_argument("--sample", type=int, default=0)
    a = ap.parse_args()
    tag, val = render(a.npz, a.sheet, a.video, a.sample)
    if tag == "error":
        print("error:", val)
        return 1
    print("  %-22s %4d frames  height %.2f m  travel %.2f m"
          % (os.path.basename(a.npz), val["frames"], val["height_m"], val["travel_m"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
