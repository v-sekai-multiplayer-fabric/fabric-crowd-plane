import mujoco, os, numpy as np, time
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
m=mujoco.MjModel.from_xml_path('thirdparty/ms-human-700/MS-Human-700-Locomotion.xml')
m.opt.timestep=0.008
T=mujoco.mjtTimer
names=[t for t in dir(T) if t.startswith('mjTIMER')]
N=28
ds=[mujoco.MjData(m) for _ in range(N)]
for d in ds:
    for _ in range(20): mujoco.mj_step(m,d)
for d in ds:
    for t in d.timer: t.duration=0; t.number=0
K=50
t0=time.perf_counter_ns()
for _ in range(K):
    for d in ds: mujoco.mj_step(m,d)
wall=(time.perf_counter_ns()-t0)/K/N/1000.0
tot=np.zeros(len(ds[0].timer))
for d in ds:
    for i in range(len(d.timer)):
        tot[i]+=d.timer[i].duration
rows=[]
for nm in names:
    i=int(getattr(T,nm))
    us=tot[i]/K/N*1e6 if tot[i] else 0.0
    if us>0.5: rows.append((us,nm.replace('mjTIMER_','')))
rows.sort(reverse=True)
print(f"wall {wall:.1f} us/body/step   (batch of {N})")
for us,nm in rows: print(f"  {nm:16} {us:8.1f} us  {us/wall*100:5.1f}%")
