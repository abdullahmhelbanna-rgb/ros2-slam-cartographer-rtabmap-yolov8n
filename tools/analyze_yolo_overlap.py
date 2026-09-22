#!/usr/bin/env python3

from pathlib import Path
import argparse
import csv
import statistics
import numpy as np


def read_column(path, column):
    values = []

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                values.append(float(row[column]))
            except (ValueError, TypeError, KeyError):
                pass

    return values


def unique_stamps(values):
    # 1 microsecond resolution is more than adequate here.
    return sorted(set(round(v, 6) for v in values))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "performance_dir",
        type=Path
    )

    args = parser.parse_args()

    p = args.performance_dir

    camera_file = p / "camera_events.csv"
    yolo_file = p / "yolo_frames.csv"

    if not camera_file.exists():
        raise SystemExit(f"Missing: {camera_file}")

    if not yolo_file.exists():
        raise SystemExit(f"Missing: {yolo_file}")

    camera_all = unique_stamps(
        read_column(camera_file, "source_stamp_s")
    )

    yolo_all = unique_stamps(
        read_column(yolo_file, "source_stamp_s")
    )

    if not camera_all:
        raise SystemExit("No valid camera timestamps")

    if not yolo_all:
        raise SystemExit("No valid YOLO timestamps")

    overlap_start = max(camera_all[0], yolo_all[0])
    overlap_end = min(camera_all[-1], yolo_all[-1])

    if overlap_end <= overlap_start:
        raise SystemExit("No common timestamp interval")

    camera = [
        t for t in camera_all
        if overlap_start <= t <= overlap_end
    ]

    yolo = [
        t for t in yolo_all
        if overlap_start <= t <= overlap_end
    ]

    camera_set = set(camera)
    yolo_set = set(yolo)

    matched = camera_set & yolo_set
    not_processed = camera_set - yolo_set
    yolo_not_seen_by_camera_monitor = yolo_set - camera_set

    duration = overlap_end - overlap_start

    camera_rate = (
        (len(camera) - 1) /
        (camera[-1] - camera[0])
        if len(camera) >= 2 and camera[-1] > camera[0]
        else float("nan")
    )

    yolo_source_rate = (
        (len(yolo) - 1) /
        (yolo[-1] - yolo[0])
        if len(yolo) >= 2 and yolo[-1] > yolo[0]
        else float("nan")
    )

    ratio = (
        100.0 * len(matched) / len(camera)
        if camera else float("nan")
    )

    inference = []
    callback = []
    overlap_rows = 0

    with yolo_file.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                stamp = float(row["source_stamp_s"])
            except (ValueError, TypeError, KeyError):
                continue

            if not np.isfinite(stamp):
                continue
            if not overlap_start <= round(stamp, 6) <= overlap_end:
                continue

            overlap_rows += 1

            for column, target in (
                ("wall_inference_ms", inference),
                ("total_callback_ms", callback),
            ):
                try:
                    value = float(row[column])
                except (ValueError, TypeError, KeyError):
                    continue
                if np.isfinite(value) and value >= 0:
                    target.append(value)

    print(f"YOLO rows selected for timing: {overlap_rows}")
    print(f"Valid predict/callback samples: {len(inference)}/{len(callback)}")


    print("=" * 72)
    print("YOLO / CAMERAINFO SOURCE-TIMESTAMP OVERLAP")
    print("=" * 72)

    print(f"Overlap start                    : {overlap_start:.6f} s")
    print(f"Overlap end                      : {overlap_end:.6f} s")
    print(f"Overlap duration                 : {duration:.3f} s")
    print()

    print(f"Unique CameraInfo stamps    : {len(camera)}")
    print(f"Unique YOLO stamps in overlap           : {len(yolo)}")
    print(f"Timestamp-matched frames         : {len(matched)}")
    print(f"CameraInfo stamps unmatched      : {len(not_processed)}")
    print(
        f"YOLO stamps absent from monitor  : "
        f"{len(yolo_not_seen_by_camera_monitor)}"
    )
    print()

    print(f"CameraInfo source-time rate             : {camera_rate:.6f} Hz")
    print(f"YOLO source-time rate           : {yolo_source_rate:.6f} FPS")
    print(f"Timestamp matching ratio            : {ratio:.3f} %")
    print()

    if inference:
        print(
            f"Mean predict-call wall time              : "
            f"{statistics.mean(inference):.3f} ms"
        )
        print(
            f"Median predict-call wall time            : "
            f"{statistics.median(inference):.3f} ms"
        )
        print(
            f"P95 predict-call wall time               : "
            f"{np.percentile(inference, 95):.3f} ms"
        )
        print(
            f"P99 predict-call wall time               : "
            f"{np.percentile(inference, 99):.3f} ms"
        )
        print(
            f"Maximum predict-call wall time           : "
            f"{max(inference):.3f} ms"
        )

    if callback:
        print(
            f"Mean callback                    : "
            f"{statistics.mean(callback):.3f} ms"
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
