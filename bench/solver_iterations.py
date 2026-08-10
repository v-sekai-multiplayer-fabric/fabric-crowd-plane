import mujoco, time, statistics, numpy as np, os
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
XML="assets/tracked_avatar.xml"; N=28
def run(it):
    m=mujoco.MjModel.from_xml_path(XML); m.opt.timestep=1/60; m.opt.iterations=it
    ds=[mujoco.MjData(m) for _ in range(N)]
    for d in ds:
        for _ in range(40): mujoco.mj_step(m,d)
    r=[]
    for _ in range(5):
        t0=time.perf_counter_ns()
        for _ in range(20):
            for d in ds: mujoco.mj_step(m,d)
        r.append((time.perf_counter_ns()-t0)/20/N/1000.0)
    us=statistics.median(r)
    # quality: worst contact penetration, and solver residual, over a long driven run
    d=ds[0]; rng=np.random.default_rng(0); worst=0.0; bad=0
    for i in range(1200):
        d.ctrl[:]=60*np.sin(2*np.pi*np.arange(m.nu)*0.01+i*0.05)
        mujoco.mj_step(m,d)
        if d.ncon: worst=min(worst, d.contact.dist[:d.ncon].min())
        if not np.all(np.isfinite(d.qpos)): bad+=1
    pp=45+280+2433+int(us*1000)
    cap=16666000//(2433+(pp-2433)//2)
    print(f"iterations={it:3}  {us:6.2f} us/body/step   deepest penetration {worst*1000:6.2f} mm   nonfinite {bad}   -> {cap} people on 2 cores")
for it in (10,4,2,1): run(it)
