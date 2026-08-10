#!/usr/bin/env python3
# Cheap vs nasty, on skeletal frames rather than the vehicle trace.
#
# nasty = bitpacked rotations. A skeleton is rotations, not positions: a joint's position
#         follows from its parent's rotation and a bone length that never changes, so bone
#         lengths go once at join time. Per body: 36 joints x 3 axes x 12 bits, plus one
#         root position as three i32 micrometres.
# cheap = CBOR-encoded JSON-LD, self-describing, named joints, float rotations. The debug
#         and interop edge, never the hot path.
#
# Reports raw bytes, zstd level 1, and zstd with the previous frame as the dictionary.
import time

import cbor2
import numpy as np
import zstandard as zstd

J, F, B = 36, 300, 16
BITS = 12
JOINT_NAMES = [f"j{i}" for i in range(J)]
CTX = {"@vocab": "https://weft.dev/crowd#", "b": "body", "r": "rot", "p": "root"}


def gait(seed):
    r = np.random.default_rng(seed)
    t = np.arange(F) / 20.0
    ph = r.uniform(0, 6.28, (J, 3))
    amp = r.uniform(0.03, 0.35, (J, 3))
    f = r.uniform(0.4, 1.4, (J, 3))
    return np.sin(2 * np.pi * f[None] * t[:, None, None] + ph[None]) * amp[None]


rot = np.stack([gait(s) for s in range(B)], axis=1)          # F x B x J x 3
root = np.cumsum(
    np.random.default_rng(1).normal(0, 1000, (F, B, 3)), axis=0
).astype(np.int32)

lim = 2 ** (BITS - 1) - 1
q = np.clip(np.round(rot / np.pi * lim), -lim - 1, lim).astype(np.int32)


def nasty_encode(fi):
    out = bytearray()
    for b in range(B):
        out += root[fi, b].tobytes()
        acc = bits = 0
        for j in range(J):
            for a in range(3):
                acc |= (int(q[fi, b, j, a]) & ((1 << BITS) - 1)) << bits
                bits += BITS
                while bits >= 8:
                    out.append(acc & 0xFF)
                    acc >>= 8
                    bits -= 8
        if bits:
            out.append(acc & 0xFF)
    return bytes(out)


def cheap_encode(fi):
    doc = {
        "@context": CTX,
        "@type": "CrowdFrame",
        "step": fi,
        "bodies": [
            {
                "b": b,
                "p": root[fi, b].tolist(),
                "r": {JOINT_NAMES[j]: [float(x) for x in rot[fi, b, j]] for j in range(J)},
            }
            for b in range(B)
        ],
    }
    return cbor2.dumps(doc)


def sizes(blobs):
    c1 = zstd.ZstdCompressor(level=1)
    raw = sum(len(x) for x in blobs)
    indep = sum(len(c1.compress(x)) for x in blobs)
    delta, prev = 0, None
    for x in blobs:
        if prev is None:
            delta += len(c1.compress(x))
        else:
            delta += len(zstd.ZstdCompressor(level=1, dict_data=zstd.ZstdCompressionDict(prev)).compress(x))
        prev = x
    return raw, indep, delta


for name, enc in (("nasty (bitpacked)", nasty_encode), ("cheap (CBOR JSON-LD)", cheap_encode)):
    t0 = time.perf_counter()
    blobs = [enc(i) for i in range(F)]
    ms = (time.perf_counter() - t0) / F * 1000
    raw, indep, delta = sizes(blobs)
    n = F * B
    print(f"{name:22} {raw/n:8.1f} raw   {indep/n:8.1f} zstd   {delta/n:8.1f} zstd-lastframe   B/body/frame"
          f"   encode {ms:6.2f} ms/frame")
