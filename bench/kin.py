import mujoco, os, time, statistics, numpy as np
os.chdir("/tmp/claude-1001/-home-ernest-lee-Desktop-weft/90f7842b-96e7-4244-9b1b-3bd40662f275/scratchpad/crowd")
m=mujoco.MjModel.from_xml_path("assets/tracked_avatar.xml"); m.opt.timestep=1/60
N=28; ds=[mujoco.MjData(m) for _ in range(N)]
for d in ds:
    for _ in range(40): mujoco.mj_step(m,d)
def timeit(label, fn, sub=1):
    for _ in range(5): fn()
    r=[]
    for _ in range(7):
        t0=time.perf_counter_ns()
        for _ in range(20): fn()
        r.append((time.perf_counter_ns()-t0)/20/N/1000.0)
    us=statistics.median(r)*sub
    bodies=13908//max(1,int(np.ceil(us))); planes=(1000+bodies-1)//bodies
    print(f"{label:40} {us:6.2f} us/body/frame  {bodies:5d} bodies/core  {planes:2d} planes")
    return us
timeit("full forward dynamics (mj_step)", lambda:[mujoco.mj_step(m,d) for d in ds])
timeit("mj_kinematics only", lambda:[mujoco.mj_kinematics(m,d) for d in ds])
def posed():
    for d in ds:
        mujoco.mj_kinematics(m,d); mujoco.mj_comPos(m,d)
timeit("kinematics + comPos (posed body)", posed)
# damped least squares IK: 6 tracked targets, 3 iterations
bodies_ik=[mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_BODY,n) for n in
           ("head","lower_arm_l","lower_arm_r","pelvis","foot_l","foot_r")]
jacp=np.zeros((3,m.nv)); jacr=np.zeros((3,m.nv))
J=np.zeros((6*len(bodies_ik), m.nv)); err=np.zeros(6*len(bodies_ik))
def ik():
    for d in ds:
        for _ in range(3):
            mujoco.mj_kinematics(m,d); mujoco.mj_comPos(m,d)
            for k,b in enumerate(bodies_ik):
                mujoco.mj_jacBody(m,d,jacp,jacr,b)
                J[6*k:6*k+3]=jacp; J[6*k+3:6*k+6]=jacr
                err[6*k:6*k+3]=0.01
            dq=np.linalg.solve(J.T@J+1e-3*np.eye(m.nv), J.T@err)
            mujoco.mj_integratePos(m,d.qpos,dq,1.0)
timeit("DLS IK, 6 targets, 3 iterations", ik)
