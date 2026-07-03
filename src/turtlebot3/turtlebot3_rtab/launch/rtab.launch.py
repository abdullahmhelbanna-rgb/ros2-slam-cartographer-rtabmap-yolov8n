from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([

        Node(
            package='rtabmap_slam',   
            executable='rtabmap',     
            name='rtabmap',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'frame_id': 'base_link',
                'subscribe_scan': True,
                'subscribe_rgb': False,
                'subscribe_depth': False,
                'Reg/Strategy': '1',
                'ICP/Strategy': '1'
            }],
            remappings=[
                ('scan', '/scan'),
                ('odom', '/odom')
            ]
        ),

        Node(
            package='rtabmap_viz',
            executable='rtabmap_viz',
            name='rtabmapviz',
            output='screen',
            parameters=[{'use_sim_time': True}]
        )
    ])
