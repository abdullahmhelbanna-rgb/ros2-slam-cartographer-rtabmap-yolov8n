import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
import json
import math

class SemanticScanFilter(Node):

    def __init__(self):
        super().__init__('semantic_scan_filter')

        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10)

        self.det_sub = self.create_subscription(
            String,
            '/yolo/detections',
            self.detection_callback,
            10)

        self.scan_pub = self.create_publisher(
            LaserScan,
            '/scan_filtered',
            10)

        self.latest_detections = []
        self.image_width = 640
        self.fov_deg = 62.0

        self.get_logger().info("Semantic Scan Filter Started 🚀")

    def detection_callback(self, msg):
        try:
            self.latest_detections = json.loads(msg.data)
        except:
            self.latest_detections = []

    def scan_callback(self, scan_msg):

        filtered_scan = LaserScan()
        filtered_scan = scan_msg

        ranges = list(scan_msg.ranges)

        for det in self.latest_detections:

            if det["class"] == "person":  # عدل لو عايز كلاس تاني

                xmin = det["xmin"]
                xmax = det["xmax"]

                x_center = (xmin + xmax) / 2.0

                angle_deg = (x_center - self.image_width/2) * (self.fov_deg / self.image_width)
                angle_rad = math.radians(angle_deg)

                index = int((angle_rad - scan_msg.angle_min) / scan_msg.angle_increment)

                sector_width = 5  # عدد نقاط يمين وشمال

                for i in range(index - sector_width, index + sector_width):
                    if 0 <= i < len(ranges):
                        ranges[i] = float('inf')

        filtered_scan.ranges = ranges
        self.scan_pub.publish(filtered_scan)


def main(args=None):
    rclpy.init(args=args)
    node = SemanticScanFilter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
