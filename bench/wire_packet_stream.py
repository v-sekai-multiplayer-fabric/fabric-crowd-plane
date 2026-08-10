#!/usr/bin/env python3
"""What the org's 100-byte packet costs once the stream is compressed.

`wire.md` measured 21 bytes for a body using a body-oriented encoding: muscle scalars, delta,
entropy coded. The fabric wire is `XRGridEntityPacket`, one 100-byte record for each entity,
and the crowd plan puts one entity on each joint. That is 2700 bytes for a body before
compression.

The question is not the raw size. It is what survives compression, because most of the packet
is constant or derivable. This measures it on real simulated motion.
"""
import os, sys, zstandard as zstd
import numpy as np, mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "proto"))
from entity_packet import Packet, SIZE

XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
F, B = 300, 8


def ent(sym):
    _, c = np.unique(sym, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def main():
    m = mujoco.MjModel.from_xml_path(XML)
    m.opt.timestep = 1 / 60
    datas = [mujoco.MjData(m) for _ in range(B)]
    rng = np.random.default_rng(0)
    ph = rng.uniform(0, 6.28, (B, m.nu))
    fr = rng.uniform(0.4, 1.4, (B, m.nu))

    nb = m.nbody - 1                       # joints/bodies per avatar, excluding world
    pos = np.zeros((F, B, nb, 3))
    quat = np.zeros((F, B, nb, 4))
    for i in range(F + 60):
        for b, d in enumerate(datas):
            d.ctrl[:] = 120 * np.sin(2 * np.pi * fr[b] * i / 60 + ph[b])
            mujoco.mj_step(m, d)
            if i >= 60:
                pos[i - 60, b] = d.xpos[1:]
                q = np.empty(4)
                for k in range(nb):
                    mujoco.mju_mat2Quat(q, d.xmat[1 + k])
                    quat[i - 60, b, k] = q

    pos_um = np.round(pos * 1e6).astype(np.int64)
    rot_i16 = np.clip(np.round(quat[..., 1:] * 32767), -32767, 32767).astype(np.int16)

    # Build the real packet stream: one 100-byte record per joint per frame.
    stream = bytearray()
    for f in range(F):
        for b in range(B):
            for j in range(nb):
                stream += Packet(
                    gid=(b << 16) | j,
                    pos_um=tuple(int(v) for v in pos_um[f, b, j]),
                    vel=(0, 0, 0),
                    hlc=(f << 8),
                    class_owner=(1 << 24) | b,
                    sub_index=j,
                    rot=tuple(int(v) for v in rot_i16[f, b, j]),
                ).encode()
    n = F * B
    raw = len(stream) / n
    c = zstd.ZstdCompressor(level=3)
    zst = len(c.compress(bytes(stream))) / n

    # Delta the varying fields across frames, keep the rest, then compress.
    dpos = np.diff(pos_um, axis=0, prepend=pos_um[:1]).astype(np.int32)
    drot = np.diff(rot_i16.astype(np.int32), axis=0, prepend=rot_i16[:1].astype(np.int32))
    delta = dpos.tobytes() + drot.tobytes()
    dz = len(c.compress(delta)) / n

    Hp = sum(ent(dpos[:, :, j, k].ravel()) for j in range(nb) for k in range(3))
    Hr = sum(ent(drot[:, :, j, k].ravel()) for j in range(nb) for k in range(3))
    floor = (Hp + Hr) / 8

    print(f"{nb} joints a body, {F} frames, {B} bodies")
    print(f"  packets raw, 100 B each              {raw:8.0f} B/body/frame")
    print(f"  packets through zstd                 {zst:8.1f}")
    print(f"  delta the varying fields, then zstd  {dz:8.1f}")
    print(f"  entropy floor of those deltas        {floor:8.1f}")
    print(f"\n  body-oriented form measured earlier      21.0")
    print(f"  ratio, packet floor over body form   {floor/21:8.1f}x")


if __name__ == "__main__":
    main()
