#!/usr/bin/env python3

from pathlib import Path
import argparse
import csv
import re
import subprocess
import sys


BEGIN_RESULTS = "===== YOLO CAMERA OVERLAP METRICS ====="
END_RESULTS = "===== END YOLO CAMERA OVERLAP METRICS ====="

BEGIN_VALIDATION = "===== YOLO OVERLAP VALIDATION ====="
END_VALIDATION = "===== END YOLO OVERLAP VALIDATION ====="


LABEL_MAP = {
    "Overlap start": "yolo_overlap_start_s",
    "Overlap end": "yolo_overlap_end_s",
    "Overlap duration": "yolo_overlap_duration_s",

    "Unique CameraInfo stamps": "camera_info_overlap_frames",
    "Unique YOLO stamps in overlap": "yolo_overlap_frames",
    "Timestamp-matched frames": "yolo_timestamp_matched_frames",
    "CameraInfo stamps unmatched": "camera_info_unmatched_frames",
    "YOLO stamps absent from monitor": "yolo_stamps_absent_from_monitor",

    "CameraInfo source-time rate": "camera_info_overlap_rate_hz",
    "YOLO source-time rate": "yolo_overlap_source_rate_fps",
    "Timestamp matching ratio": "yolo_timestamp_matching_ratio_percent",

    "Mean predict-call wall time": "yolo_predict_mean_ms",
    "Median predict-call wall time": "yolo_predict_median_ms",
    "P95 predict-call wall time": "yolo_predict_p95_ms",
    "P99 predict-call wall time": "yolo_predict_p99_ms",
    "Maximum predict-call wall time": "yolo_predict_max_ms",
    "Mean callback": "yolo_callback_mean_ms",
}


REQUIRED = [
    "yolo_overlap_duration_s",
    "camera_info_overlap_frames",
    "yolo_overlap_frames",
    "yolo_timestamp_matched_frames",
    "camera_info_unmatched_frames",
    "camera_info_overlap_rate_hz",
    "yolo_overlap_source_rate_fps",
    "yolo_timestamp_matching_ratio_percent",
    "yolo_predict_mean_ms",
    "yolo_predict_median_ms",
    "yolo_predict_p95_ms",
    "yolo_predict_p99_ms",
    "yolo_predict_max_ms",
    "yolo_callback_mean_ms",
]


def strip_units(value):
    value = value.strip()

    value = re.sub(
        r"\s*(s|Hz|FPS|%|ms)$",
        "",
        value,
        flags=re.I
    )

    return value.strip()


def parse_output(text):
    metrics = {}

    for line in text.splitlines():
        if ":" not in line:
            continue

        label, value = line.split(":", 1)
        label = label.strip()

        if label not in LABEL_MAP:
            continue

        key = LABEL_MAP[label]
        raw = strip_units(value)

        try:
            metrics[key] = float(raw)
        except ValueError:
            pass

    return metrics


def write_metrics_csv(path, metrics):
    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(metrics.keys())
        )
        writer.writeheader()
        writer.writerow(metrics)


def update_summary_row(path, metrics):
    if not path.exists():
        return

    with path.open(
        "r",
        newline="",
        encoding="utf-8"
    ) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    row = dict(rows[0])

    for key, value in metrics.items():
        row[key] = value

    fields = list(row.keys())

    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )
        writer.writeheader()
        writer.writerow(row)


def replace_marked_block(text, begin, end, block):
    pattern = (
        re.escape(begin) +
        r".*?" +
        re.escape(end)
    )

    text = re.sub(
        pattern,
        "",
        text,
        flags=re.S
    ).rstrip()

    return text + "\n\n" + block.strip() + "\n"


def update_results_summary(path, metrics):
    if not path.exists():
        return

    lines = [
        BEGIN_RESULTS,
        "",
        f"Overlap duration                 : "
        f"{metrics['yolo_overlap_duration_s']:.3f} s",

        f"CameraInfo stamps                : "
        f"{int(metrics['camera_info_overlap_frames'])}",

        f"YOLO stamps in overlap           : "
        f"{int(metrics['yolo_overlap_frames'])}",

        f"Timestamp-matched frames         : "
        f"{int(metrics['yolo_timestamp_matched_frames'])}",

        f"CameraInfo stamps unmatched      : "
        f"{int(metrics['camera_info_unmatched_frames'])}",

        f"YOLO stamps absent from monitor  : "
        f"{int(metrics.get('yolo_stamps_absent_from_monitor', 0))}",

        f"CameraInfo source-time rate      : "
        f"{metrics['camera_info_overlap_rate_hz']:.6f} Hz",

        f"YOLO source-time rate            : "
        f"{metrics['yolo_overlap_source_rate_fps']:.6f} FPS",

        f"Timestamp matching ratio         : "
        f"{metrics['yolo_timestamp_matching_ratio_percent']:.3f} %",

        f"YOLO predict mean                : "
        f"{metrics['yolo_predict_mean_ms']:.3f} ms",

        f"YOLO predict median              : "
        f"{metrics['yolo_predict_median_ms']:.3f} ms",

        f"YOLO predict P95                 : "
        f"{metrics['yolo_predict_p95_ms']:.3f} ms",

        f"YOLO predict P99                 : "
        f"{metrics['yolo_predict_p99_ms']:.3f} ms",

        f"YOLO predict maximum             : "
        f"{metrics['yolo_predict_max_ms']:.3f} ms",

        f"YOLO callback mean               : "
        f"{metrics['yolo_callback_mean_ms']:.3f} ms",
        "",
        "NOTE: Timestamp matching ratio is an observed "
        "CameraInfo-to-YOLO source-timestamp correspondence metric.",
        "It is not a DDS packet-loss measurement.",
        "",
        END_RESULTS,
    ]

    block = "\n".join(lines)

    text = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    text = replace_marked_block(
        text,
        BEGIN_RESULTS,
        END_RESULTS,
        block
    )

    path.write_text(text, encoding="utf-8")


