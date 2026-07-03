#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
from ultralytics import YOLO
import cv2
import json


class YoloNode(Node):

    def __init__(self):
        super().__init__('yolo_node')

        # تحميل موديل YOLOv8
        self.model = YOLO("yolov8n.pt")

        self.bridge = CvBridge()

        # الاشتراك في الكاميرا
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10)

        # نشر النتائج
        self.publisher = self.create_publisher(
            String,
            '/yolo/detections',
            10)

        self.get_logger().info("YOLO Node Started 🚀")

    def image_callback(self, msg):

        # 👇 نتأكد إن الصور بتوصل
        self.get_logger().info("Image received")

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        # 👇 نقلل confidence عشان نختبر detection
        results = self.model(frame, conf=0.25)

        # 👇 نعرف YOLO شايف كام object
        num_boxes = len(results[0].boxes)
        self.get_logger().info(f"Boxes found: {num_boxes}")

        detections = []

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            class_name = self.model.names[cls_id]

            xmin, ymin, xmax, ymax = box.xyxy[0].tolist()
            confidence = float(box.conf[0])

            detections.append({
                "class": class_name,
                "confidence": confidence,
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax
            })

            # رسم البوكس للعرض
            cv2.rectangle(frame,
                          (int(xmin), int(ymin)),
                          (int(xmax), int(ymax)),
                          (0, 255, 0),
                          2)

            cv2.putText(frame,
                        f"{class_name} {confidence:.2f}",
                        (int(xmin), int(ymin)-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2)

        # نشر النتائج
        msg_out = String()
        msg_out.data = json.dumps(detections)
        self.publisher.publish(msg_out)

        # نافذة Debug
        cv2.imshow("YOLOv8 Detection", frame)
        cv2.waitKey(1)


def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
