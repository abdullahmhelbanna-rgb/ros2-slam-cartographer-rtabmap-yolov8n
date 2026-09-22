#!/usr/bin/env python3

import sys
import math
import numpy as np
import matplotlib.pyplot as plt


if len(sys.argv) != 4:
    print("Usage:")
    print("python3 plot_gt_vs_slam.py gt.tum slam.tum output.png")
    sys.exit(1)


gt_file = sys.argv[1]
slam_file = sys.argv[2]
out_file = sys.argv[3]


def load_tum(path):
    data = np.loadtxt(path)

    t = data[:, 0]
    x = data[:, 1]
    y = data[:, 2]

    qx = data[:, 4]
    qy = data[:, 5]
    qz = data[:, 6]
    qw = data[:, 7]

    yaw = np.arctan2(
        2.0 * (qw*qz + qx*qy),
        1.0 - 2.0 * (qy*qy + qz*qz)
    )

    return t, x, y, yaw


gt_t, gt_x, gt_y, gt_yaw = load_tum(gt_file)
sl_t, sl_x, sl_y, sl_yaw = load_tum(slam_file)


# ---------------------------------------------------------
# Find GT pose nearest to first SLAM timestamp.
# This reproduces an initial-pose/origin alignment.
# ---------------------------------------------------------

idx = np.argmin(np.abs(gt_t - sl_t[0]))

time_diff = abs(gt_t[idx] - sl_t[0])

if time_diff > 0.02:
    raise RuntimeError(
        f"No GT match for first SLAM pose within 0.02 s. "
        f"Closest difference = {time_diff:.6f} s"
    )

gt0_x = gt_x[idx]
gt0_y = gt_y[idx]
gt0_yaw = gt_yaw[idx]

sl0_x = sl_x[0]
sl0_y = sl_y[0]
sl0_yaw = sl_yaw[0]


# ---------------------------------------------------------
# SE(2) origin alignment
# ---------------------------------------------------------

dyaw = gt0_yaw - sl0_yaw

c = math.cos(dyaw)
s = math.sin(dyaw)

dx = sl_x - sl0_x
dy = sl_y - sl0_y

slam_aligned_x = c * dx - s * dy + gt0_x
slam_aligned_y = s * dx + c * dy + gt0_y


# ---------------------------------------------------------
# Plot
# ---------------------------------------------------------

plt.figure(figsize=(12, 8))

plt.plot(
    gt_x,
    gt_y,
    color="green",
    linewidth=3.0,
    label="Ground Truth"
)

plt.plot(
    slam_aligned_x,
    slam_aligned_y,
    color="red",
    linewidth=1.5,
    label="Cartographer SLAM"
)

# Start position
plt.scatter(
    gt_x[idx],
    gt_y[idx],
    s=70,
    marker="o",
    color="black",
    label="Start"
)

plt.xlabel("X [m]", fontsize=12)
plt.ylabel("Y [m]", fontsize=12)

plt.title(
    "Trajectory Comparison – Ground Truth vs Cartographer",
    fontsize=14
)

plt.grid(True, alpha=0.5)
plt.legend(fontsize=11)

# Important for trajectory geometry
plt.axis("equal")

plt.tight_layout()

plt.savefig(
    out_file,
    dpi=300,
    bbox_inches="tight"
)

print("======================================")
print("Trajectory plot created successfully")
print("GT samples   :", len(gt_x))
print("SLAM samples :", len(sl_x))
print("First timestamp difference:", time_diff, "s")
print("Yaw alignment:", math.degrees(dyaw), "deg")
print("Saved:", out_file)
print("======================================")

plt.show()
