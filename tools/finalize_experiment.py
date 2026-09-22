#!/usr/bin/env python3

import argparse
import csv
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


HOME = Path.home()
WS = HOME / "turtlebot3_ws"
TOOLS = WS / "tools"
BASE = WS / "metrics" / "experiments"


def percentile(values, p):
    if not values:
        return float("nan")

    v = sorted(values)
    k = (len(v) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)

    if lo == hi:
        return v[lo]

    return v[lo] * (hi - k) + v[hi] * (k - lo)


def run(cmd, cwd=None, output_file=None):
    print()
    print(">>>", " ".join(str(x) for x in cmd))

    if output_file:
        with open(output_file, "w") as f:
            p = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
            )
    else:
        p = subprocess.run(
            cmd,
            cwd=cwd
        )

    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed with code {p.returncode}"
        )


def require(path):
    if not path.exists():
        print(f"ERROR: Required file not found:")
        print(path)
        sys.exit(1)


def parse_evo(path):
    text = path.read_text(
        errors="ignore"
    )

    stats = {}

    for key in [
        "max",
        "mean",
        "median",
        "min",
        "rmse",
        "std",
        "sse",
    ]:
        m = re.search(
            rf"^\s*{key}\s+([-+0-9.eE]+)",
            text,
            re.MULTILINE,
        )

        if m:
            stats[key] = float(m.group(1))

    m = re.search(
        r"Found\s+(\d+)\s+of max\.\s+"
        r"(\d+)\s+possible matching timestamps",
        text,
    )

    if m:
        stats["matched"] = int(m.group(1))
        stats["possible"] = int(m.group(2))

    return stats


def resource_values(rows, key, skip_first=False):
    out = []

    for row in rows:
        try:
            value = row[key].strip()

            if value != "":
                out.append(float(value))

        except Exception:
            pass

    # CPU utilization from psutil requires counter warm-up.
    # Exactly the first numeric CPU observation is excluded
    # when requested. This is position-based, not value-based.
    if skip_first and out:
        out = out[1:]

    return out


def stat_block(values):
    if not values:
        return {}

    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def create_resource_summary(perf):
    p = perf / "resources.csv"

    if not p.exists():
        print("WARNING: resources.csv not found")
        return {}

    with p.open() as f:
        rows = list(csv.DictReader(f))

    data = {
        "samples": len(rows)
    }

    # Original combined/system fields remain unchanged.
    # Optional per-process fields are read when present.
    fields = {
        "system_cpu_percent":
            "system_cpu",

        "process_cpu_percent_sum":
            "process_cpu",

        "process_rss_mb_sum":
            "process_ram_mb",

        "system_ram_percent":
            "system_ram",

        "cartographer_node_cpu_percent":
            "cartographer_cpu",

        "cartographer_node_rss_mb":
            "cartographer_ram_mb",

        "rtabmap_cpu_percent":
            "rtab_cpu",

        "rtabmap_rss_mb":
            "rtab_ram_mb",

        "yolo_node_cpu_percent":
            "yolo_cpu",

        "yolo_node_rss_mb":
            "yolo_ram_mb",
    }

    cpu_fields = {
        "system_cpu_percent",
        "process_cpu_percent_sum",
        "cartographer_node_cpu_percent",
        "rtabmap_cpu_percent",
        "yolo_node_cpu_percent",
    }

    for csv_key, name in fields.items():
        values = resource_values(
            rows,
            csv_key,
            skip_first=(csv_key in cpu_fields)
        )

        data[name] = stat_block(values)

    processes = sorted({
        row.get(
            "matched_processes",
            ""
        ).strip()
        for row in rows
        if row.get(
            "matched_processes",
            ""
        ).strip()
    })

    data["processes"] = processes

    lines = [
        f"samples: {len(rows)}",
        (
            "cpu_preprocessing: exactly the first numeric CPU "
            "sample of each CPU series was excluded as the "
            "psutil warm-up observation"
        ),
        (
            "cpu_filtering: position-based only; no later low "
            "or zero CPU values were removed"
        ),
        "ram_preprocessing: no first-sample exclusion",
        "",
        "matched_processes:",
    ]

    for x in processes:
        lines.append(f"  {x}")

    resource_blocks = [
        "system_cpu",
        "process_cpu",
        "process_ram_mb",
        "system_ram",
        "cartographer_cpu",
        "cartographer_ram_mb",
        "rtab_cpu",
        "rtab_ram_mb",
        "yolo_cpu",
        "yolo_ram_mb",
    ]

    for name in resource_blocks:
        block = data.get(name, {})

        # Old baseline files do not contain the optional
        # per-process columns. Do not print empty blocks.
        if not block:
            continue

        lines.append("")
        lines.append(name)

        for key in [
            "mean",
            "median",
            "p95",
            "max",
        ]:
            if key in block:
                lines.append(
                    f"{key}: "
                    f"{block[key]:.6f}"
                )

    (
        perf /
        "resource_summary.txt"
    ).write_text(
        "\n".join(lines) + "\n"
    )

    return data


