from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([

        # RTAB-Map SLAM
        #
        # Official experimental configuration:
        # - External encoder odometry: /odom
        # - 2D LiDAR: /scan
        # - RGB appearance input: /camera/image_raw
        # - Camera calibration: /camera/camera_info
        # - No depth input
        # - No IMU input
        #
        # RGB is used by RTAB-Map for visual appearance information
        # and loop-closure detection, while LiDAR ICP is used for
        # geometric registration.

        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            name='rtabmap',
            output='screen',

            parameters=[{
                'use_sim_time': True,

                # Frames
                'frame_id': 'base_footprint',
                'map_frame_id': 'map',

                # Empty -> use nav_msgs/Odometry topic /odom
                # instead of obtaining odometry from TF.
                'odom_frame_id': '',

                'publish_tf': True,

                # Inputs
                'subscribe_odom': True,
                'subscribe_scan': True,

                # Enable RGB appearance information
                'subscribe_rgb': True,

                # No depth camera in this controlled setup
                'subscribe_depth': False,
                'subscribe_rgbd': False,

                # Synchronization
                'approx_sync': True,

                # Fresh database for every experiment
                'delete_db_on_start': True,

                # Planar robot motion
                'Reg/Force3DoF': 'true',

                # Geometric registration:
                # 0=Vis, 1=ICP, 2=Vis+ICP
                #
                # We intentionally use ICP for metric geometric
                # registration while RGB remains available for
                # RTAB-Map appearance-based loop-closure processing.
                'Reg/Strategy': '1',

                # ICP implementation:
                # 1 = libpointmatcher in this RTAB-Map build
                'Icp/Strategy': '1',

                # Graph optimization
                'Optimizer/Strategy': '1',

                # Explicitly construct occupancy grid from LiDAR,
                # not from depth.
                'Grid/FromDepth': 'false',
            }],

            remappings=[
                ('scan', '/scan'),
                ('odom', '/odom'),

                # RGB camera
                ('rgb/image', '/camera/image_raw'),
                ('rgb/camera_info', '/camera/camera_info'),

                # Prevent IMU measurements from entering
                # this controlled comparison.
                ('imu', '/rtabmap_unused_imu'),
                ('/imu', '/rtabmap_unused_imu'),
            ]
        ),
    ])
