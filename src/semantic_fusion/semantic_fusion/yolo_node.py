#!/usr/bin/env python3

import csv
import json
import time
from pathlib import Path

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
from ultralytics import YOLO
import torch


class YoloNode(Node):

    def __init__(self):
        super().__init__('yolo_node')

        self.declare_parameter('device', 'cpu')
        self.declare_parameter('display', False)
        self.declare_parameter('metrics_file', '')

        self.device = str(
            self.get_parameter('device').value
        )

        self.display = bool(
            self.get_parameter('display').value
        )

        self.metrics_file = str(
            self.get_parameter('metrics_file').value
        )

        self.weights_path = (
            Path.home() / "turtlebot3_ws/yolov8n.pt"
        )
        if not self.weights_path.is_file():
            raise FileNotFoundError(self.weights_path)

        if self.device != "cpu":
            raise ValueError("This experiment protocol requires device=cpu")

        self.predict_settings = {
            "imgsz": 640,
            "conf": 0.25,
            "iou": 0.7,
            "max_det": 300,
            "device": "cpu",
            "half": False,
            "rect": True,
            "augment": False,
            "agnostic_nms": False,
            "classes": None,
            "verbose": False,
        }
        self.model = YOLO(str(self.weights_path))
        self.bridge = CvBridge()

        self.frame_count = 0
        self.first_wall = None
        self.last_wall = None
        self.last_source_stamp = None

        self.inference_times = []
        self.callback_times = []

        self.csv_file = None
        self.csv_writer = None

        if self.metrics_file:
            path = Path(self.metrics_file)
            path.parent.mkdir(parents=True, exist_ok=True)

            import hashlib
            import importlib.metadata

            metadata = {
                "weights_path": str(self.weights_path.resolve()),
                "weights_sha256": hashlib.sha256(
                    self.weights_path.read_bytes()
                ).hexdigest(),
                "ultralytics_version": importlib.metadata.version("ultralytics"),
                "torch_version": torch.__version__,
                "predict_settings": self.predict_settings,
                "input_topic": "/camera/image_raw",
                "subscription_depth": 10,
                "display": self.display,
                "timing_clock": "time.perf_counter",
                "warmup_policy": "All completed frames logged, including startup",
            }
            path.with_name(path.stem + "_config.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )

            self.csv_file = open(
                path,
                'w',
                newline='',
                buffering=1
            )

            self.csv_writer = csv.writer(self.csv_file)

            self.csv_writer.writerow([
                'frame_index',
                'source_stamp_s',
                'source_dt_ms',
                'wall_inference_ms',
                'ultralytics_preprocess_ms',
                'ultralytics_inference_ms',
                'ultralytics_postprocess_ms',
                'total_callback_ms',
                'boxes',
                'device',
                'callback_start_wall_s',
                'callback_end_wall_s'
            ])

        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )

        self.publisher = self.create_publisher(
            String,
            '/yolo/detections',
            10
        )

        self.get_logger().info(
            f"YOLO started | model=yolov8n | "
            f"device={self.device} | "
            f"CUDA available={torch.cuda.is_available()} | "
            f"display={self.display}"
        )

    def image_callback(self, msg):

        callback_start = time.perf_counter()

        source_stamp = (
            msg.header.stamp.sec +
            msg.header.stamp.nanosec * 1e-9
        )

        if self.last_source_stamp is None:
            source_dt_ms = ''
        else:
            source_dt_ms = (
                source_stamp - self.last_source_stamp
            ) * 1000.0

        self.last_source_stamp = source_stamp

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding='bgr8'
        )

        infer_start = time.perf_counter()

        results = self.model.predict(
            source=frame,
            **self.predict_settings
        )

        infer_end = time.perf_counter()

        wall_inference_ms = (
            infer_end - infer_start
        ) * 1000.0

        result = results[0]

        speed = result.speed or {}

        preprocess_ms = float(
            speed.get('preprocess', 0.0)
        )

        model_inference_ms = float(
            speed.get('inference', 0.0)
        )

        postprocess_ms = float(
            speed.get('postprocess', 0.0)
        )

        num_boxes = len(result.boxes)

        detections = []

        for box in result.boxes:

            cls_id = int(box.cls[0])
            class_name = self.model.names[cls_id]

            xmin, ymin, xmax, ymax = \
                box.xyxy[0].tolist()

            confidence = float(box.conf[0])

            detections.append({
                "class": class_name,
                "confidence": confidence,
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax
            })

            if self.display:

                cv2.rectangle(
                    frame,
                    (int(xmin), int(ymin)),
                    (int(xmax), int(ymax)),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"{class_name} {confidence:.2f}",
                    (int(xmin), int(ymin) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        msg_out = String()
        msg_out.data = json.dumps(detections)
        self.publisher.publish(msg_out)

        if self.display:
            cv2.imshow("YOLOv8 Detection", frame)
            cv2.waitKey(1)

        callback_end = time.perf_counter()

        total_callback_ms = (
            callback_end - callback_start
        ) * 1000.0

        self.last_wall = callback_end
        self.frame_count += 1

        if self.first_wall is None:
            self.first_wall = callback_start

        self.inference_times.append(
            wall_inference_ms
        )

        self.callback_times.append(
            total_callback_ms
        )

        if self.csv_writer is not None:

            self.csv_writer.writerow([
                self.frame_count,
                f"{source_stamp:.9f}",
                source_dt_ms,
                wall_inference_ms,
                preprocess_ms,
                model_inference_ms,
                postprocess_ms,
                total_callback_ms,
                num_boxes,
                self.device,
                f"{callback_start:.9f}",
                f"{callback_end:.9f}"
            ])

    @staticmethod
    def percentile(values, p):

        if not values:
            return float('nan')

        values = sorted(values)

        k = (len(values) - 1) * p / 100.0

        f = int(k)
        c = min(f + 1, len(values) - 1)

        if f == c:
            return values[f]

        return (
            values[f] * (c - k) +
            values[c] * (k - f)
        )

    def write_summary(self):

        if not self.inference_times:
            return

        elapsed = (
            self.last_wall - self.first_wall
        )

        effective_fps = (
            self.frame_count / elapsed
            if elapsed > 0 else 0.0
        )

        mean_inf = (
            sum(self.inference_times) /
            len(self.inference_times)
        )

        mean_cb = (
            sum(self.callback_times) /
            len(self.callback_times)
        )

        summary = [
            f"model: yolov8n",
            f"device: {self.device}",
            f"torch_cuda_available: {torch.cuda.is_available()}",
            f"frames_processed: {self.frame_count}",
            f"elapsed_wall_s: {elapsed:.6f}",
            f"effective_fps: {effective_fps:.6f}",
            f"mean_wall_inference_ms: {mean_inf:.6f}",
            f"median_wall_inference_ms: "
            f"{self.percentile(self.inference_times, 50):.6f}",
            f"p95_wall_inference_ms: "
            f"{self.percentile(self.inference_times, 95):.6f}",
            f"p99_wall_inference_ms: "
            f"{self.percentile(self.inference_times, 99):.6f}",
            f"max_wall_inference_ms: "
            f"{max(self.inference_times):.6f}",
            f"mean_callback_ms: {mean_cb:.6f}",
        ]

        text = "\n".join(summary)

        if rclpy.ok():
            self.get_logger().info(
                "\nYOLO PERFORMANCE SUMMARY\n" + text
            )
        else:
            print("\nYOLO PERFORMANCE SUMMARY\n" + text, flush=True)

        if self.metrics_file:

            summary_path = Path(
                self.metrics_file
            ).with_name(
                Path(self.metrics_file).stem +
                "_summary.txt"
            )

            summary_path.write_text(
                text + "\n"
            )

    def close_metrics(self):

        self.write_summary()

        if self.csv_file is not None:
            self.csv_file.close()


def main(args=None):

    rclpy.init(args=args)

    node = YoloNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:

        node.close_metrics()

        if node.display:
            cv2.destroyAllWindows()

        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
