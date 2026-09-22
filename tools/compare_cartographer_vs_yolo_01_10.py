#!/usr/bin/env python3

from pathlib import Path
import csv
import math

ROOT = Path.home() / "turtlebot3_ws"
EXP = ROOT / "metrics" / "experiments"

CART_FILE = (
    EXP
    / "cartographer"
    / "aggregate_01_10"
    / "aggregate_mean_sd_01_10.csv"
)

YOLO_FILE = (
    EXP
    / "cartographer_yolo"
    / "aggregate_01_10"
    / "aggregate_mean_sd_01_10.csv"
)

OUT_DIR = (
    EXP
    / "cartographer_yolo"
    / "aggregate_01_10"
)

TXT_OUT = (
    OUT_DIR
    / "cartographer_vs_cartographer_yolo_01_10.txt"
)

CSV_OUT = (
    OUT_DIR
    / "cartographer_vs_cartographer_yolo_01_10.csv"
)


def read_aggregate(path):
    if not path.exists():
        raise SystemExit(
            f"Missing aggregate file: {path}"
        )

    data = {}

    with path.open(
        newline="",
        encoding="utf-8"
    ) as f:

        for row in csv.DictReader(f):
            metric = row["metric"].strip()

            data[metric] = row

    return data


def get_float(data, metric, key):
    row = data.get(metric)

    if not row:
        return None

    try:
        value = float(row.get(key, ""))

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return None


def fmt(v, digits=6):
    if v is None:
        return "N/A"

    return f"{v:.{digits}f}"


def signed(v, digits=6):
    if v is None:
        return "N/A"

    return f"{v:+.{digits}f}"


def pct_change(base, new):
    if (
        base is None
        or new is None
        or base == 0
    ):
        return None

    return (
        (new - base)
        / base
        * 100.0
    )


cart = read_aggregate(CART_FILE)
yolo = read_aggregate(YOLO_FILE)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Metrics directly comparable between the two configurations
# ------------------------------------------------------------

sections = [
    (
        "1. LOCALIZATION ACCURACY",
        [
            (
                "APE Translation RMSE",
                "ape_translation_rmse_m",
                "m",
            ),
            (
                "APE Yaw RMSE",
                "ape_yaw_rmse_deg",
                "deg",
            ),
            (
                "RPE Translation @1m RMSE",
                "rpe_translation_1m_rmse_m",
                "m",
            ),
            (
                "RPE Yaw @1m RMSE",
                "rpe_yaw_1m_rmse_deg",
                "deg",
            ),
            (
                "Trajectory Match",
                "matched_percent",
                "%",
            ),
        ],
    ),

    (
        "2. SENSOR / SLAM PERFORMANCE",
        [
            (
                "LiDAR Rate",
                "lidar_rate_hz",
                "Hz",
            ),
            (
                "Camera Rate",
                "camera_rate_hz",
                "Hz",
            ),
            (
                "SLAM TF Rate",
                "slam_tf_rate_hz",
                "Hz",
            ),
            (
                "SLAM TF Latency Mean",
                "slam_tf_latency_mean_ms",
                "ms",
            ),
            (
                "SLAM TF Latency P95",
                "slam_tf_latency_p95_ms",
                "ms",
            ),
            (
                "Gazebo RTF",
                "gazebo_rtf_overall",
                "",
            ),
        ],
    ),

    (
        "3. SYSTEM RESOURCES",
        [
            (
                "System CPU Mean",
                "system_cpu_mean_percent",
                "%",
            ),
            (
                "System RAM Mean",
                "system_ram_mean_percent",
                "%",
            ),
        ],
    ),
]


comparison_rows = []


def add_comparison_row(
    section,
    label,
    metric,
    unit,
):
    b_mean = get_float(
        cart,
        metric,
        "mean"
    )

    b_sd = get_float(
        cart,
        metric,
        "sd"
    )

    y_mean = get_float(
        yolo,
        metric,
        "mean"
    )

    y_sd = get_float(
        yolo,
        metric,
        "sd"
    )

    diff = (
        y_mean - b_mean
        if (
            b_mean is not None
            and y_mean is not None
        )
        else None
    )

    change = pct_change(
        b_mean,
        y_mean
    )

    comparison_rows.append({
        "section": section,
        "metric": label,
        "metric_key": metric,
        "unit": unit,
        "cartographer_mean": b_mean,
        "cartographer_sd": b_sd,
        "cartographer_yolo_mean": y_mean,
        "cartographer_yolo_sd": y_sd,
        "absolute_difference": diff,
        "percent_change": change,
    })


