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
from entity_packet import Packet, SIZE, PACKET_DTYPE, empty as empty_packets

TICK = 1.0 / 60
PUBLISH_EVERY = 3                    # 20 Hz on the wire
N = int(os.environ.get("BODIES", "60"))
SPACING = float(os.environ.get("SPACING", "0.9"))
# The ceiling on the force a body may use to reach its wanted speed, not the force it
# always applies. A constant force has no speed it settles at, so a held stick accelerates
# a body without limit: at 1200 N on 70 kg that is 17 m/s^2, and a minute of it reaches
# thousands of m/s and takes the solver with it. See docs/logbook/body.md.
PUSH = float(os.environ.get("PUSH", "1200"))
# What a body is trying to reach, in metres a second. A person walks at about 1.4 and runs
# at about 5. The stick magnitude picks a point between them, so this is a speed a body
# has, not a number that trades one failure against another.
WALK_SPEED = float(os.environ.get("WALK_SPEED", "1.4"))
RUN_SPEED = float(os.environ.get("RUN_SPEED", "5.0"))

# The 26 joint motors stay dark, and that is a gap and not a decision. Driving them as a PD
# servo that holds the rest pose was tried and does not stand: the crowd collapses and is
# then ejected upward, which reads as standing if a height is sampled at one instant. A PD
# hold has no term for where the centre of mass is over the feet, so it cannot balance. The
# motors wait on the trained controller, which does have that term. See docs/logbook/controller.md.
JUMP = float(os.environ.get("JUMP", "6000"))
CROUCH = float(os.environ.get("CROUCH", "2500"))
FACE_TORQUE = float(os.environ.get("FACE_TORQUE", "400"))
PORT = int(os.environ.get("PORT", "8770"))
CLASS_SKELETON_JOINT = 2       # the class field says how to read the packet
# How many fixed steps one pass may take before the plane gives up and drops the debt.
#
# Godot uses `max_physics_steps_per_frame`, default 8, which is a number chosen to feel right.
# There is a derived one here instead. `lean-spatial-oracle/core/Resources.lean`:
#
#     latencyTicksFloor = max (simTickHz / 10) 1        -- 100 ms at any tick rate
#     perNeighborLatencyTicks rtt = max (ceil(rtt*hz/1000) + drainMargin) latencyTicksFloor
#
# That is the lateness the fabric already tolerates: the staging timeout a migration is
# allowed before it is considered failed, with a one-tick drain margin proved sufficient.
# A plane may therefore be late by up to that and still be inside what the protocol assumes.
# Past it, the predictions the rest of the system makes are no longer sound, so dropping is
# not a fallback but the correct thing.
#
# At 60 Hz this is 6 steps, and it moves with the tick rate rather than being pinned to 8.
SIM_TICK_HZ = int(1.0 / TICK)
DRAIN_MARGIN = 1                                   # proved: a queue drains in one tick
LATENCY_TICKS_FLOOR = max(SIM_TICK_HZ // 10, 1)
RTT_MS = int(os.environ.get("RTT_MS", "0"))
MAX_STEPS = max((RTT_MS * SIM_TICK_HZ + 999) // 1000 + DRAIN_MARGIN, LATENCY_TICKS_FLOOR)
V_MAX_RAD_S = 30.0             # scale for the velocity field, radians a second


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
        self.nv = self.m.nv // n
        self.nu_each = self.m.nu // n
        self.jrange = [(float(self.m.jnt_range[1 + j, 0]), float(self.m.jnt_range[1 + j, 1]))
                       for j in range(self.nu_each)]
        self._jlo = np.array([r[0] for r in self.jrange])
        self._jhi = np.array([r[1] for r in self.jrange])
        self.free = set(range(n))
        self.owner = {}
        # Where each actuator reads its own angle and rate. The controller will need these.
        trn = self.m.actuator_trnid[:, 0]
        self.act_qpos = self.m.jnt_qposadr[trn]
        self.act_qvel = self.m.jnt_dofadr[trn]
        self.pose = self.d.qpos[self.act_qpos].copy()
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
        """Apply what each client is asking their body to do.

        The steering task in `examples/experiments/steering/mlp.py` takes three things and
        this mirrors them: a direction to move, a speed, and a facing that is separate from
        the movement. Separate facing is what makes strafing fall out rather than being added.

        Jump and crouch are not part of that task. They are applied directly here, and a
        learned controller would take them as extra commands rather than as forces.
        """
        self.d.xfrc_applied[:] = 0.0

        for cid, cmd in drives.items():
            i = self.owner.get(cid)
            if i is None:
                continue
            r = self.roots[i]
            mx, my = cmd.get("move", (0.0, 0.0))
            mag = math.hypot(mx, my)
            if mag > 0.0:
                # Drive toward a speed and stop pushing once the body has it. The stick
                # magnitude chooses the speed between a walk and a run; the force needed to
                # close the gap in one tick is capped at PUSH, so a body accelerates hard
                # and then holds, which is what a character controller does.
                want_speed = WALK_SPEED + min(mag, 1.0) * (RUN_SPEED - WALK_SPEED)
                dof = self.m.body_dofadr[r]
                have = self.d.qvel[dof:dof + 2]
                want = np.array([mx / mag, my / mag]) * want_speed
                need = (want - have) * self.m.body_mass[r] / TICK
                over = np.linalg.norm(need)
                if over > PUSH:
                    need *= PUSH / over
                self.d.xfrc_applied[r, 0:2] = need
            if cmd.get("jump"):
                self.d.xfrc_applied[r, 2] = JUMP
            if cmd.get("crouch"):
                self.d.xfrc_applied[r, 2] = -CROUCH
            fx, fy = cmd.get("face", (0.0, 0.0))
            if fx or fy:
                # Torque about z toward the wanted facing, from the body's current heading.
                zaxis = self.d.xmat[r].reshape(3, 3)[:, 0]
                want = math.atan2(fy, fx)
                have = math.atan2(zaxis[1], zaxis[0])
                err = (want - have + math.pi) % (2 * math.pi) - math.pi
                self.d.xfrc_applied[r, 5] = err * FACE_TORQUE
        # One step of 16.7 ms for one frame of 16.7 ms. A crowd in contact is stable here
        # once the drive targets a speed rather than pushing with a constant force. A
        # smaller step does not fix an unbounded drive, it only makes it diverge slower.
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
        n, nu = self.n, self.nu_each
        q = self.d.qpos.reshape(n, self.nq)

        # Muscles: each hinge normalised to its own anatomical range, as the packet's
        # swing-twist field expects.
        ang = q[:, 7:7 + nu]
        lo, hi = self._jlo, self._jhi
        norm = np.where(hi > lo, (ang - lo) / np.maximum(hi - lo, 1e-9) * 2.0 - 1.0, 0.0)
        rot0 = np.clip(norm * 32767, -32767, 32767).astype(np.int16)

        # Velocity, which the packet carries so a client can extrapolate. It was zeroed
        # for a long time; see docs/logbook/wire.md.
        vel = self.d.qvel.reshape(n, self.nv)[:, 6:6 + nu]
        vel0 = np.clip(vel / V_MAX_RAD_S * 32767, -32767, 32767).astype(np.int16)

        pk = empty_packets(n * nu)
        idx = np.arange(n * nu)
        body = idx // nu
        joint = idx % nu
        pk["gid"] = (body.astype(np.uint32) << 16) | joint.astype(np.uint32)
        pk["sub_index"] = joint
        pk["class_owner"] = (CLASS_SKELETON_JOINT << 24) | (body & 0xFFFFFF)
        pk["hlc"] = np.uint32(frame_no << 8)
        pk["rot"][:, 0] = rot0.reshape(-1)
        pk["vel"][:, 0] = vel0.reshape(-1)

        # Only the root carries a position. Every other joint is derived by the client from
        # a bone offset it already has, so its field stays zero and costs nothing on the wire.
        root_um = np.clip(q[:, 0:3] * 1e6, -(2 ** 62), 2 ** 62).astype(np.int64)
        pk["pos"][joint == 0] = root_um

        return struct.pack("<HI", n, frame_no) + pk.tobytes()

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
        clients[cid] = ws; drives[cid] = {}
        await ws.send(json.dumps({"you": mine, **room.geometry()}))
        try:
            async for msg in ws:
                cmd = json.loads(msg)
                drives[cid] = cmd if isinstance(cmd, dict) else {"move": tuple(cmd)}
        except Exception:
            pass
        finally:
            room.release(cid); clients.pop(cid, None); drives.pop(cid, None)

    # The packets are the schema; the compression is the transport. A frame is delta-coded
    # against the previous one and then compressed, which is where the redundancy the packet
    # deliberately leaves in gets taken back. See docs/logbook/wire.md.
    comp = zstd.ZstdCompressor(level=1)

    async def loop():
        """A fixed-timestep accumulator, the shape Godot's MainTimerSync uses.

        The naive version sleeps until the next tick and does nothing when it is late:

            rest = t0 + i * TICK - now
            if rest > 0: await sleep(rest)

        That has two faults and this session hit both. It never yields when behind, so the
        event loop starves and a new connection never finishes its handshake. And it
        accumulates a debt it cannot pay, so one slow frame makes every later frame late,
        which is the spiral of death.

        Godot's answer, and this one: keep an accumulator of real time, spend it in whole
        fixed steps, and cap how many steps one pass may take. Past the cap, throw the
        remaining time away rather than chase it. Physics then runs slower than real time
        under load, which is honest, instead of running late forever and pretending.

        The cap is not Godot's 8. It is `latencyTicks` from the predictive BVH resources
        spec: the lateness a migration is already allowed to have before it is called failed.
        Inside that, being late is something the rest of the system is built to absorb.
        Outside it, the ghost bounds and waypoint periods stop being sound, so continuing to
        chase the debt would be simulating a world nothing else agrees with.
        """
        i = 0
        sent = 0
        accum = 0.0
        prev = None
        last = time.perf_counter()
        t_report = last

        comp = zstd.ZstdCompressor(level=1)

        while True:
            now = time.perf_counter()
            frame_time = now - last
            last = now
            # A pathological stall must not become thousands of steps.
            accum += min(frame_time, TICK * MAX_STEPS)

            steps = 0
            while accum >= TICK and steps < MAX_STEPS:
                room.step(drives)
                accum -= TICK
                steps += 1
                i += 1

                if i % PUBLISH_EVERY == 0 and clients:
                    raw = room.frame(i // PUBLISH_EVERY)
                    if prev is not None and len(prev) == len(raw):
                        d = bytes(a ^ b for a, b in zip(raw, prev))
                        buf = b"\x01" + comp.compress(d)
                    else:
                        buf = b"\x00" + comp.compress(raw)
                    prev = raw
                    sent += len(buf) * len(clients)
                    await asyncio.gather(*[c.send(buf) for c in list(clients.values())],
                                         return_exceptions=True)

            if steps == MAX_STEPS and accum >= TICK:
                # Saturated. Drop the debt and say so: a plane that cannot keep up should
                # run slow visibly, not silently fall further behind.
                dropped = accum
                accum = 0.0
                print(f"[plane] saturated, dropped {dropped*1000:.0f} ms of simulation",
                      flush=True)

            if now - t_report >= 10.0:
                el = now - t_report
                each = sent / max(1, len(clients)) / el / 1000
                print(f"[plane] {i//60}s sim  {len(clients)} clients  "
                      f"{room.cross_contacts()} person-to-person contacts  "
                      f"{each:.2f} kB/s each", flush=True)
                sent = 0
                t_report = now

            # Always yield, whether or not there was time to spare. This is the line whose
            # absence starved the event loop.
            await asyncio.sleep(max(0.0, TICK - accum) if steps else 0)

    async with websockets.serve(handler, "0.0.0.0", PORT, max_size=None):
        print(f"[plane] {N} bodies simulating, publishing on :{PORT}. "
              f"{SIM_TICK_HZ} Hz, at most {MAX_STEPS} steps a pass "
              f"(latencyTicks, {MAX_STEPS*TICK*1000:.0f} ms)", flush=True)
        await loop()


if __name__ == "__main__":
    asyncio.run(main())
