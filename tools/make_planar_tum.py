#!/usr/bin/env python3

import sys
import math


if len(sys.argv) != 3:
    print("Usage: make_planar_tum.py input.tum output.tum")
    sys.exit(1)

src = sys.argv[1]
dst = sys.argv[2]

total = 0
kept = 0
skipped = 0
last_t = None

with open(src, "r") as fin, open(dst, "w") as fout:

    for line in fin:

        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split()

        if len(parts) != 8:
            print("Skipping malformed line:", line)
            skipped += 1
            continue

        total += 1

        t, x, y, z, qx, qy, qz, qw = map(float, parts)

        # Require strictly increasing timestamps.
        # Duplicate/stale samples are removed.
        if last_t is not None and t <= last_t:
            skipped += 1
            continue

        # Extract yaw from the original quaternion.
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)

        yaw = math.atan2(siny_cosp, cosy_cosp)

        # Build a pure planar quaternion:
        # roll = 0, pitch = 0, yaw = original yaw
        planar_qx = 0.0
        planar_qy = 0.0
        planar_qz = math.sin(yaw / 2.0)
        planar_qw = math.cos(yaw / 2.0)

        fout.write(
            f"{t:.9f} "
            f"{x:.9f} "
            f"{y:.9f} "
            f"0.000000000 "
            f"{planar_qx:.9f} "
            f"{planar_qy:.9f} "
            f"{planar_qz:.9f} "
            f"{planar_qw:.9f}\n"
        )

        last_t = t
        kept += 1


print("===== PLANAR TUM CONVERSION =====")
print("Input :", src)
print("Output:", dst)
print("Input samples   :", total)
print("Kept samples    :", kept)
print("Skipped samples :", skipped)
print("=================================")
