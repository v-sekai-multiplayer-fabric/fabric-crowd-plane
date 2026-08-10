#!/usr/bin/env python3
# The feature: bodies that collide with each other.
#
# Every measurement before this one put each avatar in its own MjData, so avatars passed
# through one another. That is cheaper and it is not the product. A touchable crowd is one
# model, one contact solve, and it is the thing that cannot be divided across machines.
#
# This measures how many people can touch each other at 60 Hz, which is the only number that
# defines what is being sold.
import os, re, sys, time, statistics
import mujoco, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "assets", "tracked_avatar.xml")).read()
BODY = SRC[SRC.index('<body name="pelvis"'): SRC.index('</worldbody>')]
ACT = SRC[SRC.index("<actuator>") + len("<actuator>"): SRC.index("</actuator>")]
TICK_US = 16666


def venue(n, spacing=0.75, iters=10, islands=True):
    bodies, acts = [], []
    side = max(1, int(np.ceil(np.sqrt(n))))
    for i in range(n):
        b = re.sub(r'name="([a-z_]+)"', lambda m: 'name="%s_%d"' % (m.group(1), i), BODY)
        b = re.sub(r'joint="([a-z_]+)"', lambda m: 'joint="%s_%d"' % (m.group(1), i), b)
        x, y = (i % side) * spacing, (i // side) * spacing
        b = b.replace('pos="0 0 0.95"', 'pos="%.3f %.3f 0.95"' % (x, y), 1)
        bodies.append(b)
        acts.append(re.sub(r'joint="([a-z_]+)"',
                           lambda m: 'joint="%s_%d"' % (m.group(1), i), ACT))
    flag = '<flag island="enable"/>' if islands else ''
    return ('<mujoco model="venue"><compiler angle="radian"/>'
            '<option timestep="0.016666" solver="Newton" iterations="%d">%s</option>'
            '<default><geom type="capsule" condim="3" friction="0.9 0.005 0.0001" density="985"/>'
            '<joint type="hinge" damping="2" armature="0.02"/>'
            '<motor ctrlrange="-150 150"/></default>'
            '<worldbody><geom name="floor" type="plane" size="200 200 0.1" density="0"/>%s'
            '</worldbody><actuator>%s</actuator></mujoco>'
            % (iters, flag, "".join(bodies), "".join(acts)))


def run(n, spacing, secs=4.0, iters=10, islands=True):
    m = mujoco.MjModel.from_xml_string(venue(n, spacing, iters, islands))
    d = mujoco.MjData(m)
    geom_body = m.geom_bodyid
    root = np.zeros(m.nbody, dtype=int)          # which avatar each body belongs to
    for b in range(1, m.nbody):
        p = b
        while m.body_parentid[p] != 0:
            p = m.body_parentid[p]
        root[b] = p
    for _ in range(60):
        mujoco.mj_step(m, d)
    work, cross = [], []
    t_end = time.time() + secs
    while time.time() < t_end:
        t0 = time.perf_counter_ns()
        mujoco.mj_step(m, d)
        work.append((time.perf_counter_ns() - t0) / 1000.0)
        c = 0
        for k in range(d.ncon):
            g1, g2 = d.contact.geom1[k], d.contact.geom2[k]
            b1, b2 = geom_body[g1], geom_body[g2]
            if b1 and b2 and root[b1] != root[b2]:
                c += 1
        cross.append(c)
    us = statistics.median(work)
    return us, float(np.percentile(work, 99)), statistics.mean(cross), d.ncon


if __name__ == "__main__":
    print("%5s %8s %9s %11s %14s %8s" % ("n", "us/frame", "us/body", "p99 us", "person-person", "load p99"))
    for n in (25, 50, 100, 200, 400):
        us, p99, xc, ncon = run(n, spacing=0.75)
        print("%5d %8.0f %9.2f %11.0f %14.1f %8.2f"
              % (n, us, us / n, p99, xc, p99 / TICK_US))
