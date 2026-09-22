#!/usr/bin/env python3

import csv
import statistics
import sys
import time
from collections import deque
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data

from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan, CameraInfo
from tf2_msgs.msg import TFMessage


def stamp_to_sec(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


def percentile(values, p):
    if not values:
        return float("nan")

    v = sorted(values)
    k = (len(v) - 1) * p / 100.0

    lo = int(k)
    hi = min(lo + 1, len(v) - 1)

    if lo == hi:
        return v[lo]

    return (
        v[lo] * (hi - k)
        + v[hi] * (k - lo)
    )


class ExperimentMonitor(Node):

    def __init__(self, outdir):
        super().__init__("experiment_monitor")
        self.cb_group = ReentrantCallbackGroup()

        self.set_parameters([
            Parameter(
                "use_sim_time",
                Parameter.Type.BOOL,
                True
            )
        ])

        self.outdir = Path(outdir)
        self.outdir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.scan_stamps = []
        self.camera_stamps = []
        self.tf_stamps = []

        self.scan_history = deque(maxlen=5000)
        self.tf_latencies_ms = []

        self.first_clock_sim = None
        self.first_clock_wall = None
        self.last_clock_sim = None
        self.last_clock_wall = None
        self.rtf_values = []

        self.last_tf_key = None

        self.scan_file = open(
            self.outdir / "scan_events.csv",
            "w",
            newline="",
            buffering=1,
        )

        self.camera_file = open(
            self.outdir / "camera_events.csv",
            "w",
            newline="",
            buffering=1,
        )

        self.tf_file = open(
            self.outdir / "tf_events.csv",
            "w",
            newline="",
            buffering=1,
        )

        self.rtf_file = open(
            self.outdir / "rtf_samples.csv",
            "w",
            newline="",
            buffering=1,
        )

        self.scan_writer = csv.writer(self.scan_file)
        self.camera_writer = csv.writer(self.camera_file)
        self.tf_writer = csv.writer(self.tf_file)
        self.rtf_writer = csv.writer(self.rtf_file)

        self.scan_writer.writerow([
            "source_stamp_s",
            "receive_wall_s",
        ])

        self.camera_writer.writerow([
            "source_stamp_s",
            "receive_wall_s",
        ])

        self.tf_writer.writerow([
            "parent",
            "child",
            "tf_stamp_s",
            "receive_wall_s",
            "associated_scan_stamp_s",
            "scan_to_tf_wall_latency_ms",
        ])

        self.rtf_writer.writerow([
            "sim_time_s",
            "wall_time_s",
            "instant_rtf",
        ])

        self.create_subscription(
            Clock,
            "/clock",
            self.clock_callback,
            qos_profile_sensor_data,
            callback_group=self.cb_group,
        )

        self.create_subscription(
            LaserScan,
            "/scan",
            self.scan_callback,
            qos_profile_sensor_data,
            callback_group=self.cb_group,
        )

        # CameraInfo is used as a low-overhead proxy for the
        # synchronized camera publication stream.
        self.create_subscription(
            CameraInfo,
            "/camera/camera_info",
            self.camera_callback,
            qos_profile_sensor_data,
            callback_group=self.cb_group,
        )

        self.create_subscription(
            TFMessage,
            "/tf",
            self.tf_callback,
            100,
            callback_group=self.cb_group,
        )

        self.get_logger().info(
            f"Experiment monitor started: {self.outdir}"
        )

    def clock_callback(self, msg):
        sim = stamp_to_sec(msg.clock)
        wall = time.perf_counter()

        if self.first_clock_sim is None:
            self.first_clock_sim = sim
            self.first_clock_wall = wall

        if (
            self.last_clock_sim is not None
            and self.last_clock_wall is not None
        ):
            ds = sim - self.last_clock_sim
            dw = wall - self.last_clock_wall

            if ds > 0.0 and dw > 0.0:
                rtf = ds / dw

                self.rtf_values.append(rtf)

                self.rtf_writer.writerow([
                    sim,
                    wall,
                    rtf,
                ])

        self.last_clock_sim = sim
        self.last_clock_wall = wall

    def scan_callback(self, msg):
        stamp = stamp_to_sec(msg.header.stamp)
        wall = time.perf_counter()

        self.scan_stamps.append(stamp)
        self.scan_history.append((stamp, wall))

        self.scan_writer.writerow([
            stamp,
            wall,
        ])

    def camera_callback(self, msg):
        stamp = stamp_to_sec(msg.header.stamp)
        wall = time.perf_counter()

        self.camera_stamps.append(stamp)

        self.camera_writer.writerow([
            stamp,
            wall,
        ])

    def tf_callback(self, msg):
        receive_wall = time.perf_counter()

        for tr in msg.transforms:
            parent = tr.header.frame_id.lstrip("/")
            child = tr.child_frame_id.lstrip("/")

            # Global SLAM output only
            if parent != "map":
                continue

            stamp = stamp_to_sec(tr.header.stamp)

            key = (
                parent,
                child,
                round(stamp, 9),
            )

            if key == self.last_tf_key:
                continue

            self.last_tf_key = key
            self.tf_stamps.append(stamp)

            associated_scan_stamp = ""
            latency_ms = ""

            # Select most recent LiDAR message whose source
            # timestamp is not newer than this TF timestamp.
            for scan_stamp, scan_wall in reversed(
                self.scan_history
            ):
                if scan_stamp <= stamp + 1e-6:
                    associated_scan_stamp = scan_stamp

                    latency = (
                        receive_wall - scan_wall
                    ) * 1000.0

                    if latency >= 0.0:
                        latency_ms = latency
                        self.tf_latencies_ms.append(
                            latency
                        )

                    break

            self.tf_writer.writerow([
                parent,
                child,
                stamp,
                receive_wall,
                associated_scan_stamp,
                latency_ms,
            ])

    def stream_summary(self, prefix, stamps):
        if len(stamps) < 2:
            return [
                f"{prefix}_messages: {len(stamps)}"
            ]

        dts = [
            b - a
            for a, b in zip(
                stamps[:-1],
                stamps[1:]
            )
            if b > a
        ]

        duration = stamps[-1] - stamps[0]

        rate = (
            (len(stamps) - 1) / duration
            if duration > 0
            else float("nan")
        )

        if not dts:
            return [
                f"{prefix}_messages: {len(stamps)}",
                f"{prefix}_duration_s: {duration:.6f}",
            ]

        median_dt = statistics.median(dts)

        gap_threshold = 1.5 * median_dt

        gap_events = sum(
            1
            for dt in dts
            if dt > gap_threshold
        )

        skipped_intervals = 0

        for dt in dts:
            if dt > gap_threshold:
                skipped_intervals += max(
                    0,
                    round(dt / median_dt) - 1
                )

        std_ms = (
            statistics.stdev(dts) * 1000.0
            if len(dts) > 1
            else 0.0
        )

        return [
            f"{prefix}_messages: {len(stamps)}",
            f"{prefix}_duration_s: {duration:.6f}",
            f"{prefix}_rate_hz: {rate:.6f}",
            f"{prefix}_median_period_ms: "
            f"{median_dt * 1000.0:.6f}",
            f"{prefix}_period_std_ms: "
            f"{std_ms:.6f}",
            f"{prefix}_p95_period_ms: "
            f"{percentile(dts,95) * 1000.0:.6f}",
            f"{prefix}_max_gap_ms: "
            f"{max(dts) * 1000.0:.6f}",
            f"{prefix}_gap_events: {gap_events}",
            f"{prefix}_estimated_skipped_intervals: "
            f"{skipped_intervals}",
        ]

    def finish(self):
        lines = []

        lines += self.stream_summary(
            "lidar",
            self.scan_stamps
        )

        lines.append("")

        lines += self.stream_summary(
            "camera",
            self.camera_stamps
        )

        lines.append("")

        lines += self.stream_summary(
            "slam_tf",
            self.tf_stamps
        )

        lines.append("")

        lines.append(
            f"slam_tf_latency_samples: "
            f"{len(self.tf_latencies_ms)}"
        )

        if self.tf_latencies_ms:
            lines += [
                f"slam_tf_latency_mean_ms: "
                f"{statistics.mean(self.tf_latencies_ms):.6f}",

                f"slam_tf_latency_median_ms: "
                f"{statistics.median(self.tf_latencies_ms):.6f}",

                f"slam_tf_latency_p95_ms: "
                f"{percentile(self.tf_latencies_ms,95):.6f}",

                f"slam_tf_latency_max_ms: "
                f"{max(self.tf_latencies_ms):.6f}",
            ]

        lines.append("")

        lines.append(
            f"clock_rtf_samples: "
            f"{len(self.rtf_values)}"
        )

        if (
            self.first_clock_sim is not None
            and self.last_clock_sim is not None
            and self.first_clock_wall is not None
            and self.last_clock_wall is not None
        ):
            ds = (
                self.last_clock_sim
                - self.first_clock_sim
            )

            dw = (
                self.last_clock_wall
                - self.first_clock_wall
            )

            if ds >= 0.0 and dw > 0.0:
                lines.append(
                    f"gazebo_rtf_overall: "
                    f"{ds / dw:.6f}"
                )

        if self.rtf_values:
            lines += [
                f"gazebo_rtf_mean: "
                f"{statistics.mean(self.rtf_values):.6f}",

                f"gazebo_rtf_median: "
                f"{statistics.median(self.rtf_values):.6f}",

                f"gazebo_rtf_p05: "
                f"{percentile(self.rtf_values,5):.6f}",

                f"gazebo_rtf_p95: "
                f"{percentile(self.rtf_values,95):.6f}",
            ]

        lines.append("")
        lines.append(
            "NOTE: estimated_skipped_intervals is inferred "
            "from timestamp gaps relative to the median period; "
            "it is not a DDS packet-loss counter."
        )

        lines.append(
            "NOTE: slam_tf_latency is an observed LiDAR-receipt "
            "to global-TF-receipt wall-time latency proxy, not "
            "internal SLAM compute time."
        )

        summary = "\n".join(lines)

        (
            self.outdir /
            "monitor_summary.txt"
        ).write_text(summary + "\n")

        print()
        print("===== EXPERIMENT MONITOR SUMMARY =====")
        print(summary)
        print("======================================")

        self.scan_file.close()
        self.camera_file.close()
        self.tf_file.close()
        self.rtf_file.close()


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: experiment_monitor.py "
            "<output_directory>"
        )
        raise SystemExit(1)

    rclpy.init()

    node = ExperimentMonitor(sys.argv[1])

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()

    except KeyboardInterrupt:
        pass

    finally:
        executor.shutdown()
        node.finish()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
