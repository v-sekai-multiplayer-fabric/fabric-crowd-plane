#!/usr/bin/env python3
# The gate: what one MS-Human-700 body costs for one 60 Hz frame on one core.
#
# Python, on purpose. This measures MuJoCo's C engine through a thin binding, and the
# binding costs about a microsecond against a step that costs five hundred. The plane
# itself is C++ and has no Python in it.
#
#   python -m venv env && env/bin/pip install mujoco
#   git clone --depth 1 https://github.com/LNSGroup/MS-Human-700.git
#   env/bin/python bench/gate_msk_step.py
#
# Every number in spec/CrowdBudget.lean that depends on the body cost comes from here.
import time, statistics, mujoco, os
MODEL = os.environ.get("MSH", "MS-Human-700/MS-Human-700.xml")
os.chdir(os.path.dirname(MODEL) or ".")
MODEL = os.path.basename(MODEL)

m = mujoco.MjModel.from_xml_path(MODEL)
d = mujoco.MjData(m)

print(f"bodies={m.nbody} joints={m.njnt} dofs={m.nv} actuators={m.nu} tendons={m.ntendon}")
print(f"timestep={m.opt.timestep*1000:.3f} ms  solver={m.opt.solver} iterations={m.opt.iterations}")

FRAME_US = 16666      # spec/CrowdBudget.lean, tickUs
BUDGET_US = 14360     # spec/CrowdBudget.lean, biomechUs
substeps = round((FRAME_US/1e6) / m.opt.timestep)
print(f"substeps for one 60 Hz frame = {substeps}")

for _ in range(200):           # settle, and let any lazy allocation happen
    mujoco.mj_step(m, d)

def time_steps(n):
    t0 = time.perf_counter_ns()
    for _ in range(n):
        mujoco.mj_step(m, d)
    return (time.perf_counter_ns() - t0) / n / 1000.0   # us per step

runs = [time_steps(200) for _ in range(9)]
per_step = statistics.median(runs)
per_frame = per_step * substeps

print()
print(f"one mj_step      : {per_step:8.1f} us   (median of 9 x 200)")
print(f"one 60 Hz frame  : {per_frame:8.1f} us   ({substeps} substeps)")
print(f"budget           :  {BUDGET_US:8.1f} us   (spec/CrowdBudget.lean, biomechUs)")
print(f"BODIES PER PLANE : {int(BUDGET_US // per_frame)}")
print(f"PLANES FOR 1000  : {-(-1000 // max(int(BUDGET_US // per_frame),1))}")
