#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry

class OdomToTUM(Node):
    def __init__(self):
        super().__init__('odom_to_tum_logger')
        self.declare_parameter('topic', '/ground_truth/odom')
        self.declare_parameter('outfile', '/tmp/gt_gazebo_tum.txt')

        self.topic = self.get_parameter('topic').get_parameter_value().string_value
        self.outfile = self.get_parameter('outfile').get_parameter_value().string_value

        self.f = open(self.outfile, 'w')
        self.sub = self.create_subscription(Odometry, self.topic, self.cb, 100)
        self.get_logger().info(f"Logging {self.topic} -> {self.outfile}")

    def cb(self, msg: Odometry):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        # TUM: t x y z qx qy qz qw
        self.f.write(f"{t:.9f} {p.x:.6f} {p.y:.6f} {p.z:.6f} {q.x:.8f} {q.y:.8f} {q.z:.8f} {q.w:.8f}\n")
        self.f.flush()

def main(args=None):
    rclpy.init(args=args)
    node = OdomToTUM()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.f.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
