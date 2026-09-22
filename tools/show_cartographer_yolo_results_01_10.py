#!/usr/bin/env python3

from pathlib import Path
import csv
import re

ROOT = Path.home() / "turtlebot3_ws"
BASE = (
    ROOT
    / "metrics"
    / "experiments"
    / "cartographer_yolo"
)

AGG_DIR = BASE / "aggregate_01_10"
AGG_FILE = AGG_DIR / "aggregate_mean_sd_01_10.csv"


def read_row(path):
    if not path.exists():
        return {}

    with path.open(
        newline="",
        encoding="utf-8"
    ) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {}

    return rows[0]


def num(row, key):
    try:
        value = row.get(key, "")
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        return float(value)

    except Exception:
        return None


def fmt(value, digits=3):
    if value is None:
        return "N/A"

    return f"{value:.{digits}f}"


def validation_status(exp_dir):
    p = exp_dir / "experiment_validation.txt"

    if not p.exists():
        return "MISSING"

    text = p.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    m = re.search(
        r"FINAL STATUS:\s*(\S+)",
        text,
        flags=re.I
    )

    if not m:
        return "UNKNOWN"

    return m.group(1).upper()


def print_line():
    print("=" * 126)


def print_subline():
    print("-" * 126)


runs = []

for i in range(1, 11):
    exp = BASE / f"experiment_{i:02d}"

    row = read_row(
        exp / "summary_row.csv"
    )

    row["_run"] = i
    row["_status"] = validation_status(exp)

    runs.append(row)


print()
print_line()
print("CARTOGRAPHER + YOLO — EXPERIMENTS 01–10")
print_line()

valid_runs = [
    r for r in runs
    if r["_status"] == "VALID"
]

print(
    f"Runs found : "
    f"{sum(bool(r.get('configuration')) for r in runs)}/10"
)

print(
    f"VALID runs : "
    f"{len(valid_runs)}/10"
)

print()


# ============================================================
# 1. Localization
# ============================================================

print_line()
print("1. LOCALIZATION ACCURACY")
print_line()

print(
    f"{'Run':<6}"
    f"{'Status':<9}"
    f"{'Match %':>10}"
    f"{'APE Trans RMSE (m)':>21}"
    f"{'APE Yaw RMSE (deg)':>21}"
    f"{'RPE Trans @1m (m)':>20}"
    f"{'RPE Yaw @1m (deg)':>21}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{r['_status']:<9}"
        f"{fmt(num(r, 'matched_percent'), 3):>10}"
        f"{fmt(num(r, 'ape_translation_rmse_m'), 6):>21}"
        f"{fmt(num(r, 'ape_yaw_rmse_deg'), 6):>21}"
        f"{fmt(num(r, 'rpe_translation_1m_rmse_m'), 6):>20}"
        f"{fmt(num(r, 'rpe_yaw_1m_rmse_deg'), 6):>21}"
    )

print()


# ============================================================
# 2. Combined/system resources
# ============================================================

print_line()
print("2. COMBINED / SYSTEM RESOURCES")
print_line()

print(
    f"{'Run':<6}"
    f"{'Combined CPU %':>17}"
    f"{'Combined RAM MB':>18}"
    f"{'System CPU %':>16}"
    f"{'System RAM %':>16}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{fmt(num(r, 'process_cpu_mean_percent'), 3):>17}"
        f"{fmt(num(r, 'process_ram_mean_mb'), 3):>18}"
        f"{fmt(num(r, 'system_cpu_mean_percent'), 3):>16}"
        f"{fmt(num(r, 'system_ram_mean_percent'), 3):>16}"
    )

print()


# ============================================================
# 3. Per-process resources
# ============================================================

print_line()
print("3. PER-PROCESS RESOURCE BREAKDOWN")
print_line()

print(
    f"{'Run':<6}"
    f"{'Cart CPU %':>14}"
    f"{'Cart RAM MB':>15}"
    f"{'YOLO CPU %':>14}"
    f"{'YOLO RAM MB':>15}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{fmt(num(r, 'cartographer_cpu_mean_percent'), 3):>14}"
        f"{fmt(num(r, 'cartographer_ram_mean_mb'), 3):>15}"
        f"{fmt(num(r, 'yolo_cpu_mean_percent'), 3):>14}"
        f"{fmt(num(r, 'yolo_ram_mean_mb'), 3):>15}"
    )