for section, metrics in sections:
    for label, metric, unit in metrics:
        add_comparison_row(
            section,
            label,
            metric,
            unit,
        )


# ------------------------------------------------------------
# Resource-specific comparison
# ------------------------------------------------------------

resource_section = (
    "4. PROCESS RESOURCE BREAKDOWN"
)

resource_metrics = [
    (
        "Baseline Cartographer CPU",
        "process_cpu_mean_percent",
        "cartographer_cpu_mean_percent",
        "%",
    ),
    (
        "Baseline Cartographer RAM",
        "process_ram_mean_mb",
        "cartographer_ram_mean_mb",
        "MB",
    ),
]

for (
    label,
    baseline_metric,
    yolo_metric,
    unit,
) in resource_metrics:

    b_mean = get_float(
        cart,
        baseline_metric,
        "mean"
    )

    b_sd = get_float(
        cart,
        baseline_metric,
        "sd"
    )

    y_mean = get_float(
        yolo,
        yolo_metric,
        "mean"
    )

    y_sd = get_float(
        yolo,
        yolo_metric,
        "sd"
    )

    diff = (
        y_mean - b_mean
        if (
            b_mean is not None
            and y_mean is not None
        )
        else None
    )

    change = pct_change(
        b_mean,
        y_mean
    )

    comparison_rows.append({
        "section": resource_section,
        "metric": label,
        "metric_key":
            f"{baseline_metric} vs {yolo_metric}",
        "unit": unit,
        "cartographer_mean": b_mean,
        "cartographer_sd": b_sd,
        "cartographer_yolo_mean": y_mean,
        "cartographer_yolo_sd": y_sd,
        "absolute_difference": diff,
        "percent_change": change,
    })


# ------------------------------------------------------------
# Write machine-readable CSV
# ------------------------------------------------------------

