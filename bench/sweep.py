import mujoco, os, time, statistics, numpy as np
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
XML="assets/tracked_avatar.xml"
FRAME=1.0/60
def bench(label, ts, mutate=None, N=28):
    m=mujoco.MjModel.from_xml_path(XML); m.opt.timestep=ts
    if mutate: mutate(m)
    sub=max(1,round(FRAME/ts))
    ds=[mujoco.MjData(m) for _ in range(N)]
    for d in ds:
        for _ in range(40): mujoco.mj_step(m,d)
    r=[]
    for _ in range(5):
        t0=time.perf_counter_ns()
        for _ in range(20):
            for d in ds: mujoco.mj_step(m,d)
        r.append((time.perf_counter_ns()-t0)/20/N/1000.0)
    us=statistics.median(r); frame=us*sub
    bodies=13908//max(1,int(frame)); planes=(1000+bodies-1)//bodies
    print(f"{label:34} ts={ts*1000:4.1f}ms x{sub}  {us:6.2f} us/step  {frame:6.2f} us/frame  {bodies:5d} bodies/core  {planes:2d} planes")
    return frame
bench("baseline", 0.008)
for ts in (0.0125, 1/60, 0.02):
    bench("timestep", ts)
def it(n):
    return lambda m: setattr(m.opt,'iterations',n)
for n in (5,2,1):
    bench(f"iterations={n}", 1/60, it(n))
def nolimit(m): m.opt.disableflags |= mujoco.mjtDisableBit.mjDSBL_LIMIT
bench("no joint limits", 1/60, nolimit)
def c1(m): m.geom_condim[:]=1
bench("condim=1 (frictionless)", 1/60, c1)
def combo(m):
    m.opt.iterations=2; nolimit(m)
bench("iterations=2 + no limits", 1/60, combo)
