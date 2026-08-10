#!/usr/bin/env python3
# An idle stance controller that holds itself up, with nothing to hold on to.
#
# An earlier draft pulled each root toward its waist tracker. That is cheap and it assumes a
# headset. An unattended body has no tracker, and a crowd is mostly unattended bodies, so the
# avatar has to stand on its own feet.
#
# So there is no external force anywhere here. Only the 26 actuators the model already has.
#
#   pose   PD torque toward the stance pose
#   ankle  the linear inverted pendulum strategy. A standing body is a pendulum hinged at
#          the ankle, so the ankle torque that arrests a lean is proportional to how far the
#          centre of mass has travelled from the middle of the feet.
#
# Gains are derived, not chosen. The pose gain spends the actuator's full 150 Nm at half a
# radian of error and is critically damped. The ankle gain is the pendulum's own: to hold a
# body of mass m at a lean of x metres takes m g x, so the gain IS m g and there is nothing
# to tune in it.
import os, statistics, sys, time

import mujoco
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from touchable import venue, TICK_US

JOINT_FULL_TORQUE_RAD = 0.5
G = 9.81


def run(n, spacing, secs=4.0, control=True, push_at=None):
    m = mujoco.MjModel.from_xml_string(venue(n, spacing))
    d = mujoco.MjData(m)
    roots = np.array([b for b in range(1, m.nbody) if m.body_parentid[b] == 0])
    nq_each, nv_each, nu_each = m.nq // n, m.nv // n, m.nu // n
    mass_each = float(m.body_subtreemass[roots[0]])

    jq = np.concatenate([np.arange(i * nq_each + 7, i * nq_each + 7 + nu_each) for i in range(n)])
    jv = np.concatenate([np.arange(i * nv_each + 6, i * nv_each + 6 + nu_each) for i in range(n)])
    qref = m.qpos0[jq].copy()
    lo, hi = m.actuator_ctrlrange[:, 0].copy(), m.actuator_ctrlrange[:, 1].copy()
    jkp = float(hi[0]) / JOINT_FULL_TORQUE_RAD
    jkd = 2.0 * np.sqrt(jkp * float(np.mean(m.dof_armature[6:]) + 0.05))

    name = lambda i: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i)
    feetL = np.array([b for b in range(m.nbody) if (name(b) or "").startswith("foot_l")])
    feetR = np.array([b for b in range(m.nbody) if (name(b) or "").startswith("foot_r")])
    # ankle pitch actuators, one pair per avatar, in model order
    act_names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, a) for a in range(m.nu)]
    jnt_of_act = m.actuator_trnid[:, 0]
    jnames = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) for j in jnt_of_act]
    ank_y = np.array([a for a, jn in enumerate(jnames) if jn and jn.startswith("ank_l_y")
                      or jn and jn.startswith("ank_r_y")])
    ank_owner = ank_y // nu_each

    geom_body = m.geom_bodyid
    root_of = np.zeros(m.nbody, dtype=int)
    for b in range(1, m.nbody):
        p = b
        while m.body_parentid[p] != 0:
            p = m.body_parentid[p]
        root_of[b] = p

    ankle_kp = mass_each * G          # the pendulum's own gain. Nothing to tune.

    def control_step():
        np.clip(jkp * (qref - d.qpos[jq]) - jkd * d.qvel[jv], lo, hi, out=d.ctrl)
        com = d.subtree_com[roots]                       # per-avatar centre of mass
        mid = 0.5 * (d.xpos[feetL] + d.xpos[feetR])      # middle of the feet
        lean = com[:, 0] - mid[:, 0]                     # forward lean, metres
        leanv = d.cvel[roots][:, 3]                      # its rate
        tau = np.clip(-ankle_kp * lean - 0.3 * ankle_kp * leanv, lo[0], hi[0])
        d.ctrl[ank_y] += tau[ank_owner]
        np.clip(d.ctrl, lo, hi, out=d.ctrl)

    for i in range(120):
        if control:
            control_step()
        mujoco.mj_step(m, d)

    work, cross, h = [], [], []
    t_end = time.time() + secs
    while time.time() < t_end:
        t0 = time.perf_counter_ns()
        if control:
            control_step()
        mujoco.mj_step(m, d)
        work.append((time.perf_counter_ns() - t0) / 1000.0)
        c = 0
        for k in range(d.ncon):
            b1, b2 = geom_body[d.contact.geom1[k]], geom_body[d.contact.geom2[k]]
            if b1 and b2 and root_of[b1] != root_of[b2]:
                c += 1
        cross.append(c)
        h.append(float(np.mean(d.xpos[roots][:, 2])))
    return (statistics.median(work), float(np.percentile(work, 99)),
            statistics.mean(cross), h[-1], statistics.mean(h))


if __name__ == "__main__":
    print("%5s %8s %10s %9s %14s %10s %9s" %
          ("n", "control", "us/frame", "p99 us", "person-person", "pelvis z", "load p99"))
    for n in (100, 200):
        for ctl in (False, True):
            us, p99, xc, hz, hm = run(n, 0.75, control=ctl)
            print("%5d %8s %10.0f %9.0f %14.1f %10.2f %9.2f"
                  % (n, "on" if ctl else "off", us, p99, xc, hz, p99 / TICK_US))
