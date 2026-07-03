#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from tf2_ros import Buffer, TransformListener

class SlamPoseLogger(Node):
    def __init__(self):
        super().__init__('slam_pose_logger')

        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('rate_hz', 10.0)
        self.declare_parameter('outfile', '/tmp/slam_tum.txt')

        self.base = self.get_parameter('base_frame').get_parameter_value().string_value
        self.mapf = self.get_parameter('map_frame').get_parameter_value().string_value
        self.rate = self.get_parameter('rate_hz').get_parameter_value().double_value
        self.outfile = self.get_parameter('outfile').get_parameter_value().string_value

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.f = open(self.outfile, 'w')
        self.get_logger().info(
            f'Logging SLAM (TF) {self.mapf} -> {self.base} to {self.outfile} @ {self.rate} Hz'
        )

        self.timer = self.create_timer(1.0 / self.rate, self.tick)
        self._warned = False

    def tick(self):
        try:
            # IMPORTANT: use ROS_TIME when use_sim_time=true
            t = rclpy.time.Time(clock_type=self.get_clock().clock_type)

            # wait briefly for TF to be available (reduces Extrapolation spam)
            if not self.tf_buffer.can_transform(self.mapf, self.base, t, timeout=Duration(seconds=0.2)):
                if not self._warned:
                    self.get_logger().warn(
                        f"TF not available yet for {self.mapf} -> {self.base}. Waiting..."
                    )
                    self._warned = True
                return

            tfm = self.tf_buffer.lookup_transform(self.mapf, self.base, t)

            stamp = tfm.header.stamp
            ts = float(stamp.sec) + float(stamp.nanosec) * 1e-9

            tr = tfm.transform.translation
            q  = tfm.transform.rotation

            self.f.write(
                f"{ts:.9f} {tr.x:.6f} {tr.y:.6f} {tr.z:.6f} "
                f"{q.x:.8f} {q.y:.8f} {q.z:.8f} {q.w:.8f}\n"
            )
            self.f.flush()
            self._warned = False

        except Exception as e:
            if not self._warned:
                self.get_logger().warn(
                    f"TF lookup failed for {self.mapf} -> {self.base}. ({type(e).__name__})"
                )
                self._warned = True

    def destroy_node(self):
        try:
            self.f.flush()
            self.f.close()
        except Exception:
            pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = SlamPoseLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
