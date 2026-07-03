import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2

class SemanticFusionNode(Node):
    def __init__(self):
        super().__init__('fusion_node')

        self.get_logger().info("Semantic Fusion Node Started 🚀")

        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.rgb_callback,
            10
        )

        self.depth_sub = self.create_subscription(
            Image,
            '/camera/image_raw/compressedDepth',
            self.depth_callback,
            10
        )

        self.yolo_sub = self.create_subscription(
            String,
            '/yolo/detections',
            self.yolo_callback,
            10
        )

        # Bridge for ROS image -> OpenCV
        self.bridge = CvBridge()

        # Store latest images and detections
        self.latest_rgb = None
        self.latest_depth = None
        self.latest_detections = []

    def rgb_callback(self, msg):
        try:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
            self.get_logger().info("RGB Image received")
        except Exception as e:
            self.get_logger().error(f"Failed to convert RGB image: {e}")

        # Optionally, you can run fusion here if depth is available
        self.try_fusion()

    def depth_callback(self, msg):
        try:
            self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            self.get_logger().info("Depth Image received ✅")
        except Exception as e:
            self.get_logger().warn(f"Depth image not ready yet: {e}")

        self.try_fusion()

    def yolo_callback(self, msg):
        # YOLO detections are received as stringified JSON
        import json
        try:
            self.latest_detections = json.loads(msg.data)
            self.get_logger().info(f"YOLO Detections received: {len(self.latest_detections)} boxes")
        except Exception as e:
            self.get_logger().error(f"Failed to parse YOLO detections: {e}")

        self.try_fusion()

    def try_fusion(self):
        # Check if we have RGB and detections
        if self.latest_rgb is None or not self.latest_detections:
            return

        # Depth optional
        if self.latest_depth is None:
            self.get_logger().warn("Depth data not available yet, running RGB-only processing")

        # --- PLACEHOLDER: your fusion logic here ---
        # You can process self.latest_rgb + self.latest_depth (if available) + self.latest_detections

        # Example: just show RGB with YOLO boxes
        rgb_copy = self.latest_rgb.copy()
        for det in self.latest_detections:
            x1 = int(det['xmin'])
            y1 = int(det['ymin'])
            x2 = int(det['xmax'])
            y2 = int(det['ymax'])
            cls = det['class']
            cv2.rectangle(rgb_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(rgb_copy, cls, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

        cv2.imshow("Fusion Preview", rgb_copy)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = SemanticFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
