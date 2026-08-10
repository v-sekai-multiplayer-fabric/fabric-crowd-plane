#!/usr/bin/env python3
"""Differential test against the Lean canonical bytes.

`packet_golden.csv` is emitted by `lake exe packet_emit` in `lean-entity-packet`. Each row
carries the hex of a canonical packet plus the fields it decodes to. This checks both
directions: our decode must reproduce the fields, and our encode must reproduce the bytes.
"""
import csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entity_packet import Packet, SIZE

GOLDEN = os.environ.get("GOLDEN", os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "lean-entity-packet", "packet_golden.csv"))


def main():
    ok = bad = 0
    with open(GOLDEN) as fh:
        for row in csv.DictReader(fh):
            raw = bytes.fromhex(row["hex"])
            assert len(raw) == SIZE, f"golden row is {len(raw)} bytes, expected {SIZE}"
            p = Packet.decode(raw)
            checks = [
                ("gid", p.gid, int(row["gid"])),
                ("pos.x", p.pos_um[0], int(row["pumx"])),
                ("pos.y", p.pos_um[1], int(row["pumy"])),
                ("pos.z", p.pos_um[2], int(row["pumz"])),
                ("vel.x", p.vel[0], int(row["velx"])),
                ("vel.y", p.vel[1], int(row["vely"])),
                ("vel.z", p.vel[2], int(row["velz"])),
                ("pay0", p.payload[0], int(row["pay0"])),
                ("pay41", p.payload[41], int(row["pay41"])),
            ]
            for name, got, want in checks:
                if got != want:
                    print(f"  MISMATCH {name}: got {got}, want {want}")
                    bad += 1
                    break
            else:
                if p.encode() != raw:
                    print(f"  RE-ENCODE MISMATCH for gid {p.gid}")
                    bad += 1
                else:
                    ok += 1
    print(f"golden vectors: {ok} pass, {bad} fail")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
