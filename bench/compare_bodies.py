import mujoco, time, statistics, os
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
def bench(path, label, N):
    m=mujoco.MjModel.from_xml_path(path); m.opt.timestep=0.008
    ds=[mujoco.MjData(m) for _ in range(N)]
    for d in ds:
        for _ in range(30): mujoco.mj_step(m,d)
    r=[]
    for _ in range(5):
        t0=time.perf_counter_ns()
        for _ in range(20):
            for d in ds: mujoco.mj_step(m,d)
        r.append((time.perf_counter_ns()-t0)/20/N/1000.0)
    us=statistics.median(r)
    print(f"{label:24} N={N:3}  {us:7.1f} us/body/step  {us*2:7.1f} us/body/frame  (nv={m.nv} nbody={m.nbody} nsite={m.nsite} ntendon={m.ntendon})")
    return us*2
MSK="thirdparty/ms-human-700/MS-Human-700-Locomotion.xml"
AV="assets/tracked_avatar.xml"
for N in (1,28,56,128):
    a=bench(MSK,"musculoskeletal",N); b=bench(AV,"tracked avatar",N)
    print(f"    -> speedup {a/b:.1f}x\n")