print()


# ============================================================
# 4. Sensor / SLAM performance
# ============================================================

print_line()
print("4. SENSOR / SLAM PERFORMANCE")
print_line()

print(
    f"{'Run':<6}"
    f"{'LiDAR Hz':>11}"
    f"{'Camera Hz':>12}"
    f"{'SLAM TF Hz':>13}"
    f"{'Latency Mean ms':>18}"
    f"{'Latency P95 ms':>17}"
    f"{'Gazebo RTF':>13}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{fmt(num(r, 'lidar_rate_hz'), 3):>11}"
        f"{fmt(num(r, 'camera_rate_hz'), 3):>12}"
        f"{fmt(num(r, 'slam_tf_rate_hz'), 3):>13}"
        f"{fmt(num(r, 'slam_tf_latency_mean_ms'), 3):>18}"
        f"{fmt(num(r, 'slam_tf_latency_p95_ms'), 3):>17}"
        f"{fmt(num(r, 'gazebo_rtf_overall'), 6):>13}"
    )

print()


# ============================================================
# 5. YOLO full-run performance
# ============================================================

print_line()
print("5. YOLO FULL-RUN PERFORMANCE")
print_line()

print(
    f"{'Run':<6}"
    f"{'Frames':>10}"
    f"{'Effective FPS':>16}"
    f"{'Inference Mean ms':>20}"
    f"{'Inference P95 ms':>19}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{fmt(num(r, 'yolo_frames_processed'), 0):>10}"
        f"{fmt(num(r, 'yolo_effective_fps'), 3):>16}"
        f"{fmt(num(r, 'yolo_inference_mean_ms'), 3):>20}"
        f"{fmt(num(r, 'yolo_inference_p95_ms'), 3):>19}"
    )

print()


# ============================================================
# 6. YOLO / CameraInfo overlap
# ============================================================

print_line()
print("6. YOLO / CAMERAINFO OVERLAP")
print_line()

print(
    f"{'Run':<6}"
    f"{'Overlap FPS':>13}"
    f"{'Match %':>12}"
    f"{'Predict Mean ms':>18}"
    f"{'Predict P95 ms':>17}"
    f"{'Predict P99 ms':>17}"
    f"{'Callback Mean ms':>19}"
)

print_subline()

for r in runs:
    print(
        f"{r['_run']:02d}{'':<4}"
        f"{fmt(num(r, 'yolo_overlap_source_rate_fps'), 3):>13}"
        f"{fmt(num(r, 'yolo_timestamp_matching_ratio_percent'), 3):>12}"
        f"{fmt(num(r, 'yolo_predict_mean_ms'), 3):>18}"
        f"{fmt(num(r, 'yolo_predict_p95_ms'), 3):>17}"
        f"{fmt(num(r, 'yolo_predict_p99_ms'), 3):>17}"
        f"{fmt(num(r, 'yolo_callback_mean_ms'), 3):>19}"
    )

print()


# ============================================================
# 7. Official aggregate Mean ± SD
# ============================================================

print_line()
print("7. FINAL MEAN ± BETWEEN-RUN SD (n=10)")
print_line()

aggregate = {}

if AGG_FILE.exists():
    with AGG_FILE.open(
        newline="",
        encoding="utf-8"
    ) as f:

        for row in csv.DictReader(f):
            aggregate[row["metric"]] = row


