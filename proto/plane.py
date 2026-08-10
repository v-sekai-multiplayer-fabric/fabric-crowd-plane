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

import zstandard as zstd

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bench"))
sys.path.insert(0, HERE)
from touchable import venue
from entity_packet import Packet, SIZE

TICK = 1.0 / 60
PUBLISH_EVERY = 3                    # 20 Hz on the wire
N = int(os.environ.get("BODIES", "60"))
SPACING = float(os.environ.get("SPACING", "0.9"))
PUSH = float(os.environ.get("PUSH", "1200"))
PORT = int(os.environ.get("PORT", "8770"))
CLASS_SKELETON_JOINT = 2       # the class field says how to read the packet


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
        self.nq = self.m.nq // n
        self.nu_each = self.m.nu // n
        self.jrange = [(float(self.m.jnt_range[1 + j, 0]), float(self.m.jnt_range[1 + j, 1]))
                       for j in range(self.nu_each)]
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
        """Sent once: the skeleton the client needs to turn muscles back into positions.

        Shapes, bone offsets, and the parent of each body. The plane draws nothing; it says
        what a body is shaped like and then only ever sends how it is bent.
        """
        nb = (self.m.nbody - 1) // self.n            # bodies in one avatar
        bodies = []
        for b in range(1, nb + 1):
            # which muscle bends this body relative to its parent, and about which axis
            mus, axis = -1, [0.0, 0.0, 1.0]
            for j in range(self.m.njnt):
                if self.m.jnt_bodyid[j] == b and self.m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
                    for a in range(self.nu_each):
                        if self.m.actuator_trnid[a, 0] == j:
                            mus = a; axis = [float(x) for x in self.m.jnt_axis[j]]
                            break
                    break
            bodies.append({
                "parent": int(self.m.body_parentid[b]),
                "pos": [float(x) for x in self.m.body_pos[b]],
                "muscle": mus,
                "axis": axis,
            })
        geoms = []
        for g in range(self.m.ngeom):
            b = int(self.m.geom_bodyid[g])
            if b == 0 or b > nb:
                continue
            geoms.append({"body": b, "t": int(self.m.geom_type[g]),
                          "size": [float(x) for x in self.m.geom_size[g][:3]],
                          "pos": [float(x) for x in self.m.geom_pos[g]],
                          "quat": [float(x) for x in self.m.geom_quat[g]]})
        return {"n": self.n, "muscles": self.nu_each, "packet_size": SIZE,
                "jrange": self.jrange, "bodies": bodies, "geoms": geoms}

    def frame(self, frame_no):
        """The fabric wire: one XRGridEntityPacket for each joint entity.

        The rotation field carries muscle values, which are swing-twist by another name and
        are what this project sends. The position field is present because the schema has it,
        and it is derived rather than transmitted for every joint but the root: it is held
        constant, so it delta-codes to nothing and the client reconstructs each joint from its
        parent and a static bone length. See docs/logbook/wire.md.
        """
        out = bytearray(struct.pack("<HI", self.n, frame_no))
        q = self.d.qpos
        for i in range(self.n):
            base = i * self.nq
            root_um = tuple(int(np.clip(q[base + k] * 1e6, -2**62, 2**62)) for k in range(3))
            for j in range(self.nu_each):
                a = q[base + 7 + j]
                lo, hi = self.jrange[j]
                norm = 0.0 if hi <= lo else (a - lo) / (hi - lo) * 2.0 - 1.0
                v = int(np.clip(norm * 32767, -32767, 32767))
                out += Packet(
                    gid=(i << 16) | j,
                    pos_um=root_um if j == 0 else (0, 0, 0),   # derived for every joint but the root
                    vel=(0, 0, 0),
                    hlc=(frame_no << 8),
                    class_owner=(CLASS_SKELETON_JOINT << 24) | (i & 0xFFFFFF),
                    sub_index=j,
                    rot=(v, 0, 0),                             # one muscle for each hinge here
                ).encode()
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

    # The packets are the schema; the compression is the transport. A frame is delta-coded
    # against the previous one and then compressed, which is where the redundancy the packet
    # deliberately leaves in gets taken back. See docs/logbook/wire.md.
    comp = zstd.ZstdCompressor(level=1)

    async def loop():
        i, t0, sent = 0, time.perf_counter(), 0
        prev = None
        while True:
            room.step(drives)
            i += 1
            if i % PUBLISH_EVERY == 0 and clients:
                raw = room.frame(i // PUBLISH_EVERY)
                if prev is not None and len(prev) == len(raw):
                    d = bytes(a ^ b for a, b in zip(raw, prev))     # delta against last frame
                    buf = b"\x01" + comp.compress(d)
                else:
                    buf = b"\x00" + comp.compress(raw)
                prev = raw
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
