#!/usr/bin/env python3
"""The player's client. Runs on the player's machine, not in the datacenter.

Receives fabric entity packets, turns muscles back into a pose by walking the skeleton, and
draws it with Viser, which the player's browser reaches on localhost. Sends stick input back.

It simulates nothing. It is handed how each body is bent and it believes it, which is what a
client is. The positions it draws were never transmitted: only one root position for each body
crosses the wire, and every other joint is reconstructed here from a bone offset that arrived
once and a muscle value that arrives each frame.

    PLANE=ws://localhost:8770 python proto/client.py     then open the URL it prints
"""
import asyncio, json, os, struct, sys

import numpy as np
import trimesh
import viser
import zstandard as zstd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entity_packet import Packet, SIZE

PLANE = os.environ.get("PLANE", "ws://localhost:8770")
CAPSULE, SPHERE, BOX = 3, 2, 6


def mesh_for(t, size):
    if t == CAPSULE:
        m = trimesh.creation.capsule(radius=size[0], height=2.0 * size[1], count=[8, 8])
        m.apply_translation([0, 0, -size[1]]); return m
    if t == SPHERE:
        return trimesh.creation.icosphere(radius=size[0], subdivisions=2)
    if t == BOX:
        return trimesh.creation.box(extents=2.0 * np.array(size[:3]))
    return None


def axis_angle_mat(axis, ang):
    a = np.asarray(axis, float); a = a / (np.linalg.norm(a) + 1e-12)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * (K @ K)


def mat2quat(R):
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = 0.5 / np.sqrt(t + 1.0)
        return np.array([0.25 / s, (R[2, 1] - R[1, 2]) * s,
                         (R[0, 2] - R[2, 0]) * s, (R[1, 0] - R[0, 1]) * s])
    i = int(np.argmax([R[0, 0], R[1, 1], R[2, 2]]))
    if i == 0:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        return np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s,
                         (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    if i == 1:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        return np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s,
                         0.25 * s, (R[1, 2] + R[2, 1]) / s])
    s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
    return np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s,
                     (R[1, 2] + R[2, 1]) / s, 0.25 * s])


class Skeleton:
    """Bone offsets and hinge axes, received once. Muscles arrive every frame."""

    def __init__(self, meta):
        self.bodies = meta["bodies"]
        self.jrange = meta["jrange"]
        self.n = meta["n"]
        self.nb = len(self.bodies)

    def pose(self, root_pos, muscles):
        """Walk the tree. Returns a world transform for each body of one avatar."""
        pos = np.zeros((self.nb, 3)); rot = np.zeros((self.nb, 3, 3))
        for b, spec in enumerate(self.bodies):
            par = spec["parent"] - 1
            local = np.eye(3)
            mi = spec["muscle"]
            if mi >= 0:
                lo, hi = self.jrange[mi]
                ang = lo + (muscles[mi] / 32767.0 * 0.5 + 0.5) * (hi - lo)
                local = axis_angle_mat(spec["axis"], ang)
            if par < 0:
                rot[b] = local
                pos[b] = root_pos
            else:
                rot[b] = rot[par] @ local
                pos[b] = pos[par] + rot[par] @ np.asarray(spec["pos"])
        return pos, rot


async def main():
    import websockets
    server = viser.ViserServer()
    server.scene.add_grid("/floor", width=40.0, height=40.0)
    drive = {"v": (0.0, 0.0)}
    with server.gui.add_folder("Shove your body"):
        for label, dx, dy in (("forward", 1, 0), ("back", -1, 0),
                              ("left", 0, 1), ("right", 0, -1), ("stop", 0, 0)):
            server.gui.add_button(label).on_click(
                lambda _, dx=dx, dy=dy: drive.update(v=(dx, dy)))
    status = server.gui.add_text("plane", initial_value="connecting")

    async with websockets.connect(PLANE, max_size=None) as ws:
        meta = json.loads(await ws.recv())
        skel = Skeleton(meta)
        nmus = meta["muscles"]
        print(f"[client] {meta['n']} bodies, {skel.nb} joints each, {nmus} muscles", flush=True)
        status.value = f"body {meta['you']} of {meta['n']}"

        groups = {}
        for g in meta["geoms"]:
            key = (g["t"], tuple(round(v, 4) for v in g["size"]))
            groups.setdefault(key, []).append(g)
        handles = {}
        for key, gs in groups.items():
            m = mesh_for(key[0], list(key[1]))
            if m is None:
                continue
            k = len(gs) * meta["n"]
            handles[key] = (server.scene.add_batched_meshes_simple(
                f"/g{abs(hash(key)) % 10**8}",
                vertices=np.asarray(m.vertices, np.float32),
                faces=np.asarray(m.faces, np.uint32),
                batched_positions=np.zeros((k, 3), np.float32),
                batched_wxyzs=np.tile(np.array([1, 0, 0, 0], np.float32), (k, 1)),
            ), gs)

        async def send_input():
            last = None
            while True:
                if drive["v"] != last:
                    last = drive["v"]; await ws.send(json.dumps(list(last)))
                await asyncio.sleep(1 / 30)
        asyncio.create_task(send_input())

        got = 0; bytes_in = 0; prev = None
        dec = zstd.ZstdDecompressor()
        async for wire in ws:
            bytes_in += len(wire); got += 1
            body = dec.decompress(wire[1:], max_output_size=1 << 24)
            if wire[0] == 1 and prev is not None:
                buf = bytes(a ^ b for a, b in zip(body, prev))
            else:
                buf = body
            prev = buf
            n, frame_no = struct.unpack_from("<HI", buf, 0)
            off = 6
            roots = np.zeros((n, 3)); mus = np.zeros((n, nmus))
            for i in range(n):
                for j in range(nmus):
                    p = Packet.decode(buf[off:off + SIZE]); off += SIZE
                    if j == 0:
                        roots[i] = np.array(p.pos_um) / 1e6
                    mus[i, j] = p.rot[0]
            allpos, allrot = [], []
            for i in range(n):
                pp, rr = skel.pose(roots[i], mus[i])
                allpos.append(pp); allrot.append(rr)
            for key, (handle, gs) in handles.items():
                P = np.zeros((len(gs) * n, 3), np.float32)
                Q = np.zeros((len(gs) * n, 4), np.float32)
                for i in range(n):
                    for gi, g in enumerate(gs):
                        b = g["body"] - 1
                        R = allrot[i][b]
                        P[i * len(gs) + gi] = allpos[i][b] + R @ np.asarray(g["pos"])
                        Q[i * len(gs) + gi] = mat2quat(R)
                handle.batched_positions = P
                handle.batched_wxyzs = Q
            if got % 20 == 0:
                status.value = (f"{n} bodies, {bytes_in/got/1000:.1f} kB/frame, "
                                f"{bytes_in/got/n:.0f} B/body")


if __name__ == "__main__":
    asyncio.run(main())