def update_validation(path, metrics, passed, reason):
    if not path.exists():
        return

    if passed:
        block = "\n".join([
            BEGIN_VALIDATION,
            "",
            "YOLO overlap analysis          PASS",
            f"  CameraInfo frames: "
            f"{int(metrics['camera_info_overlap_frames'])}",
            f"  YOLO frames: "
            f"{int(metrics['yolo_overlap_frames'])}",
            f"  Matched frames: "
            f"{int(metrics['yolo_timestamp_matched_frames'])}",
            f"  Timestamp matching ratio: "
            f"{metrics['yolo_timestamp_matching_ratio_percent']:.3f} %",
            f"  YOLO source-time rate: "
            f"{metrics['yolo_overlap_source_rate_fps']:.3f} FPS",
            f"  Mean predict wall time: "
            f"{metrics['yolo_predict_mean_ms']:.3f} ms",
            "",
            END_VALIDATION,
        ])
    else:
        block = "\n".join([
            BEGIN_VALIDATION,
            "",
            "YOLO overlap analysis          FAIL",
            f"  {reason}",
            "",
            END_VALIDATION,
        ])

    text = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    pattern = (
        re.escape(BEGIN_VALIDATION) +
        r".*?" +
        re.escape(END_VALIDATION)
    )

    text = re.sub(
        pattern,
        "",
        text,
        flags=re.S
    )

    marker = "===== VALIDATION RULES ====="

    if marker in text:
        text = text.replace(
            marker,
            block + "\n\n" + marker,
            1
        )
    else:
        text = text.rstrip() + "\n\n" + block + "\n"

    if not passed:
        text = re.sub(
            r"FINAL STATUS:\s*VALID",
            "FINAL STATUS: INVALID",
            text
        )

    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "experiment_dir",
        type=Path
    )

    args = parser.parse_args()

    exp_dir = args.experiment_dir.expanduser().resolve()
    perf = exp_dir / "performance"

    analyzer = (
        Path.home() /
        "turtlebot3_ws/tools/analyze_yolo_overlap.py"
    )

    if not analyzer.exists():
        raise SystemExit(
            f"Missing analyzer: {analyzer}"
        )

    perf.mkdir(
        parents=True,
        exist_ok=True
    )

    cmd = [
        sys.executable,
        str(analyzer),
        str(perf),
    ]

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True
    )

    raw_out = perf / "yolo_overlap_summary.txt"

    raw_out.write_text(
        result.stdout +
        (
            "\nSTDERR:\n" + result.stderr
            if result.stderr else ""
        ),
        encoding="utf-8"
    )

    if result.returncode != 0:
        reason = (
            result.stderr.strip() or
            result.stdout.strip() or
            f"Analyzer return code {result.returncode}"
        )

        update_validation(
            exp_dir / "experiment_validation.txt",
            {},
            False,
            reason
        )

        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)

        raise SystemExit(result.returncode)

    metrics = parse_output(result.stdout)

    missing = [
        key for key in REQUIRED
        if key not in metrics
    ]

    if missing:
        reason = (
            "Missing parsed metrics: " +
            ", ".join(missing)
        )

        update_validation(
            exp_dir / "experiment_validation.txt",
            metrics,
            False,
            reason
        )

        raise SystemExit(reason)

    metrics_csv = (
        perf /
        "yolo_overlap_metrics.csv"
    )

    write_metrics_csv(
        metrics_csv,
        metrics
    )

    update_summary_row(
        exp_dir / "summary_row.csv",
        metrics
    )

    update_results_summary(
        exp_dir / "results_summary.txt",
        metrics
    )

    update_validation(
        exp_dir / "experiment_validation.txt",
        metrics,
        True,
        ""
    )

    print(result.stdout, end="")

    print(
        f"\nSaved overlap summary : {raw_out}"
    )
    print(
        f"Saved overlap metrics : {metrics_csv}"
    )

    if (exp_dir / "summary_row.csv").exists():
        print(
            "Updated summary row    : "
            f"{exp_dir / 'summary_row.csv'}"
        )


if __name__ == "__main__":
    main()
