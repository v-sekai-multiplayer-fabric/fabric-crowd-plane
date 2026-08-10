#!/usr/bin/env python3
"""XRGridEntityPacket: the fabric's 100-byte entity packet.

Not invented here. The source of truth is `lean-entity-packet`, whose Lean codec this
mirrors field for field, and whose `packet_golden.csv` this is tested against. A C++ decoder
already passes those vectors; anything written here has to pass them too rather than assert
that it is compatible.

The wire is fully integral. There are no floats in it, which is why it models exactly in Lean
and why a roundtrip property can find codec gaps without rebuilding an engine.

    offset  field         encoding
    0       gid           u32
    4       pos x/y/z     int64 absolute micrometres
    28      vel x/y/z     i16, scaled to V_MAX
    40      hlc           u32, (frame << 8) | counter
    44      class|owner   u32
    48      sub_index     u32
    52      rot           i16 swing-twist x3
    58      payload       42 bytes
"""
import struct
from dataclasses import dataclass, field

SIZE = 100
PAYLOAD_OFFSET = 58
PAYLOAD_LEN = SIZE - PAYLOAD_OFFSET          # 42

_HEAD = struct.Struct("<Iqqq hhh 6x III hhh")   # bytes 34..39 are unused, as in the Lean


@dataclass
class Packet:
    gid: int = 0
    pos_um: tuple = (0, 0, 0)
    vel: tuple = (0, 0, 0)
    hlc: int = 0
    class_owner: int = 0
    sub_index: int = 0
    rot: tuple = (0, 0, 0)
    payload: bytes = field(default_factory=lambda: bytes(PAYLOAD_LEN))

    def encode(self) -> bytes:
        head = _HEAD.pack(self.gid, *self.pos_um, *self.vel,
                          self.hlc, self.class_owner, self.sub_index, *self.rot)
        pay = self.payload[:PAYLOAD_LEN].ljust(PAYLOAD_LEN, b"\0")
        return head + pay

    @classmethod
    def decode(cls, b: bytes) -> "Packet":
        (gid, px, py, pz, vx, vy, vz, hlc, co, si, rx, ry, rz) = _HEAD.unpack_from(b, 0)
        return cls(gid, (px, py, pz), (vx, vy, vz), hlc, co, si, (rx, ry, rz),
                   bytes(b[PAYLOAD_OFFSET:PAYLOAD_OFFSET + PAYLOAD_LEN]))


assert _HEAD.size == PAYLOAD_OFFSET, f"header is {_HEAD.size}, expected {PAYLOAD_OFFSET}"


# ---------------------------------------------------------------------------
# Vectorised encoding.
#
# Building packets one at a time in Python costs more than the physics they
# describe: 40 bodies at 26 muscles is 1040 `encode` calls a frame, and that
# measured 7956 microseconds against 1169 for the simulation step itself.
#
# The layout is fixed, so a numpy structured dtype expresses it exactly and the
# whole frame is filled column by column. `PACKET_DTYPE` is byte-for-byte the
# same as `encode`, which `test_packet_golden.py` checks.
# ---------------------------------------------------------------------------
import numpy as _np

PACKET_DTYPE = _np.dtype([
    ("gid", "<u4"),          # 0
    ("pos", "<i8", 3),       # 4
    ("vel", "<i2", 3),       # 28
    ("_pad", "V6"),          # 34, unused by the spec
    ("hlc", "<u4"),          # 40
    ("class_owner", "<u4"),  # 44
    ("sub_index", "<u4"),    # 48
    ("rot", "<i2", 3),       # 52
    ("payload", "V42"),      # 58
])
assert PACKET_DTYPE.itemsize == SIZE, f"dtype is {PACKET_DTYPE.itemsize}, expected {SIZE}"


def empty(count):
    """A zeroed block of packets, ready to fill column by column."""
    return _np.zeros(count, dtype=PACKET_DTYPE)
