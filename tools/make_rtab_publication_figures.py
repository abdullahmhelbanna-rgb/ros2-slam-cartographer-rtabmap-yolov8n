#!/usr/bin/env python3

from pathlib import Path
import argparse
import math
import numpy as np
import yaml
from PIL import Image
import matplotlib.pyplot as plt


def yaw(qx, qy, qz, qw):
    return math.atan2(
        2.0 * (qw*qz + qx*qy),
        1.0 - 2.0 * (qy*qy + qz*qz)
    )


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


parser = argparse.ArgumentParser()
parser.add_argument("experiment", type=int)
args = parser.parse_args()

exp = args.experiment

run = (
    Path.home()
    / "turtlebot3_ws/metrics/experiments/rtab"
    / f"experiment_{exp:02d}"
)

figdir = run / "figures"

# Use the same planar-clean trajectories used by the official
# EVO evaluation whenever they are available.
gt_clean = run / "gt_planar_clean.tum"
slam_clean = run / "slam_planar_clean.tum"

gt_file = gt_clean if gt_clean.is_file() else run / "gt_tum.txt"
slam_file = slam_clean if slam_clean.is_file() else run / "slam_tum.txt"

pgm = figdir / f"rtab_run{exp:02d}_map.pgm"
yaml_file = figdir / f"rtab_run{exp:02d}_map.yaml"

for p in [gt_file, slam_file, pgm, yaml_file]:
    if not p.is_file():
        raise SystemExit(f"Missing: {p}")

gt = np.loadtxt(gt_file)
slam = np.loadtxt(slam_file)

if gt.ndim == 1:
    gt = gt.reshape(1, -1)

if slam.ndim == 1:
    slam = slam.reshape(1, -1)

MAX_DIFF = 0.02

# Use EVO's own timestamp association implementation so that the
# publication figures use exactly the same correspondence rule as
# the official APE/RPE evaluation.
try:
    from evo.core import sync as evo_sync
except ImportError as e:
    raise SystemExit(f"Could not import evo.core.sync: {e}")

# SLAM must be the primary (sparser) trajectory.
# This matches the official validation denominator:
# matched SLAM poses / total clean SLAM poses.
sidx, gidx = evo_sync.matching_time_indices(
    slam[:, 0],
    gt[:, 0],
    max_diff=MAX_DIFF
)

gidx = np.asarray(gidx, dtype=int)
sidx = np.asarray(sidx, dtype=int)

if len(gidx) < 2:
    raise SystemExit("Too few associated poses.")

# Keep the associated trajectories ordered chronologically.
order = np.argsort(sidx)
gidx = gidx[order]
sidx = sidx[order]

dt = np.abs(gt[gidx, 0] - slam[sidx, 0])

g = gt[gidx].copy()
s = slam[sidx].copy()

gy0 = yaw(*g[0, 4:8])
sy0 = yaw(*s[0, 4:8])

dyaw = wrap(sy0 - gy0)

c = math.cos(dyaw)
ss = math.sin(dyaw)

R = np.array([
    [c, -ss],
    [ss, c]
])

g0 = g[0, 1:3].copy()
s0 = s[0, 1:3].copy()

ga = g.copy()

for i in range(len(ga)):
    xy = R @ (g[i, 1:3] - g0) + s0

    ga[i, 1] = xy[0]
    ga[i, 2] = xy[1]
    ga[i, 3] = 0.0

    yy = wrap(yaw(*g[i, 4:8]) + dyaw)

    ga[i, 4] = 0.0
    ga[i, 5] = 0.0
    ga[i, 6] = math.sin(yy / 2.0)
    ga[i, 7] = math.cos(yy / 2.0)

sa = s.copy()

for i in range(len(sa)):
    yy = yaw(*sa[i, 4:8])

    sa[i, 3] = 0.0
    sa[i, 4] = 0.0
    sa[i, 5] = 0.0
    sa[i, 6] = math.sin(yy / 2.0)
    sa[i, 7] = math.cos(yy / 2.0)

ga[:, 0] = sa[:, 0]

gt_out = run / "gt_associated_origin_aligned.tum"
slam_out = run / "slam_associated.tum"

np.savetxt(gt_out, ga, fmt="%.9f")
np.savetxt(slam_out, sa, fmt="%.9f")

with open(yaml_file) as f:
    meta = yaml.safe_load(f)

res = float(meta["resolution"])
ox = float(meta["origin"][0])
oy = float(meta["origin"][1])

img = np.asarray(Image.open(pgm))
h, w = img.shape

extent = [
    ox,
    ox + w * res,
    oy,
    oy + h * res
]


def save(fig, stem):
    fig.savefig(
        figdir / f"{stem}.png",
        dpi=600,
        bbox_inches="tight"
    )

    fig.savefig(
        figdir / f"{stem}.pdf",
        bbox_inches="tight"
    )

    plt.close(fig)


# Figure 1 — Occupancy map
fig, ax = plt.subplots(figsize=(9, 6.5))

ax.imshow(
    img,
    cmap="gray",
    origin="upper",
    extent=extent,
    interpolation="nearest"
)

ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")

fig.tight_layout()

save(
    fig,
    f"RTAB_Run{exp:02d}_Occupancy_Map_PUBLICATION"
)


# Figure 2 — Map + RTAB trajectory
fig, ax = plt.subplots(figsize=(9, 6.5))

ax.imshow(
    img,
    cmap="gray",
    origin="upper",
    extent=extent,
    interpolation="nearest"
)

ax.plot(
    sa[:, 1],
    sa[:, 2],
    linewidth=1.9,
    label="RTAB-Map estimated trajectory"
)

ax.scatter(
    sa[0, 1],
    sa[0, 2],
    s=35,
    label="Start"
)

ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
ax.legend(fontsize=9)

fig.tight_layout()

save(
    fig,
    f"RTAB_Run{exp:02d}_Map_and_Trajectory_PUBLICATION"
)


# Figure 3 — GT vs RTAB
fig, ax = plt.subplots(figsize=(9, 6.5))

ax.imshow(
    img,
    cmap="gray",
    origin="upper",
    extent=extent,
    interpolation="nearest"
)

ax.plot(
    ga[:, 1],
    ga[:, 2],
    linewidth=2.0,
    label="Ground truth"
)

ax.plot(
    sa[:, 1],
    sa[:, 2],
    linewidth=1.8,
    linestyle="--",
    label="RTAB-Map estimate"
)

ax.scatter(
    sa[0, 1],
    sa[0, 2],
    s=35,
    label="Common start"
)

ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
ax.legend(fontsize=9)

fig.tight_layout()

save(
    fig,
    f"RTAB_Run{exp:02d}_GT_vs_Estimated_PUBLICATION"
)

print("==============================================")
print(f"RTAB Experiment {exp:02d}")
print(f"Associated poses      : {len(gidx)}")
print(
    f"Association ratio     : "
    f"{100*len(gidx)/len(slam):.3f} %"
)
print(f"Mean |dt|             : {dt.mean()*1000:.3f} ms")
print(f"Max |dt|              : {dt.max()*1000:.3f} ms")
print(f"Initial yaw correction: {math.degrees(dyaw):.6f} deg")
print("Figures created in:")
print(figdir)
print("==============================================")
