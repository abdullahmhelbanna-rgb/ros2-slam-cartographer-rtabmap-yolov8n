#!/usr/bin/env python3

from pathlib import Path
import argparse
import csv
import math
import statistics

ROOT = Path.home() / "turtlebot3_ws"
BASE = ROOT / "metrics" / "experiments"

CONFIGS = [
    "cartographer",
    "cartographer_yolo",
    "rtab",
    "rtab_yolo",
]

FIRST_EXP = 1
LAST_EXP = 10


def to_float(value):
    if value is None:
        return None

    s = str(value).strip()

    if s == "" or s.lower() in {
        "n/a", "na", "nan", "none", "not available"
    }:
        return None

    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def read_row(path):
    if not path.exists():
        return None

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return rows[0] if rows else None


def validation_status(exp_dir):
    path = exp_dir / "experiment_validation.txt"

    if not path.exists():
        # Experiment 01 may predate automatic validation
        return "N/A"

    text = path.read_text(encoding="utf-8", errors="ignore")

    for line in text.splitlines():
        if "FINAL STATUS:" in line:
            return line.split("FINAL STATUS:", 1)[1].strip()

    return "N/A"


def fmt(value, decimals=6):
    x = to_float(value)

    if x is None:
        return "N/A"

    return f"{x:.{decimals}f}"


def print_table(headers, rows):
    widths = []

    for i, h in enumerate(headers):
        values = [str(row[i]) for row in rows]
        widths.append(
            max(
                len(str(h)),
                max((len(v) for v in values), default=0)
            )
        )

    def line():
        return "+-" + "-+-".join("-" * w for w in widths) + "-+"

    print(line())

    print(
        "| " +
        " | ".join(
            str(h).ljust(widths[i])
            for i, h in enumerate(headers)
        ) +
        " |"
    )

    print(line())

    for row in rows:
        print(
            "| " +
            " | ".join(
                str(row[i]).ljust(widths[i])
                for i in range(len(headers))
            ) +
            " |"
        )

    print(line())


