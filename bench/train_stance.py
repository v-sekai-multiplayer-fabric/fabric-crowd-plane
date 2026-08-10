#!/usr/bin/env python3
# A learned idle stance, trained with Augmented Random Search.
#
# A derived controller did not hold a stance: PD to a pose plus an ankle strategy falls in
# five seconds. Standing balance for a 27 degree of freedom humanoid is not a gain, so this
# learns one instead.
#
# The policy is LINEAR: one matrix from observation to torque. ARS is known to solve MuJoCo
# benchmarks with linear policies, and a linear policy is the smallest trained thing that
# could work. It matters here because inference for a whole crowd is then a single matmul,
# and because a matrix can be read, stored, and diffed, which a network cannot.
#
# This is a trained model, and a trained model is the largest tuning constant a system can
# have. weft's rule against them is deliberately overridden here, by decision, and the cost
# is that the stance is now fitted to whatever this training saw.
import os, sys, time
import mujoco, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "..", "assets", "tracked_avatar.xml")
STAND_Z = 0.95


class Env:
    def __init__(self, seed=0):
        self.m = mujoco.MjModel.from_xml_path(XML)
        self.m.opt.timestep = 1 / 60
        self.m.opt.iterations = 10
        self.d = mujoco.MjData(self.m)
        self.nu = self.m.nu
        self.rng = np.random.default_rng(seed)
        b = lambda n: mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, n)
        self.fl, self.fr, self.pelvis = b("foot_l"), b("foot_r"), b("pelvis")
        self.lo = self.m.actuator_ctrlrange[:, 0]
        self.hi = self.m.actuator_ctrlrange[:, 1]

    def reset(self, jitter=0.05):
        mujoco.mj_resetData(self.m, self.d)
        self.d.qpos[7:] += self.rng.normal(0, jitter, self.m.nq - 7)
        self.d.qvel[:] += self.rng.normal(0, jitter, self.m.nv)
        mujoco.mj_forward(self.m, self.d)
        return self.obs()

    def obs(self):
        d, m = self.d, self.m
        zax = d.xmat[self.pelvis].reshape(3, 3)[:, 2]
        mid = 0.5 * (d.xpos[self.fl] + d.xpos[self.fr])
        com = d.subtree_com[self.pelvis]
        return np.concatenate([
            d.qpos[7:],                 # 26 joint angles
            np.clip(d.qvel[6:], -20, 20) * 0.1,   # 26 joint rates
            zax,                        # 3, pelvis up-axis: the tilt
            np.clip(d.cvel[self.pelvis], -10, 10) * 0.1,   # 6
            (com - mid)[:2] * 10.0,     # 2, lean over the feet
            [d.xpos[self.pelvis][2] - STAND_Z],   # 1, height error
        ])

    def step(self, a):
        self.d.ctrl[:] = np.clip(a, self.lo, self.hi)
        mujoco.mj_step(self.m, self.d)
        z = self.d.xpos[self.pelvis][2]
        zax = self.d.xmat[self.pelvis].reshape(3, 3)[2, 2]
        mid = 0.5 * (self.d.xpos[self.fl] + self.d.xpos[self.fr])
        lean = np.linalg.norm(self.d.subtree_com[self.pelvis][:2] - mid[:2])
        r = (2.0 * min(z / STAND_Z, 1.0)      # stand tall
             + 1.0 * max(zax, 0.0)            # stay upright
             - 2.0 * lean                     # keep the mass over the feet
             - 0.001 * float(np.square(self.d.ctrl).mean()))
        done = z < 0.45
        return self.obs(), r, done


def rollout(env, W, mu, sig, T=240):
    o = env.reset()
    tot, n = 0.0, 0
    s1 = np.zeros_like(mu); s2 = np.zeros_like(mu)
    for _ in range(T):
        on = (o - mu) / sig
        o, r, done = env.step(W @ on)
        s1 += o; s2 += o * o; n += 1
        tot += r
        if done:
            break
    return tot, s1, s2, n


def train(iters=300, ndir=16, top=8, alpha=0.015, nu_=0.025, seed=0):
    env = Env(seed)
    nobs = len(env.reset())
    W = np.zeros((env.nu, nobs))
    mu = np.zeros(nobs); var = np.ones(nobs); cnt = 1e-4
    t0 = time.time()
    for it in range(iters):
        sig = np.sqrt(np.maximum(var, 1e-6))
        deltas = [np.random.default_rng(seed * 100000 + it * 100 + k).normal(0, 1, W.shape)
                  for k in range(ndir)]
        rp, rm = [], []
        S1 = np.zeros(nobs); S2 = np.zeros(nobs); N = 0
        for dW in deltas:
            a, s1, s2, n = rollout(env, W + nu_ * dW, mu, sig); rp.append(a); S1 += s1; S2 += s2; N += n
            b, s1, s2, n = rollout(env, W - nu_ * dW, mu, sig); rm.append(b); S1 += s1; S2 += s2; N += n
        rp, rm = np.array(rp), np.array(rm)
        order = np.argsort(-np.maximum(rp, rm))[:top]
        sr = np.concatenate([rp[order], rm[order]]).std() + 1e-6
        step = sum((rp[k] - rm[k]) * deltas[k] for k in order)
        W += alpha / (top * sr) * step
        if N:
            newc = cnt + N
            dmu = S1 / N - mu
            mu += dmu * N / newc
            var = (var * cnt + (S2 - N * (S1 / N) ** 2) + dmu ** 2 * cnt * N / newc) / newc
            cnt = newc
        if it % 250 == 0 or it == iters - 1:
            ev, _, _, _ = rollout(env, W, mu, np.sqrt(np.maximum(var, 1e-6)), T=600)
            print(f"  iter {it:4}  eval return {ev:8.1f}  ({time.time()-t0:5.0f}s)", flush=True)
    return W, mu, np.sqrt(np.maximum(var, 1e-6))


if __name__ == "__main__":
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    W, mu, sig = train(iters)
    np.savez(os.path.join(HERE, "stance_policy.npz"), W=W, mu=mu, sig=sig)
    print(f"saved policy: {W.shape[0]} x {W.shape[1]} = {W.size} parameters")