def create_camera_summary(perf):
    summary = perf / "camera_rate_summary.txt"

    if summary.exists():
        return parse_key_value_file(summary)

    events = perf / "camera_events.csv"

    if not events.exists():
        print(
            "WARNING: Camera events not found"
        )
        return {}

    with events.open() as f:
        rows = list(csv.DictReader(f))

    stamps = []

    for row in rows:
        try:
            stamps.append(
                float(row["source_stamp_s"])
            )
        except Exception:
            pass

    if len(stamps) < 2:
        return {}

    # Keep only strictly increasing
    clean = []

    last = None

    for s in stamps:
        if last is None or s > last:
            clean.append(s)
            last = s

    if len(clean) < 2:
        return {}

    dts = [
        b-a
        for a,b in zip(
            clean[:-1],
            clean[1:]
        )
        if b > a
    ]

    duration = (
        clean[-1] - clean[0]
    )

    rate = (
        (len(clean)-1) / duration
        if duration > 0
        else float("nan")
    )

    median_dt = statistics.median(dts)

    gap_threshold = (
        1.5 * median_dt
    )

    gap_events = sum(
        1
        for dt in dts
        if dt > gap_threshold
    )

    skipped = 0

    for dt in dts:
        if dt > gap_threshold:
            skipped += max(
                0,
                round(
                    dt / median_dt
                ) - 1
            )

    data = {
        "camera_messages":
            len(stamps),

        "camera_unique_source_stamps":
            len(set(stamps)),

        "camera_duration_s":
            duration,

        "camera_rate_hz":
            rate,

        "camera_median_period_ms":
            median_dt * 1000.0,

        "camera_p95_period_ms":
            percentile(
                dts,
                95
            ) * 1000.0,

        "camera_max_gap_ms":
            max(dts) * 1000.0,

        "camera_gap_events":
            gap_events,

        "camera_estimated_skipped_intervals":
            skipped,
    }

    lines = []

    for k,v in data.items():
        if isinstance(v, float):
            lines.append(
                f"{k}: {v:.6f}"
            )
        else:
            lines.append(
                f"{k}: {v}"
            )

    lines += [
        "",
        "NOTE: Camera rate is based on "
        "observed camera source timestamps.",
        "Estimated skipped intervals are "
        "not a DDS packet-loss count.",
    ]

    summary.write_text(
        "\n".join(lines) + "\n"
    )

    return data


def parse_key_value_file(path):
    data = {}

    if not path.exists():
        return data

    for line in path.read_text(
        errors="ignore"
    ).splitlines():

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1
        )

        key = key.strip()
        value = value.strip()

        if not key:
            continue

        try:
            data[key] = float(value)

        except ValueError:
            data[key] = value

    return data


def parse_yolo(perf):
    candidates = [
        perf / "yolo_frames_summary.txt",
        perf / "yolo_summary.txt",
    ]

    for p in candidates:
        if p.exists():
            return parse_key_value_file(p)

    return {}


