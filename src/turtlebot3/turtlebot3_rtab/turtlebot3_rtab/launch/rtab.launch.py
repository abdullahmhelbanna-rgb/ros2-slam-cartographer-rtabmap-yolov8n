from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([

        # ICP Odometry (LaserScan -> TF odom_icp -> base_footprint + topic /odom_icp)
        Node(
            package='rtabmap_odom',
            executable='icp_odometry',
            name='icp_odom',
            output='screen',
            parameters=[{
                'use_sim_time': True,

                # frames
                'frame_id': 'base_footprint',
                'odom_frame_id': 'odom_icp',
                'publish_tf': True,

                # input
                'subscribe_scan': True,

                # NOTE: RTABMap "slash params" are strings in Humble
                'Icp/Force4DoF': 'true',
                'Icp/Strategy': '1',
                'Icp/RangeMin': '0.12',
                'Icp/RangeMax': '3.5',
                'Icp/VoxelSize': '0.05',
                'Icp/MaxCorrespondenceDistance': '0.5',
            }],
            remappings=[
                ('scan', '/scan'),
                ('odom', '/odom_icp'),   # publish nav_msgs/Odometry on /odom_icp
            ]
        ),

        # RTAB-Map SLAM (uses ICP odom)
        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            name='rtabmap',
            output='screen',
            parameters=[{
                'use_sim_time': True,

                # frames
                'frame_id': 'base_footprint',
                'map_frame_id': 'map',
                'odom_frame_id': 'odom_icp',
                'publish_tf': True,

                # inputs
                'subscribe_scan': True,
                'subscribe_odom': True,
                'subscribe_rgb': False,
                'subscribe_depth': False,

                # delete db each start (optional, since you pass delete_db_on_start:=true)
                'delete_db_on_start': True,

                # RTABMap "slash params" as strings
                'Reg/Force3DoF': 'true',
                'Reg/Strategy': '1',
                'Icp/Strategy': '1',
                'Optimizer/Strategy': '1',
            }],
            remappings=[
                ('scan', '/scan'),
                ('odom', '/odom_icp'),
            ]
        ),

        Node(
            package='rtabmap_viz',
            executable='rtabmap_viz',
            name='rtabmapviz',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'frame_id': 'base_footprint',
                'map_frame_id': 'map',
                'odom_frame_id': 'odom_icp',
            }]
        ),
    ])
