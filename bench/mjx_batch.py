import os, time, statistics
os.environ.setdefault("XLA_FLAGS", "--xla_force_host_platform_device_count=1")
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
import jax, jax.numpy as jp, mujoco
from mujoco import mjx

XML = "thirdparty/ms-human-700/MS-Human-700-Locomotion.xml"
m = mujoco.MjModel.from_xml_path(XML)
m.opt.timestep = 0.008
import numpy as np
print("margins nonzero:", int((m.geom_margin!=0).sum()), " gaps nonzero:", int((m.geom_gap!=0).sum()))
m.geom_margin[:] = 0.0
m.geom_gap[:] = 0.0
print(f"model: {m.nbody} bodies, {m.njnt} joints, {m.nv} dofs, {m.nu} actuators")

try:
    mx = mjx.put_model(m)
except Exception as e:
    print("mjx.put_model FAILED:", type(e).__name__, str(e)[:300]); raise SystemExit(1)

for N in (1, 8, 32, 64):
    d = mjx.make_data(mx)
    batch = jax.vmap(lambda _: d)(jp.arange(N))
    step = jax.jit(jax.vmap(mjx.step, in_axes=(None, 0)))
    t0 = time.perf_counter()
    batch = step(mx, batch); jax.block_until_ready(batch.qpos)
    compile_s = time.perf_counter() - t0

    for _ in range(5):
        batch = step(mx, batch)
    jax.block_until_ready(batch.qpos)

    runs = []
    for _ in range(5):
        t0 = time.perf_counter_ns()
        for _ in range(10):
            batch = step(mx, batch)
        jax.block_until_ready(batch.qpos)
        runs.append((time.perf_counter_ns() - t0) / 10 / 1000.0)
    us = statistics.median(runs)
    print(f"N={N:3}  {us:9.1f} us/step  {us/N:8.1f} us/body/step  {us*2/N:8.1f} us/body/frame  (compile {compile_s:.1f}s)")