def get(d, key, default="N/A"):
    if key not in d:
        return default

    v = d[key]

    if isinstance(v, float):
        return f"{v:.6f}"

    return str(v)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a SLAM experiment: "
            "EVO metrics, plots and "
            "performance summary."
        )
    )

    parser.add_argument(
        "configuration",
        choices=[
            "cartographer",
            "cartographer_yolo",
            "rtab",
            "rtab_yolo",
        ]
    )

    parser.add_argument(
        "experiment",
        type=int
    )

    args = parser.parse_args()

    exp_name = (
        f"experiment_{args.experiment:02d}"
    )

    exp = (
        BASE /
        args.configuration /
        exp_name
    )

    perf = exp / "performance"
    plots = exp / "plots"

    gt = exp / "gt_tum.txt"
    slam = exp / "slam_tum.txt"

    gt_clean = (
        exp /
        "gt_planar_clean.tum"
    )

    slam_clean = (
        exp /
        "slam_planar_clean.tum"
    )

    print("=" * 65)
    print(
        "FINALIZING:",
        args.configuration,
        exp_name
    )
    print("=" * 65)

    require(gt)
    require(slam)

    perf.mkdir(
        parents=True,
        exist_ok=True
    )

    plots.mkdir(
        parents=True,
        exist_ok=True
    )

    # ------------------------------------------------
    # 1. Planar conversion
    # ------------------------------------------------

    run([
        "python3",
        str(
            TOOLS /
            "make_planar_tum.py"
        ),
        str(gt),
        str(gt_clean),
    ])

    run([
        "python3",
        str(
            TOOLS /
            "make_planar_tum.py"
        ),
        str(slam),
        str(slam_clean),
    ])

    # ------------------------------------------------
    # 2. EVO metrics
    # ------------------------------------------------

    tests = [
        (
            "ape_translation",
            "evo_ape",
            "trans_part",
            True,
            False,
        ),
        (
            "ape_yaw",
            "evo_ape",
            "angle_deg",
            True,
            False,
        ),
        (
            "rpe_translation_1m",
            "evo_rpe",
            "trans_part",
            False,
            True,
        ),
        (
            "rpe_yaw_1m",
            "evo_rpe",
            "angle_deg",
            False,
            True,
        ),
    ]

    evo_results = {}

    for (
        name,
        command,
        relation,
        align_origin,
        rpe,
    ) in tests:

        txt = exp / f"{name}.txt"
        zipp = exp / f"{name}.zip"

        # Remove previous EVO outputs so rerunning this
        # finalizer never waits for an overwrite prompt.
        for old_file in (txt, zipp):
            if old_file.exists():
                old_file.unlink()

        cmd = [
            command,
            "tum",
            str(gt_clean),
            str(slam_clean),
            "--t_max_diff",
            "0.02",
        ]

        if align_origin:
            cmd += [
                "--align_origin"
            ]

        if rpe:
            cmd += [
                "--delta",
                "1",
                "--delta_unit",
                "m",
                "--all_pairs",
            ]

        cmd += [
            "-r",
            relation,
            "-v",
            "--save_results",
            str(zipp),
        ]

        run(
            cmd,
            cwd=exp,
            output_file=txt
        )

        evo_results[name] = (
            parse_evo(txt)
        )

    # ------------------------------------------------
    # 3. Plots
    # ------------------------------------------------

    plot_script = (
        TOOLS /
        "plot_experiment_results.py"
    )

    if plot_script.exists():

        run([
            "python3",
            str(plot_script),
            str(gt_clean),
            str(slam_clean),
            str(plots),
        ])

        # The old plotting script may use
        # experiment01 in the filename.
        old_combined = (
            plots /
            "05_experiment01_combined_results.png"
        )

        new_combined = (
            plots /
            (
                f"05_{args.configuration}_"
                f"{exp_name}_combined_results.png"
            )
        )

        if (
            old_combined.exists()
            and old_combined != new_combined
        ):
            shutil.copy2(
                old_combined,
                new_combined
            )
            old_combined.unlink()

    else:
        print(
            "WARNING: plot_experiment_results.py "
            "not found. Metrics still generated."
        )

    # ------------------------------------------------
    # 4. Performance
    # ------------------------------------------------

    resource = create_resource_summary(
        perf
    )

    camera = create_camera_summary(
        perf
    )

    monitor = parse_key_value_file(
        perf /
        "monitor_summary.txt"
    )

    yolo = parse_yolo(perf)

    # ------------------------------------------------
    # 5. Extract important results
    # ------------------------------------------------

    ape_t = evo_results[
        "ape_translation"
    ]

    ape_y = evo_results[
        "ape_yaw"
    ]

    rpe_t = evo_results[
        "rpe_translation_1m"
    ]

    rpe_y = evo_results[
        "rpe_yaw_1m"
    ]

    matched = ape_t.get(
        "matched",
        0
    )

    possible = ape_t.get(
        "possible",
        0
    )

    matched_pct = (
        100.0 * matched / possible
        if possible
        else float("nan")
    )

    proc_cpu = resource.get(
        "process_cpu",
        {}
    )

    proc_ram = resource.get(
        "process_ram_mb",
        {}
    )

    sys_cpu = resource.get(
        "system_cpu",
        {}
    )

    sys_ram = resource.get(
        "system_ram",
        {}
    )

    # Optional per-process resource measurements.
    # Present in the revised multi-process resources.csv.
    cart_cpu_resource = resource.get(
        "cartographer_cpu",
        {}
    )

    cart_ram_resource = resource.get(
        "cartographer_ram_mb",
        {}
    )

    rtab_cpu_resource = resource.get(
        "rtab_cpu",
        {}
    )

    rtab_ram_resource = resource.get(
        "rtab_ram_mb",
        {}
    )

    yolo_cpu_resource = resource.get(
        "yolo_cpu",
        {}
    )

    yolo_ram_resource = resource.get(
        "yolo_ram_mb",
        {}
    )

    # ------------------------------------------------
    # 6. Automatic experiment validation
    # ------------------------------------------------

    def count_lines(path):
        if not path.exists():
            return 0

        with path.open(errors="ignore") as f:
            return sum(
                1 for line in f
                if line.strip()
            )

    validation = []

    def check(label, passed, details=""):
        validation.append({
            "label": label,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        })

    def info(label, details=""):
        validation.append({
            "label": label,
            "status": "N/A",
            "details": details,
        })

    gt_count = count_lines(gt)
    slam_count = count_lines(slam)

    check(
        "GT trajectory",
        gt_count >= 100,
        f"{gt_count} samples"
    )

    check(
        "SLAM trajectory",
        slam_count >= 100,
        f"{slam_count} samples"
    )

    check(
        "Timestamp matching",
        possible > 0 and matched_pct >= 95.0,
        (
            f"{matched}/{possible} matched "
            f"({matched_pct:.3f} %)"
            if possible
            else "No matching result"
        )
    )

    localization_ok = all(
        "rmse" in block
        for block in [
            ape_t,
            ape_y,
            rpe_t,
            rpe_y,
        ]
    )

    check(
        "APE / RPE metrics",
        localization_ok,
        "All four EVO RMSE metrics available"
        if localization_ok
        else "One or more EVO metrics missing"
    )

    resource_samples = int(
        resource.get("samples", 0)
        or 0
    )

    cpu_ok = (
        resource_samples >= 30
        and bool(proc_cpu)
        and "mean" in proc_cpu
    )

    check(
        "CPU recording",
        cpu_ok,
        f"{resource_samples} resource samples"
    )

    ram_ok = (
        resource_samples >= 30
        and bool(proc_ram)
        and "mean" in proc_ram
    )

    check(
        "RAM recording",
        ram_ok,
        (
            f"Mean process RSS "
            f"{proc_ram.get('mean', float('nan')):.3f} MB"
            if proc_ram
            else "RAM data missing"
        )
    )

    lidar_messages = monitor.get(
        "lidar_messages",
        0
    )

    lidar_rate = monitor.get(
        "lidar_rate_hz",
        0
    )

    lidar_ok = (
        isinstance(lidar_messages, (int, float))
        and isinstance(lidar_rate, (int, float))
        and lidar_messages >= 100
        and lidar_rate > 0
    )

    check(
        "LiDAR recording",
        lidar_ok,
        (
            f"{lidar_messages:.0f} messages, "
            f"{lidar_rate:.3f} Hz"
            if isinstance(lidar_rate, (int, float))
            else "LiDAR data missing"
        )
    )

    camera_messages = camera.get(
        "camera_messages",
        0
    )

    camera_rate = camera.get(
        "camera_rate_hz",
        0
    )

    camera_ok = (
        isinstance(camera_messages, (int, float))
        and isinstance(camera_rate, (int, float))
        and camera_messages >= 100
        and camera_rate > 0
    )

    check(
        "Camera recording",
        camera_ok,
        (
            f"{camera_messages:.0f} messages, "
            f"{camera_rate:.3f} Hz"
            if isinstance(camera_rate, (int, float))
            else "Camera data missing"
        )
    )

    tf_messages = monitor.get(
        "slam_tf_messages",
        0
    )

    tf_rate = monitor.get(
        "slam_tf_rate_hz",
        0
    )

    tf_ok = (
        isinstance(tf_messages, (int, float))
        and isinstance(tf_rate, (int, float))
        and tf_messages >= 100
        and tf_rate > 0
    )

    check(
        "SLAM TF recording",
        tf_ok,
        (
            f"{tf_messages:.0f} updates, "
            f"{tf_rate:.3f} Hz"
            if isinstance(tf_rate, (int, float))
            else "SLAM TF data missing"
        )
    )

    latency_samples = monitor.get(
        "slam_tf_latency_samples",
        0
    )

    latency_mean = monitor.get(
        "slam_tf_latency_mean_ms",
        None
    )

    latency_ok = (
        isinstance(latency_samples, (int, float))
        and latency_samples > 0
        and isinstance(latency_mean, (int, float))
        and latency_mean >= 0
    )

    check(
        "TF latency",
        latency_ok,
        (
            f"{latency_samples:.0f} samples, "
            f"mean {latency_mean:.3f} ms"
            if isinstance(latency_mean, (int, float))
            else "Latency data missing"
        )
    )

    rtf_samples = monitor.get(
        "clock_rtf_samples",
        0
    )

    rtf_overall = monitor.get(
        "gazebo_rtf_overall",
        None
    )

    rtf_ok = (
        isinstance(rtf_samples, (int, float))
        and rtf_samples >= 10
        and isinstance(rtf_overall, (int, float))
        and rtf_overall > 0
    )

    check(
        "Gazebo RTF",
        rtf_ok,
        (
            f"{rtf_samples:.0f} samples, "
            f"overall {rtf_overall:.6f}"
            if isinstance(rtf_overall, (int, float))
            else "RTF data missing"
        )
    )

    if "yolo" in args.configuration:

        yolo_frames = yolo.get(
            "frames_processed",
            0
        )

        yolo_fps = yolo.get(
            "effective_fps",
            0
        )

        yolo_inf = yolo.get(
            "mean_wall_inference_ms",
            0
        )

        yolo_device = yolo.get(
            "device",
            ""
        )

        yolo_ok = (
            isinstance(yolo_frames, (int, float))
            and yolo_frames > 0
            and isinstance(yolo_fps, (int, float))
            and yolo_fps > 0
            and isinstance(yolo_inf, (int, float))
            and yolo_inf > 0
            and str(yolo_device).strip() != ""
        )

        check(
            "YOLO measurements",
            yolo_ok,
            (
                f"{yolo_frames} frames, "
                f"{yolo_fps} FPS, "
                f"{yolo_inf} ms, "
                f"device={yolo_device}"
            )
        )

        if args.configuration in {
            "cartographer_yolo",
            "rtab_yolo",
        }:

            if args.configuration == "cartographer_yolo":
                slam_name = "Cartographer"
                slam_cpu_resource = cart_cpu_resource
                slam_ram_resource = cart_ram_resource
            else:
                slam_name = "RTAB-Map"
                slam_cpu_resource = rtab_cpu_resource
                slam_ram_resource = rtab_ram_resource

            slam_cpu_mean = slam_cpu_resource.get(
                "mean",
                None
            )

            slam_ram_mean = slam_ram_resource.get(
                "mean",
                None
            )

            yolo_cpu_mean = yolo_cpu_resource.get(
                "mean",
                None
            )

            yolo_ram_mean = yolo_ram_resource.get(
                "mean",
                None
            )

            per_process_resource_values = [
                slam_cpu_mean,
                slam_ram_mean,
                yolo_cpu_mean,
                yolo_ram_mean,
            ]

            per_process_resources_ok = all(
                isinstance(value, (int, float))
                and value > 0
                for value in per_process_resource_values
            )

            check(
                "Per-process resources",
                per_process_resources_ok,
                (
                    (
                        f"{slam_name} CPU "
                        f"{slam_cpu_mean:.3f} %, "
                        f"RAM {slam_ram_mean:.3f} MB; "
                        f"YOLO CPU "
                        f"{yolo_cpu_mean:.3f} %, "
                        f"RAM {yolo_ram_mean:.3f} MB"
                    )
                    if per_process_resources_ok
                    else (
                        f"{slam_name}/YOLO separate "
                        "CPU/RAM measurements missing"
                    )
                )
            )

    else:

        info(
            "YOLO measurements",
            "Not applicable to baseline configuration"
        )

    failed = [
        x for x in validation
        if x["status"] == "FAIL"
    ]

    final_status = (
        "VALID"
        if not failed
        else "INVALID"
    )

    validation_lines = [
        f"Configuration: {args.configuration}",
        f"Experiment: {args.experiment:02d}",
        "",
        "===== AUTOMATIC VALIDATION =====",
        "",
    ]

    for item in validation:

        validation_lines.append(
            f"{item['label']:<28} "
            f"{item['status']}"
        )

        if item["details"]:
            validation_lines.append(
                f"  {item['details']}"
            )

    validation_lines += [
        "",
        "===== VALIDATION RULES =====",
        "GT samples >= 100",
        "SLAM samples >= 100",
        "Timestamp matching >= 95 %",
        "All four EVO RMSE metrics available",
        "Resource samples >= 30",
        "LiDAR messages >= 100 and rate > 0",
        "Camera messages >= 100 and rate > 0",
        "SLAM TF updates >= 100 and rate > 0",
        "TF latency samples > 0",
        "Gazebo RTF samples >= 10 and overall RTF > 0",
        "YOLO metrics required only for YOLO configurations",
        "Separate Cartographer/YOLO CPU and RAM required for cartographer_yolo",
        "Separate RTAB-Map/YOLO CPU and RAM required for rtab_yolo",
        "",
        f"FINAL STATUS: {final_status}",
    ]

    validation_file = (
        exp /
        "experiment_validation.txt"
    )

    validation_file.write_text(
        "\n".join(validation_lines) + "\n"
    )

    # ------------------------------------------------
    # 7. Human-readable summary
    # ------------------------------------------------

    lines = [
        f"Configuration: {args.configuration}",
        f"Experiment: {args.experiment:02d}",
        f"Status: {final_status}",
        "",
        "===== TRAJECTORY MATCHING =====",
        f"Matched poses: {matched} / {possible}",
        f"Matched percentage: {matched_pct:.3f} %",
        "",
        "===== APE TRANSLATION =====",
        f"Mean: {ape_t.get('mean', float('nan')):.6f} m",
        f"Median: {ape_t.get('median', float('nan')):.6f} m",
        f"RMSE: {ape_t.get('rmse', float('nan')):.6f} m",
        f"Std: {ape_t.get('std', float('nan')):.6f} m",
        f"Max: {ape_t.get('max', float('nan')):.6f} m",
        "",
        "===== APE YAW =====",
        f"Mean: {ape_y.get('mean', float('nan')):.6f} deg",
        f"Median: {ape_y.get('median', float('nan')):.6f} deg",
        f"RMSE: {ape_y.get('rmse', float('nan')):.6f} deg",
        f"Std: {ape_y.get('std', float('nan')):.6f} deg",
        f"Max: {ape_y.get('max', float('nan')):.6f} deg",
        "",
        "===== RPE TRANSLATION @ 1 m =====",
        f"Mean: {rpe_t.get('mean', float('nan')):.6f} m",
        f"Median: {rpe_t.get('median', float('nan')):.6f} m",
        f"RMSE: {rpe_t.get('rmse', float('nan')):.6f} m",
        f"Std: {rpe_t.get('std', float('nan')):.6f} m",
        f"Max: {rpe_t.get('max', float('nan')):.6f} m",
        "",
        "===== RPE YAW @ 1 m =====",
        f"Mean: {rpe_y.get('mean', float('nan')):.6f} deg",
        f"Median: {rpe_y.get('median', float('nan')):.6f} deg",
        f"RMSE: {rpe_y.get('rmse', float('nan')):.6f} deg",
        f"Std: {rpe_y.get('std', float('nan')):.6f} deg",
        f"Max: {rpe_y.get('max', float('nan')):.6f} deg",
        "",
        "===== PROCESS CPU =====",
        f"Mean: {proc_cpu.get('mean', float('nan')):.6f} %",
        f"Median: {proc_cpu.get('median', float('nan')):.6f} %",
        f"P95: {proc_cpu.get('p95', float('nan')):.6f} %",
        f"Max: {proc_cpu.get('max', float('nan')):.6f} %",
        "",
        "===== PROCESS RAM =====",
        f"Mean: {proc_ram.get('mean', float('nan')):.6f} MB",
        f"Median: {proc_ram.get('median', float('nan')):.6f} MB",
        f"P95: {proc_ram.get('p95', float('nan')):.6f} MB",
        f"Max: {proc_ram.get('max', float('nan')):.6f} MB",
        "",
        "===== SYSTEM CPU / RAM =====",
        f"System CPU Mean: {sys_cpu.get('mean', float('nan')):.6f} %",
        f"System CPU P95: {sys_cpu.get('p95', float('nan')):.6f} %",
        f"System RAM Mean: {sys_ram.get('mean', float('nan')):.6f} %",
        f"System RAM P95: {sys_ram.get('p95', float('nan')):.6f} %",
        "",
        "===== SENSOR / SLAM PERFORMANCE =====",
        f"LiDAR Rate: {get(monitor, 'lidar_rate_hz')} Hz",
        f"Camera Rate: {get(camera, 'camera_rate_hz')} Hz",
        f"SLAM TF Rate: {get(monitor, 'slam_tf_rate_hz')} Hz",
        f"SLAM TF Latency Mean: {get(monitor, 'slam_tf_latency_mean_ms')} ms",
        f"SLAM TF Latency P95: {get(monitor, 'slam_tf_latency_p95_ms')} ms",
        f"Gazebo RTF Overall: {get(monitor, 'gazebo_rtf_overall')}",
        f"Gazebo RTF Mean: {get(monitor, 'gazebo_rtf_mean')}",
        "",
        "===== YOLO =====",
    ]

    if yolo:
        lines += [
            f"Device: {get(yolo, 'device')}",
            f"Frames processed: {get(yolo, 'frames_processed')}",
            f"Effective FPS: {get(yolo, 'effective_fps')}",
            f"Mean inference: {get(yolo, 'mean_wall_inference_ms')} ms",
            f"P95 inference: {get(yolo, 'p95_wall_inference_ms')} ms",
            f"P99 inference: {get(yolo, 'p99_wall_inference_ms')} ms",
        ]

    else:
        lines += [
            "YOLO active: No",
            "YOLO device: N/A",
            "YOLO inference: N/A",
        ]

    if (
        cart_cpu_resource
        or cart_ram_resource
        or rtab_cpu_resource
        or rtab_ram_resource
        or yolo_cpu_resource
        or yolo_ram_resource
    ):
        lines += [
            "",
            "===== PER-PROCESS RESOURCE BREAKDOWN =====",
        ]

        if cart_cpu_resource or cart_ram_resource:
            lines += [
                "",
                "Cartographer CPU:",
                f"Mean: {cart_cpu_resource.get('mean', float('nan')):.6f} %",
                f"Median: {cart_cpu_resource.get('median', float('nan')):.6f} %",
                f"P95: {cart_cpu_resource.get('p95', float('nan')):.6f} %",
                f"Max: {cart_cpu_resource.get('max', float('nan')):.6f} %",
                "",
                "Cartographer RAM:",
                f"Mean: {cart_ram_resource.get('mean', float('nan')):.6f} MB",
                f"Median: {cart_ram_resource.get('median', float('nan')):.6f} MB",
                f"P95: {cart_ram_resource.get('p95', float('nan')):.6f} MB",
                f"Max: {cart_ram_resource.get('max', float('nan')):.6f} MB",
            ]

        if rtab_cpu_resource or rtab_ram_resource:
            lines += [
                "",
                "RTAB-Map CPU:",
                f"Mean: {rtab_cpu_resource.get('mean', float('nan')):.6f} %",
                f"Median: {rtab_cpu_resource.get('median', float('nan')):.6f} %",
                f"P95: {rtab_cpu_resource.get('p95', float('nan')):.6f} %",
                f"Max: {rtab_cpu_resource.get('max', float('nan')):.6f} %",
                "",
                "RTAB-Map RAM:",
                f"Mean: {rtab_ram_resource.get('mean', float('nan')):.6f} MB",
                f"Median: {rtab_ram_resource.get('median', float('nan')):.6f} MB",
                f"P95: {rtab_ram_resource.get('p95', float('nan')):.6f} MB",
                f"Max: {rtab_ram_resource.get('max', float('nan')):.6f} MB",
            ]

        if yolo_cpu_resource or yolo_ram_resource:
            lines += [
                "",
                "YOLO CPU:",
                f"Mean: {yolo_cpu_resource.get('mean', float('nan')):.6f} %",
                f"Median: {yolo_cpu_resource.get('median', float('nan')):.6f} %",
                f"P95: {yolo_cpu_resource.get('p95', float('nan')):.6f} %",
                f"Max: {yolo_cpu_resource.get('max', float('nan')):.6f} %",
                "",
                "YOLO RAM:",
                f"Mean: {yolo_ram_resource.get('mean', float('nan')):.6f} MB",
                f"Median: {yolo_ram_resource.get('median', float('nan')):.6f} MB",
                f"P95: {yolo_ram_resource.get('p95', float('nan')):.6f} MB",
                f"Max: {yolo_ram_resource.get('max', float('nan')):.6f} MB",
            ]

    lines += [
        "",
        "===== NOTES =====",
        "APE uses planar trajectories and origin alignment.",
        "RPE is evaluated at a 1 m delta.",
        "TF latency is an observed LiDAR-receipt to global-TF-receipt wall-time latency proxy.",
        "Estimated skipped intervals are inferred from timestamp gaps and are not DDS packet-loss counts.",
        "Numerical localization metrics are taken from EVO outputs.",
    ]

    summary_file = (
        exp /
        "results_summary.txt"
    )

    summary_file.write_text(
        "\n".join(lines) + "\n"
    )

    # ------------------------------------------------
    # 8. Machine-readable CSV row
    # ------------------------------------------------

    row = {
        "configuration":
            args.configuration,

        "experiment":
            f"{args.experiment:02d}",

        "matched_poses":
            matched,

        "possible_poses":
            possible,

        "matched_percent":
            matched_pct,

        "ape_translation_rmse_m":
            ape_t.get("rmse", ""),

        "ape_translation_mean_m":
            ape_t.get("mean", ""),

        "ape_yaw_rmse_deg":
            ape_y.get("rmse", ""),

        "ape_yaw_mean_deg":
            ape_y.get("mean", ""),

        "rpe_translation_1m_rmse_m":
            rpe_t.get("rmse", ""),

        "rpe_translation_1m_mean_m":
            rpe_t.get("mean", ""),

        "rpe_yaw_1m_rmse_deg":
            rpe_y.get("rmse", ""),

        "rpe_yaw_1m_mean_deg":
            rpe_y.get("mean", ""),

        "process_cpu_mean_percent":
            proc_cpu.get("mean", ""),

        "process_cpu_p95_percent":
            proc_cpu.get("p95", ""),

        "process_ram_mean_mb":
            proc_ram.get("mean", ""),

        "process_ram_p95_mb":
            proc_ram.get("p95", ""),

        "cartographer_cpu_mean_percent":
            cart_cpu_resource.get("mean", ""),

        "cartographer_cpu_p95_percent":
            cart_cpu_resource.get("p95", ""),

        "cartographer_ram_mean_mb":
            cart_ram_resource.get("mean", ""),

        "cartographer_ram_p95_mb":
            cart_ram_resource.get("p95", ""),

        "rtab_cpu_mean_percent":
            rtab_cpu_resource.get("mean", ""),

        "rtab_cpu_p95_percent":
            rtab_cpu_resource.get("p95", ""),

        "rtab_ram_mean_mb":
            rtab_ram_resource.get("mean", ""),

        "rtab_ram_p95_mb":
            rtab_ram_resource.get("p95", ""),

        "yolo_cpu_mean_percent":
            yolo_cpu_resource.get("mean", ""),

        "yolo_cpu_p95_percent":
            yolo_cpu_resource.get("p95", ""),

        "yolo_ram_mean_mb":
            yolo_ram_resource.get("mean", ""),

        "yolo_ram_p95_mb":
            yolo_ram_resource.get("p95", ""),

        "system_cpu_mean_percent":
            sys_cpu.get("mean", ""),

        "system_ram_mean_percent":
            sys_ram.get("mean", ""),

        "lidar_rate_hz":
            monitor.get(
                "lidar_rate_hz",
                ""
            ),

        "camera_rate_hz":
            camera.get(
                "camera_rate_hz",
                ""
            ),

        "slam_tf_rate_hz":
            monitor.get(
                "slam_tf_rate_hz",
                ""
            ),

        "slam_tf_latency_mean_ms":
            monitor.get(
                "slam_tf_latency_mean_ms",
                ""
            ),

        "slam_tf_latency_p95_ms":
            monitor.get(
                "slam_tf_latency_p95_ms",
                ""
            ),

        "gazebo_rtf_overall":
            monitor.get(
                "gazebo_rtf_overall",
                ""
            ),

        "yolo_device":
            yolo.get(
                "device",
                ""
            ),

        "yolo_frames_processed":
            yolo.get(
                "frames_processed",
                ""
            ),

        "yolo_effective_fps":
            yolo.get(
                "effective_fps",
                ""
            ),

        "yolo_inference_mean_ms":
            yolo.get(
                "mean_wall_inference_ms",
                ""
            ),

        "yolo_inference_p95_ms":
            yolo.get(
                "p95_wall_inference_ms",
                ""
            ),
    }

    row_file = (
        exp /
        "summary_row.csv"
    )

    with row_file.open(
        "w",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(row.keys())
        )

        writer.writeheader()
        writer.writerow(row)

    # ------------------------------------------------
    # Finish
    # ------------------------------------------------

    print()
    print("=" * 65)
    print("EXPERIMENT FINALIZATION COMPLETE")
    print("=" * 65)
    print(f"Folder : {exp}")
    print(f"Summary: {summary_file}")
    print(f"CSV row: {row_file}")
    print(f"Plots  : {plots}")
    print()
    print(
        f"APE Translation RMSE : "
        f"{ape_t.get('rmse', float('nan')):.6f} m"
    )
    print(
        f"APE Yaw RMSE         : "
        f"{ape_y.get('rmse', float('nan')):.6f} deg"
    )
    print(
        f"RPE Translation RMSE : "
        f"{rpe_t.get('rmse', float('nan')):.6f} m"
    )
    print(
        f"RPE Yaw RMSE         : "
        f"{rpe_y.get('rmse', float('nan')):.6f} deg"
    )
    print("=" * 65)


