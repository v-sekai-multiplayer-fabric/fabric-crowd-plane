#!/usr/bin/env python3
# Does a long dictionary of previous frames pay, and what does it cost in delivery?
#
# Four schemes, same muscle-space frames:
#   independent   every frame compressed alone. Survives any loss. The current design.
#   static dict   a dictionary trained offline on other people's motion, shipped with the
#                 client, never updated. Still stateless per frame, so still loss-proof.
#   GOP           a keyframe every N frames, each later frame using the keyframe as its
#                 dictionary. Loss costs the rest of the group.
#   streaming     one compressor for the whole session, full history. Needs reliable
#                 ordered delivery, and one lost datagram desynchronises the decoder.
import numpy as np, zstandard as zstd

MAXD = np.array([40,40,40,40,40,40,20,20,20,40,40,40,40,40,40,
                 50,60,60,80,90,50,30,50, 50,60,60,80,90,50,30,50,
                 30,15,100,100,90,80,90,80,40, 30,15,100,100,90,80,90,80,40], float)
MIND = np.array([-40,-40,-40,-40,-40,-40,-20,-20,-20,-40,-40,-40,-40,-40,-40,
                 -90,-60,-60,-80,-90,-50,-30,-50, -90,-60,-60,-80,-90,-50,-30,-50,
                 -15,-15,-60,-100,-90,-80,-90,-80,-40, -15,-15,-60,-100,-90,-80,-90,-80,-40], float)
M=len(MAXD); F=600; B=16; PREC=0.088; ROOT=12
bits=np.ceil(np.log2((MAXD-MIND)/PREC)).astype(int)

def gait(seed, F=F):
    r=np.random.default_rng(seed); t=np.arange(F)/20.0
    ph=r.uniform(0,6.28,M); amp=r.uniform(0.1,0.7,M); f=r.uniform(0.4,1.4,M)
    a=np.sin(2*np.pi*f[None]*t[:,None]+ph[None])*amp[None]
    a[:, r.random(M)<0.35]*=0.02
    return np.clip(a,-1,1)

def frames(seeds):
    mus=np.stack([gait(s) for s in seeds],axis=1)
    q=np.round((mus+1)/2*(2**bits-1)).astype(np.int32)
    d=np.diff(q,axis=0,prepend=q[:1]).astype(np.int16)
    return [d[i].tobytes() for i in range(F)]        # one blob per frame, all bodies

live  = frames(range(B))                              # the session
train = frames(range(100, 100+B))                     # other people, for the dictionary
n = F*B
per = lambda tot: tot/n + ROOT

L=3
print(f"{M} muscles, {F} frames, {B} bodies, zstd level {L}\n")
print(f"{'scheme':34} {'B/body/frame':>13}  delivery")

c=zstd.ZstdCompressor(level=L)
print(f"{'  independent frames':34} {per(sum(len(c.compress(b)) for b in live)):13.1f}  any loss ok")

dct=zstd.train_dictionary(110*1024, train, level=L)
cd=zstd.ZstdCompressor(level=L, dict_data=dct)
print(f"{'  static trained dictionary':34} {per(sum(len(cd.compress(b)) for b in live)):13.1f}  any loss ok  ({len(dct.as_bytes())//1024} KiB, shipped once)")

for gop in (20, 60):
    tot=0
    for i in range(0, F, gop):
        key=live[i]; tot+=len(c.compress(key))
        kd=zstd.ZstdCompressor(level=L, dict_data=zstd.ZstdCompressionDict(key))
        for b in live[i+1:i+gop]: tot+=len(kd.compress(b))
    print(f"{'  keyframe every '+str(gop)+' frames':34} {per(tot):13.1f}  loss costs {gop/20:.0f}s")

cs=zstd.ZstdCompressor(level=L).compressobj()
tot=sum(len(cs.compress(b)) for b in live)+len(cs.flush())
print(f"{'  streaming, full history':34} {per(tot):13.1f}  needs reliable ordered")
