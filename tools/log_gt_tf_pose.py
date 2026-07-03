#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

CANDIDATE_WORLDS = ["world", "map", "odom"]

class GtTfLogger(Node):
    def __init__(self):
        super().__init__('gt_tf_logger')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('world_frame', '')          
        self.declare_parameter('rate_hz', 10.0)
        self.declare_parameter('outfile', '/tmp/gt_tum.txt')

        self.base  = self.get_parameter('base_frame').get_parameter_value().string_value
        self.world = self.get_parameter('world_frame').get_parameter_value().string_value
        self.rate  = self.get_parameter('rate_hz').get_parameter_value().double_value
        self.out   = self.get_parameter('outfile').get_parameter_value().string_value

        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.f = open(self.out, 'w')

        world_text = self.world if self.world else "<?>"
        self.get_logger().info(f'Logging GT (TF) {world_text} -> {self.base} to {self.out}')
        self.timer = self.create_timer(1.0 / self.rate, self.tick)

    def tick(self):
        if not self.world:
            for w in CANDIDATE_WORLDS:
                try:
                    self.buf.lookup_transform(w, self.base, rclpy.time.Time())
                    self.world = w
                    self.get_logger().info(f'Auto-detected world frame: {self.world}')
                    break
                except Exception:
                    pass
            if not self.world:
                return

        try:
            t = self.buf.lookup_transform(self.world, self.base, rclpy.time.Time())
            ts = self.get_clock().now().nanoseconds * 1e-9
            tr = t.transform.translation
            q  = t.transform.rotation
            self.f.write(f"{ts:.9f} {tr.x:.6f} {tr.y:.6f} {tr.z:.6f} "
                         f"{q.x:.6f} {q.y:.6f} {q.z:.6f} {q.w:.6f}\n")
            self.f.flush()
        except Exception:
            pass

    def destroy_node(self):
        try:
            self.f.flush(); self.f.close()
        except:
            pass
        super().destroy_node()

def main():
    rclpy.init()
    node = GtTfLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
