#!/usr/bin/env python3
"""The crowd plane. Physics only.

Every avatar is in one MuJoCo model, so contact between people is solved once and everybody
agrees on it. That is the product.

This process renders nothing and knows nothing about browsers. It simulates, and it publishes
poses to whoever asked. A plane that draws is not a plane.

Python here is a stand-in for the C++ plane; see PLAN.md. What is not a stand-in is the split:
rendering happens on the player's machine, in client.py.

    BODIES=60 python proto/plane.py
"""
import asyncio, json, math, os, struct, sys, time

import mujoco
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from touchable import venue

TICK = 1.0 / 60
PUBLISH_EVERY = 3                    # 20 Hz on the wire
N = int(os.environ.get("BODIES", "60"))
SPACING = float(os.environ.get("SPACING", "0.9"))
PUSH = float(os.environ.get("PUSH", "1200"))
PORT = int(os.environ.get("PORT", "8770"))


class Room:
    def __init__(self, n, spacing):
        self.m = mujoco.MjModel.from_xml_string(venue(n, spacing))
        self.m.opt.timestep = TICK
        self.d = mujoco.MjData(self.m)
        self.n = n
        self.roots = np.array([b for b in range(1, self.m.nbody)
                               if self.m.body_parentid[b] == 0])
        self.geoms = np.array([g for g in range(self.m.ngeom)
                               if self.m.geom_bodyid[g] != 0])
        self.free = set(range(n))
        self.owner = {}
        for _ in range(40):
            mujoco.mj_step(self.m, self.d)

    def claim(self, cid):
        if not self.free:
            return None
        i = min(self.free); self.free.discard(i); self.owner[cid] = i
        return i

    def release(self, cid):
        i = self.owner.pop(cid, None)
        if i is not None:
            self.free.add(i)

    def step(self, drives):
        self.d.xfrc_applied[:] = 0.0
        for cid, (dx, dy) in drives.items():
            i = self.owner.get(cid)
            if i is not None:
                self.d.xfrc_applied[self.roots[i], 0] = dx * PUSH
                self.d.xfrc_applied[self.roots[i], 1] = dy * PUSH
        mujoco.mj_step(self.m, self.d)

    def geometry(self):
        """Sent once. The client needs shapes to draw; the plane never draws them."""
        out = []
        for g in self.geoms:
            out.append({"t": int(self.m.geom_type[g]),
                        "size": [float(x) for x in self.m.geom_size[g][:3]]})
        return {"n": self.n, "geoms": out}

    def frame(self):
        """Poses on the wire: position in millimetres as int16, orientation as int16 quat."""
        pos = self.d.geom_xpos[self.geoms]
        out = bytearray(struct.pack("<H", len(self.geoms)))
        q = np.empty(4)
        for k, g in enumerate(self.geoms):
            out += struct.pack("<hhh", *(int(np.clip(v * 1000, -32000, 32000)) for v in pos[k]))
            mujoco.mju_mat2Quat(q, self.d.geom_xmat[g])
            out += struct.pack("<hhhh", *(int(np.clip(v * 32767, -32767, 32767)) for v in q))
        return bytes(out)

    def cross_contacts(self):
        root_of = {}
        def root(b):
            r = b
            while self.m.body_parentid[r]:
                r = self.m.body_parentid[r]
            return r
        c = 0
        for k in range(self.d.ncon):
            b1 = self.m.geom_bodyid[self.d.contact.geom1[k]]
            b2 = self.m.geom_bodyid[self.d.contact.geom2[k]]
            if b1 and b2 and root(b1) != root(b2):
                c += 1
        return c


async def main():
    import websockets
    room = Room(N, SPACING)
    clients, drives = {}, {}

    async def handler(ws):
        cid = id(ws)
        mine = room.claim(cid)
        clients[cid] = ws; drives[cid] = (0.0, 0.0)
        await ws.send(json.dumps({"you": mine, **room.geometry()}))
        try:
            async for msg in ws:
                dx, dy = json.loads(msg)
                drives[cid] = (float(dx), float(dy))
        except Exception:
            pass
        finally:
            room.release(cid); clients.pop(cid, None); drives.pop(cid, None)

    async def loop():
        i, t0, sent = 0, time.perf_counter(), 0
        while True:
            room.step(drives)
            i += 1
            if i % PUBLISH_EVERY == 0 and clients:
                buf = room.frame()
                sent += len(buf) * len(clients)
                await asyncio.gather(*[c.send(buf) for c in list(clients.values())],
                                     return_exceptions=True)
            if i % 600 == 0:
                el = time.perf_counter() - t0
                each = sent / max(1, len(clients)) / el / 1000
                print(f"[plane] {i//60}s  {len(clients)} clients  "
                      f"{room.cross_contacts()} person-to-person contacts  "
                      f"{each:.2f} kB/s each", flush=True)
            rest = t0 + i * TICK - time.perf_counter()
            if rest > 0:
                await asyncio.sleep(rest)

    async with websockets.serve(handler, "0.0.0.0", PORT, max_size=None):
        print(f"[plane] {N} bodies simulating, publishing on :{PORT}", flush=True)
        await loop()


if __name__ == "__main__":
    asyncio.run(main())
