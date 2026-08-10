#!/usr/bin/env python3
"""The prototype: a room of bodies that push each other, streamed to a browser.

One MuJoCo model holds every avatar, so contact between people is solved once and everybody
agrees on it. That is the product. Each connected client drives one body by pushing on its
pelvis, which is a force and not a teleport, so shoving into the crowd moves the crowd.

The wire is the measured one: a root position in millimetres as three int16, and each joint
as three 12-bit rotations packed. See docs/logbook/wire.md.
"""
import asyncio, json, math, os, struct, sys, time

import mujoco
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from touchable import venue

TICK = 1.0 / 60
PUBLISH_EVERY = 3                      # 20 Hz on the wire
N = int(os.environ.get("BODIES", "40"))
SPACING = float(os.environ.get("SPACING", "0.9"))
PUSH = float(os.environ.get("PUSH", "900"))     # newtons on the pelvis


class Room:
    def __init__(self, n, spacing):
        self.m = mujoco.MjModel.from_xml_string(venue(n, spacing))
        self.m.opt.timestep = TICK
        self.d = mujoco.MjData(self.m)
        self.roots = np.array([b for b in range(1, self.m.nbody)
                               if self.m.body_parentid[b] == 0])
        self.n = n
        self.nq = self.m.nq // n
        self.free = set(range(n))       # bodies nobody is driving
        self.owner = {}                 # client id -> body index
        for _ in range(30):
            mujoco.mj_step(self.m, self.d)

    def claim(self, cid):
        if not self.free:
            return None
        i = min(self.free)
        self.free.discard(i)
        self.owner[cid] = i
        return i

    def release(self, cid):
        i = self.owner.pop(cid, None)
        if i is not None:
            self.free.add(i)

    def step(self, drives):
        self.d.xfrc_applied[:] = 0.0
        for cid, (dx, dy) in drives.items():
            i = self.owner.get(cid)
            if i is not None and (dx or dy):
                self.d.xfrc_applied[self.roots[i], 0] = dx * PUSH
                self.d.xfrc_applied[self.roots[i], 1] = dy * PUSH
        mujoco.mj_step(self.m, self.d)

    def frame(self):
        """Root position as int16 millimetres, joints as 12-bit rotations."""
        out = bytearray(struct.pack("<H", self.n))
        q = self.d.qpos
        for i in range(self.n):
            b = i * self.nq
            out += struct.pack("<hhh", *(int(np.clip(q[b + k] * 1000, -32000, 32000))
                                         for k in range(3)))
            out += struct.pack("<hhhh", *(int(np.clip(q[b + 3 + k] * 32767, -32767, 32767))
                                          for k in range(4)))
            acc = bits = 0
            for j in range(self.nq - 7):
                v = int(np.clip(q[b + 7 + j] / math.pi * 2047, -2048, 2047)) & 0xFFF
                acc |= v << bits
                bits += 12
                while bits >= 8:
                    out.append(acc & 0xFF); acc >>= 8; bits -= 8
            if bits:
                out.append(acc & 0xFF)
        return bytes(out)

    def shape(self):
        """Static description the client needs once: capsule geometry per body."""
        geoms = []
        for g in range(self.m.ngeom):
            if self.m.geom_bodyid[g] == 0:
                continue
            geoms.append({
                "body": int(self.m.geom_bodyid[g]),
                "type": int(self.m.geom_type[g]),
                "size": [float(x) for x in self.m.geom_size[g]],
                "pos": [float(x) for x in self.m.geom_pos[g]],
                "quat": [float(x) for x in self.m.geom_quat[g]],
            })
        return {"bodies": int(self.m.nbody), "nq_each": self.nq, "n": self.n,
                "roots": [int(r) for r in self.roots], "geoms": geoms}


async def main():
    import websockets
    room = Room(N, SPACING)
    clients = {}
    drives = {}

    async def handler(ws):
        cid = id(ws)
        mine = room.claim(cid)
        clients[cid] = ws
        drives[cid] = (0.0, 0.0)
        await ws.send(json.dumps({"hello": mine, **room.shape()}))
        try:
            async for msg in ws:
                dx, dy = json.loads(msg)
                drives[cid] = (float(dx), float(dy))
        except Exception:
            pass
        finally:
            room.release(cid); clients.pop(cid, None); drives.pop(cid, None)

    async def loop():
        i = 0
        t0 = time.perf_counter()
        sent = 0
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
                print(f"[room] {i} ticks  {len(clients)} clients  "
                      f"{sent/el/1000:.1f} kB/s total  "
                      f"{sent/max(1,len(clients))/el/1000:.2f} kB/s each", flush=True)
            nxt = t0 + i * TICK
            rest = nxt - time.perf_counter()
            if rest > 0:
                await asyncio.sleep(rest)

    async with websockets.serve(handler, "0.0.0.0", 8080, max_size=None):
        print(f"[room] {N} bodies, ws://0.0.0.0:8080", flush=True)
        await loop()


if __name__ == "__main__":
    asyncio.run(main())
