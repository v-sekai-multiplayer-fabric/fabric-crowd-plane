import numpy as np, zstandard as zstd
J=36; F=400; B=16
t=np.arange(F)/20.0
def motion(seed):   # realistic gait: peak joint speed ~2-3 rad/s
    r=np.random.default_rng(seed)
    ph=r.uniform(0,6.28,(J,3)); amp=r.uniform(0.03,0.35,(J,3)); f=r.uniform(0.4,1.4,(J,3))
    return np.sin(2*np.pi*f[None]*t[:,None,None]+ph[None])*amp[None]
rot=np.concatenate([motion(s) for s in range(B)],axis=1)
peak=np.abs(np.diff(rot,axis=0)).max()*20
print(f"peak joint speed {peak:.1f} rad/s   frames {F} bodies {B} joints {J}\n")
c=zstd.ZstdCompressor(level=3)
rng=np.random.default_rng(1)
root=np.cumsum(rng.normal(0,1000,(F,B,3)),axis=0).astype(np.int32)
per=lambda n: n/F/B
def pack(bits):
    q=np.clip(np.round(rot/np.pi*(2**(bits-1)-1)),-(2**(bits-1)),2**(bits-1)-1).astype(np.int32)
    d=np.diff(q,axis=0,prepend=q[:1])
    # bit-pack: 3 axes x bits, rounded up to whole bytes per joint
    nbytes=(3*bits+7)//8
    body=nbytes*J+12
    raw=q.astype(np.int16).tobytes()+root.tobytes()
    dz=len(c.compress(d.astype(np.int16).tobytes()+np.diff(root,axis=0,prepend=root[:1]).tobytes()))
    return body, per(dz)
print(f"{'bits/axis':>10} {'packed B/body/frame':>22} {'delta+zstd B/body/frame':>26}")
for bits in (16,12,10,8):
    body,dz=pack(bits)
    print(f"{bits:>10} {body:>22} {dz:>26.1f}")