def mean_sd(values):
    vals = [x for x in values if x is not None]

    if not vals:
        return 0, None, None

    mean = statistics.mean(vals)

    if len(vals) >= 2:
        sd = statistics.stdev(vals)
    else:
        sd = None

    return len(vals), mean, sd


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "configuration",
        choices=CONFIGS,
        help="Configuration name"
    )

    args = parser.parse_args()
    config = args.configuration

    config_dir = BASE / config

    runs = []

    for exp in range(FIRST_EXP, LAST_EXP + 1):

        exp_dir = config_dir / f"experiment_{exp:02d}"
        row = read_row(exp_dir / "summary_row.csv")

        if row is None:
            print(
                f"WARNING: Experiment {exp:02d} "
                f"summary_row.csv not found"
            )
            continue

        row = dict(row)
        row["_experiment"] = exp
        row["_status"] = validation_status(exp_dir)

        runs.append(row)

    print()
    print("=" * 110)
    print(
        f"{config.upper()} — EXPERIMENTS 01–10 RESULTS"
    )
    print("=" * 110)

    # ==========================================================
    # TABLE 1 — LOCALIZATION RESULTS FOR EACH EXPERIMENT
    # ==========================================================

    print()
    print("TABLE 1 — LOCALIZATION RESULTS FOR EACH EXPERIMENT")
    print()

    localization_rows = []

    for r in runs:
        localization_rows.append([
            f"{r['_experiment']:02d}",
            r["_status"],
            fmt(r.get("matched_percent"), 3),
            fmt(r.get("ape_translation_rmse_m"), 6),
            fmt(r.get("ape_yaw_rmse_deg"), 6),
            fmt(r.get("rpe_translation_1m_rmse_m"), 6),
            fmt(r.get("rpe_yaw_1m_rmse_deg"), 6),
        ])

    print_table(
        [
            "Exp",
            "Status",
            "Match %",
            "APE Trans RMSE m",
            "APE Yaw RMSE deg",
            "RPE Trans RMSE m",
            "RPE Yaw RMSE deg",
        ],
        localization_rows
    )

    # ==========================================================
    # TABLE 2 — PERFORMANCE RESULTS FOR EACH EXPERIMENT
    # ==========================================================

    print()
    print("TABLE 2 — PERFORMANCE RESULTS FOR EACH EXPERIMENT")
    print()

    performance_rows = []

    for r in runs:
        performance_rows.append([
            f"{r['_experiment']:02d}",
            fmt(r.get("process_cpu_mean_percent"), 3),
            fmt(r.get("process_ram_mean_mb"), 3),
            fmt(r.get("lidar_rate_hz"), 3),
            fmt(r.get("camera_rate_hz"), 3),
            fmt(r.get("slam_tf_rate_hz"), 3),
            fmt(r.get("slam_tf_latency_mean_ms"), 3),
            fmt(r.get("gazebo_rtf_overall"), 6),
        ])

    print_table(
        [
            "Exp",
            "CPU Mean %",
            "RAM Mean MB",
            "LiDAR Hz",
            "Camera Hz",
            "SLAM TF Hz",
            "TF Latency ms",
            "Gazebo RTF",
        ],
        performance_rows
    )

    # ==========================================================
    # TABLE 3 — FINAL MEAN ± SD
    # ==========================================================

    metrics = [
        (
            "APE Translation RMSE",
            "ape_translation_rmse_m",
            "m",
            6,
        ),
        (
            "APE Yaw RMSE",
            "ape_yaw_rmse_deg",
            "deg",
            6,
        ),
        (
            "RPE Translation @1m RMSE",
            "rpe_translation_1m_rmse_m",
            "m",
            6,
        ),
        (
            "RPE Yaw @1m RMSE",
            "rpe_yaw_1m_rmse_deg",
            "deg",
            6,
        ),
        (
            "Process CPU Mean",
            "process_cpu_mean_percent",
            "%",
            4,
        ),
        (
            "Process RAM Mean",
            "process_ram_mean_mb",
            "MB",
            4,
        ),
        (
            "LiDAR Rate",
            "lidar_rate_hz",
            "Hz",
            6,
        ),
        (
            "Camera Rate",
            "camera_rate_hz",
            "Hz",
            4,
        ),
        (
            "SLAM TF Rate",
            "slam_tf_rate_hz",
            "Hz",
            4,
        ),
        (
            "TF Latency Mean",
            "slam_tf_latency_mean_ms",
            "ms",
            4,
        ),
        (
            "TF Latency P95",
            "slam_tf_latency_p95_ms",
            "ms",
            4,
        ),
        (
            "Gazebo RTF",
            "gazebo_rtf_overall",
            "",
            6,
        ),
    ]

    final_rows = []

    for label, key, unit, decimals in metrics:

        values = [
            to_float(r.get(key))
            for r in runs
        ]

        n, mean, sd = mean_sd(values)

        if mean is None:
            mean_str = "N/A"
            sd_str = "N/A"
            combined = "N/A"
        else:
            mean_str = f"{mean:.{decimals}f}"

            if sd is None:
                sd_str = "N/A"
                combined = f"{mean_str} ± N/A"
            else:
                sd_str = f"{sd:.{decimals}f}"
                combined = (
                    f"{mean:.{decimals}f} ± "
                    f"{sd:.{decimals}f}"
                )

        final_rows.append([
            label,
            unit,
            n,
            mean_str,
            sd_str,
            combined,
        ])

    print()
    print("TABLE 3 — FINAL RESULTS: MEAN ± BETWEEN-RUN SD")
    print()

    print_table(
        [
            "Metric",
            "Unit",
            "n",
            "Mean",
            "SD",
            "Mean ± SD",
        ],
        final_rows
    )

    print()
    print("=" * 110)
    print(f"Experiments found: {len(runs)}/10")

    found = [f"{r['_experiment']:02d}" for r in runs]
    print("Runs:", ", ".join(found))

    print(
        "Note: n is calculated independently for each metric."
    )
    print(
        "Experiments 01-10 use the complete localization and performance "
        "monitoring protocol; therefore all reported metrics are expected "
        "to have n=10."
    )
    print("=" * 110)


if __name__ == "__main__":
    main()
