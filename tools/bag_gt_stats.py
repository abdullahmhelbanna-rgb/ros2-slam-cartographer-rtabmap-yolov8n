#!/usr/bin/env python3

import sys
import math
import rosbag2_py

from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


if len(sys.argv) != 2:
    print("Usage: python3 bag_gt_stats.py <bag_directory>")
    sys.exit(1)

bag_path = sys.argv[1]

reader = rosbag2_py.SequentialReader()

storage_options = rosbag2_py.StorageOptions(
    uri=bag_path,
    storage_id='sqlite3'
)

converter_options = rosbag2_py.ConverterOptions(
    input_serialization_format='',
    output_serialization_format=''
)

reader.open(storage_options, converter_options)

topic_types = {
    topic.name: topic.type
    for topic in reader.get_all_topics_and_types()
}

topic = '/ground_truth/odom'

if topic not in topic_types:
    print(f"ERROR: {topic} not found in bag.")
    sys.exit(1)

msg_type = get_message(topic_types[topic])

first = None
previous = None
last = None

distance = 0.0
count = 0

t_start = None
t_end = None

xmin = ymin = float('inf')
xmax = ymax = float('-inf')

while reader.has_next():

    topic_name, data, _ = reader.read_next()

    if topic_name != topic:
        continue

    msg = deserialize_message(data, msg_type)

    x = msg.pose.pose.position.x
    y = msg.pose.pose.position.y

    stamp = (
        msg.header.stamp.sec +
        msg.header.stamp.nanosec * 1e-9
    )

    if first is None:
        first = (x, y)
        t_start = stamp

    if previous is not None:
        dx = x - previous[0]
        dy = y - previous[1]

        step = math.hypot(dx, dy)

        # Reject impossible jumps only
        if step < 1.0:
            distance += step

    previous = (x, y)
    last = (x, y)

    xmin = min(xmin, x)
    xmax = max(xmax, x)
    ymin = min(ymin, y)
    ymax = max(ymax, y)

    t_end = stamp
    count += 1


duration = t_end - t_start

start_end_error = math.hypot(
    last[0] - first[0],
    last[1] - first[1]
)

average_speed = distance / duration if duration > 0 else 0.0


print("\n========== GROUND TRUTH RUN STATS ==========")

print(f"Samples               : {count}")
print(f"Duration               : {duration:.3f} s")
print(f"Path length            : {distance:.3f} m")
print(f"Mean translational rate: {average_speed:.3f} m/s")

print()
print(f"Start position         : ({first[0]:.3f}, {first[1]:.3f})")
print(f"End position           : ({last[0]:.3f}, {last[1]:.3f})")
print(f"Start-end displacement : {start_end_error:.3f} m")

print()
print(f"X range                : {xmin:.3f} → {xmax:.3f} m")
print(f"Y range                : {ymin:.3f} → {ymax:.3f} m")

print("============================================\n")
