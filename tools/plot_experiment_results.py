#!/usr/bin/env python3

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from evo.core import sync
from evo.tools import file_interface


MAX_TIME_DIFF = 0.02


def require(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")


def load_result(path):
    require(path)
    return file_interface.load_res_file(str(path))


def get_array(result, name):
    if name not in result.np_arrays:
        raise KeyError(
            f"Array '{name}' not found in EVO result. "
            f"Available: {list(result.np_arrays.keys())}"
        )

    return np.asarray(result.np_arrays[name])


def save_csv(path, x, y, xname, yname):
    np.savetxt(
        path,
        np.column_stack((x, y)),
        delimiter=",",
        header=f"{xname},{yname}",
        comments=""
    )


if len(sys.argv) != 4:
    print(
        "Usage: plot_experiment_results.py "
        "gt_planar.tum slam_planar.tum output_directory"
    )
    sys.exit(1)


gt_file = Path(sys.argv[1]).resolve()
slam_file = Path(sys.argv[2]).resolve()
outdir = Path(sys.argv[3]).resolve()

require(gt_file)
require(slam_file)

outdir.mkdir(parents=True, exist_ok=True)

exp_dir = gt_file.parent

ape_translation_zip = exp_dir / "ape_translation.zip"
ape_yaw_zip = exp_dir / "ape_yaw.zip"
rpe_translation_zip = exp_dir / "rpe_translation_1m.zip"
rpe_yaw_zip = exp_dir / "rpe_yaw_1m.zip"

for p in [
    ape_translation_zip,
    ape_yaw_zip,
    rpe_translation_zip,
    rpe_yaw_zip,
]:
    require(p)


# ============================================================
# Load official EVO result files
# ============================================================

ape_t_result = load_result(ape_translation_zip)
ape_y_result = load_result(ape_yaw_zip)
rpe_t_result = load_result(rpe_translation_zip)
rpe_y_result = load_result(rpe_yaw_zip)


# ============================================================
# Exact EVO error arrays
# ============================================================

ape_translation = get_array(
    ape_t_result,
    "error_array"
)

ape_yaw = get_array(
    ape_y_result,
    "error_array"
)

rpe_translation = get_array(
    rpe_t_result,
    "error_array"
)

rpe_yaw = get_array(
    rpe_y_result,
    "error_array"
)


# Exact EVO x-axis arrays
ape_time = get_array(
    ape_t_result,
    "seconds_from_start"
)

ape_yaw_time = get_array(
    ape_y_result,
    "seconds_from_start"
)

rpe_distance = get_array(
    rpe_t_result,
    "distances_from_start"
)

rpe_yaw_distance = get_array(
    rpe_y_result,
    "distances_from_start"
)


# ============================================================
# Sanity checks
# ============================================================

if len(ape_translation) != len(ape_time):
    raise RuntimeError(
        "APE translation array/time length mismatch"
    )

if len(ape_yaw) != len(ape_yaw_time):
    raise RuntimeError(
        "APE yaw array/time length mismatch"
    )

if len(rpe_translation) != len(rpe_distance):
    raise RuntimeError(
        "RPE translation array/distance length mismatch"
    )

if len(rpe_yaw) != len(rpe_yaw_distance):
    raise RuntimeError(
        "RPE yaw array/distance length mismatch"
    )


# ============================================================
# Trajectory visualization using EVO's own synchronization
# and origin alignment
# ============================================================

traj_ref = file_interface.read_tum_trajectory_file(
    str(gt_file)
)

traj_est = file_interface.read_tum_trajectory_file(
    str(slam_file)
)

traj_ref, traj_est = sync.associate_trajectories(
    traj_ref,
    traj_est,
    MAX_TIME_DIFF,
    0.0
)

# Same origin-alignment operation used by EVO --align_origin.
traj_est.align_origin(traj_ref)

gt_xyz = traj_ref.positions_xyz
slam_xyz = traj_est.positions_xyz

gt_x = gt_xyz[:, 0]
gt_y = gt_xyz[:, 1]

slam_x = slam_xyz[:, 0]
slam_y = slam_xyz[:, 1]


# ============================================================
# Save exact EVO arrays as CSV
# ============================================================

save_csv(
    outdir / "ape_translation_timeseries.csv",
    ape_time,
    ape_translation,
    "time_s",
    "ape_translation_m"
)

save_csv(
    outdir / "ape_yaw_timeseries.csv",
    ape_yaw_time,
    ape_yaw,
    "time_s",
    "ape_yaw_deg"
)

save_csv(
    outdir / "rpe_translation_1m_timeseries.csv",
    rpe_distance,
    rpe_translation,
    "travelled_distance_m",
    "rpe_translation_m"
)

save_csv(
    outdir / "rpe_yaw_1m_timeseries.csv",
    rpe_yaw_distance,
    rpe_yaw,
    "travelled_distance_m",
    "rpe_yaw_deg"
)


# ============================================================
# Official statistics - read directly from EVO result objects
# ============================================================

ape_t_rmse = float(
    ape_t_result.stats["rmse"]
)

ape_y_rmse = float(
    ape_y_result.stats["rmse"]
)

rpe_t_rmse = float(
    rpe_t_result.stats["rmse"]
)

rpe_y_rmse = float(
    rpe_y_result.stats["rmse"]
)


# ============================================================
# Configuration label
# ============================================================

configuration = exp_dir.parent.name

labels = {
    "cartographer": "Cartographer",
    "cartographer_yolo": "Cartographer + YOLO",
    "rtab": "RTAB-Map",
    "rtab_yolo": "RTAB-Map + YOLO",
}

slam_label = labels.get(
    configuration,
    configuration
)


# ============================================================
# 1. Trajectory
# ============================================================

plt.figure(figsize=(11, 8))

plt.plot(
    gt_x,
    gt_y,
    linewidth=3.0,
    label="Ground Truth"
)

plt.plot(
    slam_x,
    slam_y,
    linewidth=1.5,
    label=slam_label
)

plt.scatter(
    gt_x[0],
    gt_y[0],
    s=55,
    marker="o",
    label="Start"
)

plt.xlabel("X [m]")
plt.ylabel("Y [m]")

plt.title(
    f"Trajectory Comparison: "
    f"Ground Truth vs {slam_label}"
)

plt.grid(True, alpha=0.4)
plt.legend()
plt.axis("equal")
plt.tight_layout()

plt.savefig(
    outdir / "01_trajectory_gt_vs_slam.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# 2. APE translation
# ============================================================

plt.figure(figsize=(11, 6))

plt.plot(
    ape_time,
    ape_translation,
    linewidth=1.2
)

plt.xlabel("Time [s]")
plt.ylabel("APE Translation [m]")

plt.title(
    f"APE Translation vs Time "
    f"(EVO RMSE = {ape_t_rmse:.6f} m)"
)

plt.grid(True, alpha=0.4)
plt.tight_layout()

plt.savefig(
    outdir / "02_ape_translation_vs_time.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# 3. APE yaw
# ============================================================

plt.figure(figsize=(11, 6))

plt.plot(
    ape_yaw_time,
    ape_yaw,
    linewidth=1.2
)

plt.xlabel("Time [s]")
plt.ylabel("APE Yaw [deg]")

plt.title(
    f"APE Yaw vs Time "
    f"(EVO RMSE = {ape_y_rmse:.6f} deg)"
)

plt.grid(True, alpha=0.4)
plt.tight_layout()

plt.savefig(
    outdir / "03_ape_yaw_vs_time.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# 4. RPE translation @ 1 m
# ============================================================

plt.figure(figsize=(11, 6))

plt.plot(
    rpe_distance,
    rpe_translation,
    linewidth=1.2
)

plt.xlabel("Travelled Distance [m]")
plt.ylabel("RPE Translation [m]")

plt.title(
    f"RPE Translation @ 1 m "
    f"(EVO RMSE = {rpe_t_rmse:.6f} m)"
)

plt.grid(True, alpha=0.4)
plt.tight_layout()

plt.savefig(
    outdir / "04_rpe_translation_vs_distance.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# 5. Combined 2x2 figure
# ============================================================

fig, axes = plt.subplots(
    2,
    2,
    figsize=(15, 11)
)

ax = axes[0, 0]

ax.plot(
    gt_x,
    gt_y,
    linewidth=2.5,
    label="Ground Truth"
)

ax.plot(
    slam_x,
    slam_y,
    linewidth=1.3,
    label=slam_label
)

ax.set_xlabel("X [m]")
ax.set_ylabel("Y [m]")
ax.set_title("Trajectory")
ax.grid(True, alpha=0.4)
ax.legend()
ax.axis("equal")


ax = axes[0, 1]

ax.plot(
    ape_time,
    ape_translation,
    linewidth=1.0
)

ax.set_xlabel("Time [s]")
ax.set_ylabel("APE Translation [m]")

ax.set_title(
    f"APE Translation "
    f"(RMSE {ape_t_rmse:.6f} m)"
)

ax.grid(True, alpha=0.4)


ax = axes[1, 0]

ax.plot(
    ape_yaw_time,
    ape_yaw,
    linewidth=1.0
)

ax.set_xlabel("Time [s]")
ax.set_ylabel("APE Yaw [deg]")

ax.set_title(
    f"APE Yaw "
    f"(RMSE {ape_y_rmse:.6f}°)"
)

ax.grid(True, alpha=0.4)


ax = axes[1, 1]

ax.plot(
    rpe_distance,
    rpe_translation,
    linewidth=1.0
)

ax.set_xlabel("Travelled Distance [m]")
ax.set_ylabel("RPE Translation [m]")

ax.set_title(
    f"RPE Translation @ 1 m "
    f"(RMSE {rpe_t_rmse:.6f} m)"
)

ax.grid(True, alpha=0.4)


fig.suptitle(
    f"{slam_label} — Experimental Results",
    fontsize=16
)

fig.tight_layout()

# Keep this legacy filename because finalize_experiment.py
# automatically renames it to the correct configuration/run name.
combined_legacy = (
    outdir /
    "05_experiment01_combined_results.png"
)

fig.savefig(
    combined_legacy,
    dpi=300,
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# Summary
# ============================================================

print()
print("========== EVO-BASED PLOT SUMMARY ==========")

print(
    f"Matched trajectory poses: "
    f"{traj_ref.num_poses}"
)

print()
print("APE Translation")
print(
    f"RMSE: {ape_t_rmse:.6f} m"
)

print()
print("APE Yaw")
print(
    f"RMSE: {ape_y_rmse:.6f} deg"
)

print()
print("RPE Translation @ 1 m")
print(
    f"Pairs: {len(rpe_translation)}"
)
print(
    f"RMSE: {rpe_t_rmse:.6f} m"
)

print()
print("RPE Yaw @ 1 m")
print(
    f"Pairs: {len(rpe_yaw)}"
)
print(
    f"RMSE: {rpe_y_rmse:.6f} deg"
)

print()
print(
    f"Saved figures in: {outdir}"
)

print("=============================================")
