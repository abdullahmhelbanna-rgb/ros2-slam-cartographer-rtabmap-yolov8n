#!/usr/bin/env python3

import argparse
import csv
import statistics
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo


def stamp_sec(msg):
    return (
        msg.header.stamp.sec +
        msg.header.stamp.nanosec * 1e-9
    )


def percentile(values, p):
    if not values:
        return float("nan")

    v = sorted(values)
    k = (len(v) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)

    if lo == hi:
        return v[lo]

    return v[lo] * (hi-k) + v[hi] * (k-lo)


class CameraMonitor(Node):

    def __init__(self, outdir):
        super().__init__("camera_rate_monitor")

        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)

        self.stamps = []

        self.f = open(
            self.outdir / "camera_rate_events.csv",
            "w",
            newline="",
            buffering=1
        )

        self.writer = csv.writer(self.f)

        self.writer.writerow([
            "camera_source_stamp_s"
        ])

        self.create_subscription(
            CameraInfo,
            "/camera/camera_info",
            self.callback,
            qos_profile_sensor_data
        )

        self.get_logger().info(
            "Camera rate monitor started"
        )

    def callback(self, msg):
        t = stamp_sec(msg)

        self.stamps.append(t)

        self.writer.writerow([t])

    def finish(self):
        lines = [
            f"camera_messages: {len(self.stamps)}"
        ]

        if len(self.stamps) >= 2:

            dts = [
                b-a
                for a, b in zip(
                    self.stamps[:-1],
                    self.stamps[1:]
                )
                if b > a
            ]

            duration = (
                self.stamps[-1] -
                self.stamps[0]
            )

            rate = (
                (len(self.stamps)-1) /
                duration
                if duration > 0
                else float("nan")
            )

            median_dt = statistics.median(dts)

            gap_threshold = 1.5 * median_dt

            gap_events = sum(
                dt > gap_threshold
                for dt in dts
            )

            skipped = 0

            for dt in dts:
                if dt > gap_threshold:
                    skipped += max(
                        0,
                        round(dt / median_dt)-1
                    )

            lines += [
                f"camera_duration_s: {duration:.6f}",
                f"camera_rate_hz: {rate:.6f}",
                f"camera_median_period_ms: "
                f"{median_dt*1000:.6f}",
                f"camera_p95_period_ms: "
                f"{percentile(dts,95)*1000:.6f}",
                f"camera_max_gap_ms: "
                f"{max(dts)*1000:.6f}",
                f"camera_gap_events: {gap_events}",
                f"camera_estimated_skipped_intervals: "
                f"{skipped}",
            ]

        lines.append(
            "NOTE: rate is measured from CameraInfo. "
            "A validation recording confirmed one-to-one "
            "publication with /camera/image_raw."
        )

        text = "\n".join(lines)

        (
            self.outdir /
            "camera_rate_summary.txt"
        ).write_text(text + "\n")

        print()
        print("===== CAMERA RATE SUMMARY =====")
        print(text)
        print("===============================")

        self.f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rclpy.init()

    node = CameraMonitor(args.out)

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.finish()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