if __name__ == "__main__":
    main()

# ===== BEGIN YOLO OVERLAP POSTHOOK =====

def _run_yolo_overlap_posthook():
    import subprocess
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        return

    configuration = str(sys.argv[1]).strip()
    experiment_raw = str(sys.argv[2]).strip()

    if configuration not in {
        "cartographer_yolo",
        "rtab_yolo",
    }:
        return

    try:
        experiment = int(experiment_raw)
    except ValueError:
        return

    root = Path.home() / "turtlebot3_ws"

    exp_dir = (
        root /
        "metrics" /
        "experiments" /
        configuration /
        f"experiment_{experiment:02d}"
    )

    helper = (
        root /
        "tools" /
        "yolo_overlap_finalize.py"
    )

    print()
    print("=" * 65)
    print("RUNNING YOLO / CAMERA OVERLAP POST-PROCESSING")
    print("=" * 65)

    if not helper.is_file() or not exp_dir.is_dir():
        print(
            "YOLO overlap analysis FAILED: helper or experiment "
            "directory is missing.",
            file=sys.stderr,
        )
        print(f"Helper: {helper}", file=sys.stderr)
        print(f"Experiment: {exp_dir}", file=sys.stderr)
        print(
            "Previously saved main-analysis outputs remain available.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    result = subprocess.run(
        [
            sys.executable,
            str(helper),
            str(exp_dir),
        ],
        check=False,
    )

    if result.returncode != 0:
        print(
            "YOLO overlap analysis FAILED. Main-analysis outputs "
            "were already saved, but finalization is incomplete.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("=" * 65)
    print("YOLO OVERLAP POST-PROCESSING COMPLETE")
    print("=" * 65)


if __name__ == "__main__":
    _run_yolo_overlap_posthook()

# ===== END YOLO OVERLAP POSTHOOK =====