important_metrics = [
    (
        "APE Translation RMSE",
        "ape_translation_rmse_m",
        "m"
    ),
    (
        "APE Yaw RMSE",
        "ape_yaw_rmse_deg",
        "deg"
    ),
    (
        "RPE Translation @1m RMSE",
        "rpe_translation_1m_rmse_m",
        "m"
    ),
    (
        "RPE Yaw @1m RMSE",
        "rpe_yaw_1m_rmse_deg",
        "deg"
    ),
    (
        "Combined CPU Mean",
        "process_cpu_mean_percent",
        "%"
    ),
    (
        "Combined RAM Mean",
        "process_ram_mean_mb",
        "MB"
    ),
    (
        "Cartographer CPU Mean",
        "cartographer_cpu_mean_percent",
        "%"
    ),
    (
        "Cartographer RAM Mean",
        "cartographer_ram_mean_mb",
        "MB"
    ),
    (
        "YOLO CPU Mean",
        "yolo_cpu_mean_percent",
        "%"
    ),
    (
        "YOLO RAM Mean",
        "yolo_ram_mean_mb",
        "MB"
    ),
    (
        "System CPU Mean",
        "system_cpu_mean_percent",
        "%"
    ),
    (
        "System RAM Mean",
        "system_ram_mean_percent",
        "%"
    ),
    (
        "LiDAR Rate",
        "lidar_rate_hz",
        "Hz"
    ),
    (
        "Camera Rate",
        "camera_rate_hz",
        "Hz"
    ),
    (
        "SLAM TF Rate",
        "slam_tf_rate_hz",
        "Hz"
    ),
    (
        "SLAM TF Latency Mean",
        "slam_tf_latency_mean_ms",
        "ms"
    ),
    (
        "SLAM TF Latency P95",
        "slam_tf_latency_p95_ms",
        "ms"
    ),
    (
        "Gazebo RTF",
        "gazebo_rtf_overall",
        ""
    ),
    (
        "YOLO Effective FPS",
        "yolo_effective_fps",
        "FPS"
    ),
    (
        "YOLO Inference Mean",
        "yolo_inference_mean_ms",
        "ms"
    ),
    (
        "YOLO Inference P95",
        "yolo_inference_p95_ms",
        "ms"
    ),
    (
        "YOLO Overlap FPS",
        "yolo_overlap_source_rate_fps",
        "FPS"
    ),
    (
        "YOLO Timestamp Matching",
        "yolo_timestamp_matching_ratio_percent",
        "%"
    ),
    (
        "YOLO Predict Mean",
        "yolo_predict_mean_ms",
        "ms"
    ),
    (
        "YOLO Predict P95",
        "yolo_predict_p95_ms",
        "ms"
    ),
    (
        "YOLO Predict P99",
        "yolo_predict_p99_ms",
        "ms"
    ),
    (
        "YOLO Callback Mean",
        "yolo_callback_mean_ms",
        "ms"
    ),
]


print(
    f"{'Metric':<36}"
    f"{'n':>5}"
    f"{'Mean ± SD':>32}"
    f"{'Unit':>10}"
)

print_subline()

for label, key, unit in important_metrics:

    row = aggregate.get(key)

    if not row:
        print(
            f"{label:<36}"
            f"{'N/A':>5}"
            f"{'N/A':>32}"
            f"{unit:>10}"
        )
        continue

    n = row.get("n", "")
    mean_sd = row.get(
        "mean_plus_minus_sd",
        ""
    )

    print(
        f"{label:<36}"
        f"{n:>5}"
        f"{mean_sd:>32}"
        f"{unit:>10}"
    )


print()
print_line()
print("QUALITY / INTERPRETATION NOTES")
print_line()

print(
    "• All 10 experiments should report FINAL STATUS: VALID."
)

print(
    "• CPU percentages can exceed 100% because Linux psutil "
    "reports utilization across multiple logical CPU cores."
)

print(
    "• YOLO timestamp matching is the observed "
    "CameraInfo-to-YOLO source-timestamp correspondence ratio; "
    "it is NOT a DDS packet-loss measurement."
)

print(
    "• TF latency is the measured LiDAR-receipt to "
    "global-map-TF-receipt wall-time latency proxy."
)

print(
    "• Localization metrics use planar trajectories, "
    "origin alignment for APE, and 1 m delta for RPE."
)

print(
    "• Mean ± SD is calculated across the 10 independent runs "
    "using between-run sample SD."
)

print_line()
print("END OF CARTOGRAPHER + YOLO 01–10 REPORT")
print_line()
print()
