import time, statistics, mujoco, numpy as np, os
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
XML="thirdparty/ms-human-700/MS-Human-700-Locomotion.xml"
N=28
def run(label, mutate):
    m=mujoco.MjModel.from_xml_path(XML); m.opt.timestep=0.008
    mutate(m)
    ds=[mujoco.MjData(m) for _ in range(N)]
    def step():
        for d in ds: mujoco.mj_step(m,d)
    for _ in range(20): step()
    r=[]
    for _ in range(5):
        t0=time.perf_counter_ns()
        for _ in range(20): step()
        r.append((time.perf_counter_ns()-t0)/20/1000.0)
    us=statistics.median(r)
    print(f"{label:38} {us:9.1f} us/step  {us/N:7.1f} us/body  {us*2/N:7.1f} us/body/frame")
    return us/N

base = run("baseline", lambda m: None)
run("margins zeroed", lambda m: m.geom_margin.__setitem__(slice(None), 0.0))
def nomesh(m):
    for i in range(m.ngeom):
        if m.geom_type[i]==7: m.geom_contype[i]=0; m.geom_conaffinity[i]=0
run("collision meshes disabled", nomesh)
def nocontact(m):
    m.geom_contype[:]=0; m.geom_conaffinity[:]=0
run("ALL contact disabled", nocontact)
def notendon(m):
    m.opt.disableflags |= mujoco.mjtDisableBit.mjDSBL_ACTUATION
run("actuation disabled (muscles off)", notendon)
def both(m):
    nocontact(m); notendon(m)
run("no contact AND no actuation", both)
