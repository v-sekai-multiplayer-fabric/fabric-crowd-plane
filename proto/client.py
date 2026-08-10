#!/usr/bin/env python3
"""The player's client. Runs on the player's machine, not in the datacenter.

Connects to a crowd plane, decodes poses off the wire, and draws them with Viser, which the
player's browser reaches on localhost. Sends stick input back.

This process simulates nothing. It has no MuJoCo, no physics, and no authority: it is handed
positions and it believes them, which is what a client is.

    PLANE=ws://localhost:8770 python proto/client.py     then open the URL it prints
"""
import asyncio, json, os, struct

import numpy as np
import trimesh
import viser

PLANE = os.environ.get("PLANE", "ws://localhost:8770")
CAPSULE, SPHERE, BOX = 3, 2, 6


def mesh_for(t, size):
    if t == CAPSULE:
        m = trimesh.creation.capsule(radius=size[0], height=2.0 * size[1], count=[8, 8])
        m.apply_translation([0, 0, -size[1]])
        return m
    if t == SPHERE:
        return trimesh.creation.icosphere(radius=size[0], subdivisions=2)
    if t == BOX:
        return trimesh.creation.box(extents=2.0 * np.array(size[:3]))
    return None


async def main():
    import websockets
    server = viser.ViserServer()
    server.scene.add_grid("/floor", width=40.0, height=40.0)
    drive = {"v": (0.0, 0.0)}
    with server.gui.add_folder("Shove your body"):
        for label, dx, dy in (("forward", 1, 0), ("back", -1, 0),
                              ("left", 0, 1), ("right", 0, -1), ("stop", 0, 0)):
            b = server.gui.add_button(label)
            b.on_click(lambda _, dx=dx, dy=dy: drive.update(v=(dx, dy)))
    status = server.gui.add_text("plane", initial_value="connecting")

    async with websockets.connect(PLANE, max_size=None) as ws:
        hello = json.loads(await ws.recv())
        status.value = f"connected, you are body {hello['you']}"
        print(f"[client] connected to {PLANE}, {hello['n']} bodies", flush=True)

        # Group identical shapes so each is one batched draw call.
        groups, order = {}, []
        for idx, g in enumerate(hello["geoms"]):
            key = (g["t"], tuple(round(v, 4) for v in g["size"]))
            groups.setdefault(key, []).append(idx)
        handles = {}
        for key, idxs in groups.items():
            m = mesh_for(key[0], list(key[1]))
            if m is None:
                continue
            handles[key] = (server.scene.add_batched_meshes_simple(
                f"/g{abs(hash(key)) % 10**8}",
                vertices=np.asarray(m.vertices, np.float32),
                faces=np.asarray(m.faces, np.uint32),
                batched_positions=np.zeros((len(idxs), 3), np.float32),
                batched_wxyzs=np.tile(np.array([1, 0, 0, 0], np.float32), (len(idxs), 1)),
            ), np.array(idxs))
            order.append(key)

        async def send_input():
            last = None
            while True:
                if drive["v"] != last:
                    last = drive["v"]
                    await ws.send(json.dumps(list(last)))
                await asyncio.sleep(1 / 30)

        asyncio.create_task(send_input())
        bytes_in, frames = 0, 0
        async for buf in ws:
            bytes_in += len(buf); frames += 1
            (count,) = struct.unpack_from("<H", buf, 0)
            raw = np.frombuffer(buf, dtype=np.int16, offset=2, count=count * 7).reshape(count, 7)
            pos = raw[:, :3].astype(np.float32) / 1000.0
            quat = raw[:, 3:].astype(np.float32) / 32767.0
            for key in order:
                handle, idxs = handles[key]
                handle.batched_positions = pos[idxs]
                handle.batched_wxyzs = quat[idxs]
            if frames % 60 == 0:
                status.value = f"{count} shapes, {bytes_in/frames/1000:.1f} kB/frame"


if __name__ == "__main__":
    asyncio.run(main())