with CSV_OUT.open(
    "w",
    newline="",
    encoding="utf-8"
) as f:

    fieldnames = [
        "section",
        "metric",
        "metric_key",
        "unit",
        "cartographer_mean",
        "cartographer_sd",
        "cartographer_yolo_mean",
        "cartographer_yolo_sd",
        "absolute_difference",
        "percent_change",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()

    for row in comparison_rows:
        writer.writerow(row)


# ------------------------------------------------------------
# Build human-readable report
# ------------------------------------------------------------

lines = []

sep = "=" * 142
sub = "-" * 142

lines += [
    sep,
    "CARTOGRAPHER vs CARTOGRAPHER + YOLO — EXPERIMENTS 01–10",
    sep,
    "",
    "Both configurations contain 10 experimental runs.",
    "Values are reported as mean ± between-run sample SD.",
    "",
]


for section, _ in sections:

    lines += [
        sep,
        section,
        sep,
        (
            f"{'Metric':<32}"
            f"{'Cartographer Mean ± SD':>30}"
            f"{'Cartographer+YOLO Mean ± SD':>33}"
            f"{'Difference':>18}"
            f"{'% Change':>14}"
            f"{'Unit':>10}"
        ),
        sub,
    ]

    for row in comparison_rows:

        if row["section"] != section:
            continue

        b = (
            f"{fmt(row['cartographer_mean'])} "
            f"± {fmt(row['cartographer_sd'])}"
        )

        y = (
            f"{fmt(row['cartographer_yolo_mean'])} "
            f"± {fmt(row['cartographer_yolo_sd'])}"
        )

        lines.append(
            f"{row['metric']:<32}"
            f"{b:>30}"
            f"{y:>33}"
            f"{signed(row['absolute_difference']):>18}"
            f"{signed(row['percent_change'], 3):>14}"
            f"{row['unit']:>10}"
        )

    lines.append("")


# Process resource section
lines += [
    sep,
    resource_section,
    sep,
    (
        f"{'Metric':<32}"
        f"{'Baseline Mean ± SD':>30}"
        f"{'YOLO Run Cart Component':>33}"
        f"{'Difference':>18}"
        f"{'% Change':>14}"
        f"{'Unit':>10}"
    ),
    sub,
]

for row in comparison_rows:

    if row["section"] != resource_section:
        continue

    b = (
        f"{fmt(row['cartographer_mean'])} "
        f"± {fmt(row['cartographer_sd'])}"
    )

    y = (
        f"{fmt(row['cartographer_yolo_mean'])} "
        f"± {fmt(row['cartographer_yolo_sd'])}"
    )

    lines.append(
        f"{row['metric']:<32}"
        f"{b:>30}"
        f"{y:>33}"
        f"{signed(row['absolute_difference']):>18}"
        f"{signed(row['percent_change'], 3):>14}"
        f"{row['unit']:>10}"
    )


# ------------------------------------------------------------
# Additional YOLO configuration resources
# ------------------------------------------------------------

lines += [
    "",
    sep,
    "5. CARTOGRAPHER + YOLO CONFIGURATION — ADDITIONAL RESOURCES",
    sep,
]

extra_yolo = [
    (
        "Combined CPU Mean",
        "process_cpu_mean_percent",
        "%",
    ),
    (
        "Combined RAM Mean",
        "process_ram_mean_mb",
        "MB",
    ),
    (
        "Cartographer CPU Mean",
        "cartographer_cpu_mean_percent",
        "%",
    ),
    (
        "Cartographer RAM Mean",
        "cartographer_ram_mean_mb",
        "MB",
    ),
    (
        "YOLO CPU Mean",
        "yolo_cpu_mean_percent",
        "%",
    ),
    (
        "YOLO RAM Mean",
        "yolo_ram_mean_mb",
        "MB",
    ),
]

for label, metric, unit in extra_yolo:

    mean = get_float(
        yolo,
        metric,
        "mean"
    )

    sd = get_float(
        yolo,
        metric,
        "sd"
    )

    lines.append(
        f"{label:<34}: "
        f"{fmt(mean)} ± {fmt(sd)} {unit}"
    )


# ------------------------------------------------------------
# YOLO performance
# ------------------------------------------------------------

lines += [
    "",
    sep,
    "6. YOLO PERFORMANCE — 10-RUN AGGREGATE",
    sep,
]

yolo_metrics = [
    (
        "YOLO Effective FPS",
        "yolo_effective_fps",
        "FPS",
    ),
    (
        "YOLO Inference Mean",
        "yolo_inference_mean_ms",
        "ms",
    ),
    (
        "YOLO Inference P95",
        "yolo_inference_p95_ms",
        "ms",
    ),
    (
        "YOLO Overlap FPS",
        "yolo_overlap_source_rate_fps",
        "FPS",
    ),
    (
        "CameraInfo→YOLO Match",
        "yolo_timestamp_matching_ratio_percent",
        "%",
    ),
    (
        "YOLO Predict Mean",
        "yolo_predict_mean_ms",
        "ms",
    ),
    (
        "YOLO Predict P95",
        "yolo_predict_p95_ms",
        "ms",
    ),
    (
        "YOLO Predict P99",
        "yolo_predict_p99_ms",
        "ms",
    ),
    (
        "YOLO Callback Mean",
        "yolo_callback_mean_ms",
        "ms",
    ),
]

for label, metric, unit in yolo_metrics:

    mean = get_float(
        yolo,
        metric,
        "mean"
    )

    sd = get_float(
        yolo,
        metric,
        "sd"
    )

    lines.append(
        f"{label:<34}: "
        f"{fmt(mean)} ± {fmt(sd)} {unit}"
    )


# ------------------------------------------------------------
# Methodology notes
# ------------------------------------------------------------

lines += [
    "",
    sep,
    "7. INTERPRETATION / METHODOLOGY NOTES",
    sep,
    "",
    (
        "• Percentage change is descriptive and is calculated as "
        "(Cartographer+YOLO mean - Cartographer mean) / "
        "Cartographer mean × 100."
    ),
    (
        "• Positive percentage values mean the numerical metric "
        "increased in the Cartographer+YOLO experiments."
    ),
    (
        "• Localization runs were manually teleoperated; the two "
        "configurations therefore did not follow identical trajectories."
    ),
    (
        "• Consequently, these between-configuration differences "
        "should not be interpreted as a paired or isolated causal "
        "effect of YOLO."
    ),
    (
        "• The YOLO experiments were run with YOLO on CPU "
        "(device=cpu); CUDA/GPU inference was not active."
    ),
    (
        "• Linux process CPU utilization can exceed 100% because "
        "utilization is accumulated across logical CPU cores."
    ),
    (
        "• CameraInfo-to-YOLO timestamp matching is a source-timestamp "
        "correspondence metric, not a DDS packet-loss measurement."
    ),
    (
        "• APE uses planar trajectories with origin alignment. "
        "RPE uses a 1 m delta."
    ),
    (
        "• TF latency is the LiDAR-receipt to global-map-TF-receipt "
        "wall-time latency proxy used consistently in the experiment."
    ),
    "",
    sep,
    "END OF COMPARISON REPORT",
    sep,
]


text = "\n".join(lines) + "\n"

TXT_OUT.write_text(
    text,
    encoding="utf-8"
)

print(text)

print(
    f"Saved TXT: {TXT_OUT}"
)

print(
    f"Saved CSV: {CSV_OUT}"
)
