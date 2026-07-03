# Comparative Analysis of Real-Time Appearance-Based Mapping and Cartographer Algorithms Using Deep Learning Object Detection

This repository contains the ROS 2 simulation workflow, configuration files, trajectory logs, and evaluation commands used for a comparative study of two LiDAR-based SLAM frameworks:

- Google Cartographer
- RTAB-Map with ICP odometry

The experiments use a TurtleBot3 Waffle Pi in an indoor Gazebo House World environment. Each framework is evaluated in a baseline configuration and while a YOLOv8n object-detection and visualization workload runs concurrently.

> **Important scope note:** YOLOv8n is used as a concurrent perception workload. Its detections are visualized through the `semantic_fusion` nodes and are **not** injected into the Cartographer or RTAB-Map SLAM back end in the final reported workflow.

---

## Study configurations

The reported comparison includes four configurations:

1. Cartographer
2. Cartographer + YOLOv8n + fusion visualization
3. RTAB-Map
4. RTAB-Map + YOLOv8n + fusion visualization

The simulator provides the ground-truth trajectory through `/ground_truth/odom`. The estimated SLAM trajectory is collected from the TF transform:

```text
map -> base_footprint
```

All trajectory logging is performed at **10 Hz** using simulation time.

---

## System overview

| Component | Configuration |
|---|---|
| Robot platform | TurtleBot3 Waffle Pi |
| Operating system | Ubuntu 22.04 LTS |
| ROS distribution | ROS 2 Humble |
| Simulation | Gazebo House World |
| SLAM sensors | 2D LiDAR |
| Perception sensor | Simulated RGB camera |
| Object detector | YOLOv8n |
| Ground-truth topic | `/ground_truth/odom` |
| SLAM trajectory source | TF: `map -> base_footprint` |
| Trajectory format | TUM |
| Evaluation toolkit | EVO |
| Logging rate | 10 Hz |

---

## Repository layout

A recommended clean repository structure is:

```text
turtlebot3_ws/
├── src/
│   ├── turtlebot3/
│   ├── turtlebot3_cartographer/
│   ├── turtlebot3_rtab/
│   ├── turtlebot3_gazebo/
│   ├── semantic_fusion/
│   └── ... other ROS 2 packages
├── tools/
│   ├── log_gt_odom_pose.py
│   ├── log_slam_pose.py
│   └── analyze_trajectories.py
├── metrics/
│   ├── cartographer/
│   ├── cartographer_yolo/
│   ├── rtabmap/
│   └── rtab_yolo/
├── maps/
├── figures/
├── README.md
└── requirements.txt
```

Do not include generated ROS workspace folders such as `build/`, `install/`, or `log/` in the public repository.

---

## Prerequisites

Install ROS 2 Humble and the ROS packages required by the workspace. Then build the workspace:

```bash
cd ~/turtlebot3_ws
colcon build
source /opt/ros/humble/setup.bash
source install/setup.bash
```

Set the robot model and ROS domain ID used in the reported workflow:

```bash
export TURTLEBOT3_MODEL=waffle_pi
export ROS_DOMAIN_ID=30
```

### Python tools

The workflow requires Python packages used by YOLOv8n and trajectory evaluation. A typical environment includes:

```bash
pip install ultralytics evo numpy matplotlib opencv-python
```

Install any additional package dependencies declared by the ROS packages in `src/`.

---

## Common simulation setup

Start each terminal with:

```bash
cd ~/turtlebot3_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export ROS_DOMAIN_ID=30
```

Launch Gazebo:

```bash
ros2 launch turtlebot3_gazebo house.launch.py
```

Useful checks:

```bash
ros2 topic echo /ground_truth/odom --once
ros2 topic echo /clock --once
ros2 topic info /odom
ros2 topic info /ground_truth/odom
```

---

## A. Cartographer baseline

### Terminal 1 — Gazebo

```bash
ros2 launch turtlebot3_gazebo house.launch.py
```

### Terminal 2 — Cartographer

```bash
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=true
```

Optional TF check:

```bash
timeout 5s ros2 run tf2_ros tf2_echo map base_footprint
```

### Terminal 3 — Ground-truth logger

```bash
python3 ~/turtlebot3_ws/tools/log_gt_odom_pose.py --ros-args \
  -p use_sim_time:=true \
  -p topic:=/ground_truth/odom \
  -p outfile:=~/turtlebot3_ws/metrics/cartographer/gt_gazebo_tum.txt
```

### Terminal 4 — SLAM logger

```bash
python3 ~/turtlebot3_ws/tools/log_slam_pose.py --ros-args \
  -p use_sim_time:=true \
  -p map_frame:=map \
  -p base_frame:=base_footprint \
  -p rate_hz:=10.0 \
  -p outfile:=~/turtlebot3_ws/metrics/cartographer/slam_tum.txt
```

### Terminal 5 — Teleoperation

```bash
ros2 run turtlebot3_teleop teleop_keyboard
```

---

## B. Cartographer + YOLOv8n + fusion visualization

Run Gazebo, Cartographer, and both loggers as in the Cartographer baseline. Then add:

### Terminal 3 — YOLOv8n

```bash
ros2 run semantic_fusion yolo_node --ros-args \
  -p use_sim_time:=true \
  -r image:=/camera/image_raw \
  -r camera_info:=/camera/camera_info \
  --log-level info
```

### Terminal 4 — Fusion visualization

```bash
ros2 run semantic_fusion fusion_node_master --ros-args \
  -p use_sim_time:=true \
  -p map_frame:=map \
  -p base_frame:=base_footprint \
  --log-level info
```

Use separate output paths, for example:

```text
metrics/cartographer_yolo/gt_gazebo_tum.txt
metrics/cartographer_yolo/slam_tum.txt
```

---

## C. RTAB-Map baseline

Before each RTAB-Map run, remove any prior RTAB-Map database to prevent carry-over between experiments:

```bash
rm -f ~/.ros/rtabmap.db
```

### Terminal 1 — Gazebo

```bash
ros2 launch turtlebot3_gazebo house.launch.py
```

### Terminal 2 — RTAB-Map

```bash
ros2 launch turtlebot3_rtab rtab.launch.py delete_db_on_start:=true
```

### Terminal 3 — Ground-truth logger

```bash
python3 ~/turtlebot3_ws/tools/log_gt_odom_pose.py --ros-args \
  -p use_sim_time:=true \
  -p topic:=/ground_truth/odom \
  -p outfile:=~/turtlebot3_ws/metrics/rtabmap/gt_gazebo_tum.txt
```

### Terminal 4 — SLAM logger

```bash
python3 ~/turtlebot3_ws/tools/log_slam_pose.py --ros-args \
  -p use_sim_time:=true \
  -p map_frame:=map \
  -p base_frame:=base_footprint \
  -p rate_hz:=10.0 \
  -p outfile:=~/turtlebot3_ws/metrics/rtabmap/slam_tum.txt
```

### Terminal 5 — Teleoperation

```bash
ros2 run turtlebot3_teleop teleop_keyboard
```

---

## D. RTAB-Map + YOLOv8n + fusion visualization

Run the RTAB-Map baseline procedure, then add:

```bash
ros2 run semantic_fusion yolo_node --ros-args \
  -p use_sim_time:=true \
  --log-level info
```

```bash
ros2 run semantic_fusion fusion_node_master --ros-args \
  -p use_sim_time:=true \
  -p map_frame:=map \
  -p base_frame:=base_footprint \
  --log-level info
```

Use separate output paths, for example:

```text
metrics/rtab_yolo/gt_gazebo_tum.txt
metrics/rtab_yolo/slam_tum.txt
```

---

## Trajectory evaluation

The ground-truth and SLAM trajectories are stored in TUM format:

```text
timestamp tx ty tz qx qy qz qw
```

### Absolute Pose Error (APE)

Translation-only APE after alignment:

```bash
evo_ape tum gt_gazebo_tum.txt slam_tum.txt -a -r trans_part
```

### Relative Pose Error (RPE)

Translation-only RPE with a 1 m displacement interval:

```bash
evo_rpe tum gt_gazebo_tum.txt slam_tum.txt \
  --delta 1 \
  --delta_unit m \
  --all_pairs \
  -a \
  -r trans_part
```

### Trajectory plotting

```bash
evo_traj tum \
  gt_gazebo_tum.txt \
  slam_tum.txt \
  --ref gt_gazebo_tum.txt \
  -a \
  --plot \
  --plot_mode=xy
```

The `-a` option applies trajectory alignment before evaluation. The reported analysis uses translation-only errors (`trans_part`).

---

## Saving occupancy maps

Save a generated occupancy-grid map using:

```bash
ros2 run nav2_map_server map_saver_cli -f ~/output_map --ros-args -r map:=/map
```

This creates:

```text
output_map.pgm
output_map.yaml
```

Place final maps used in the manuscript under:

```text
maps/
```

Suggested names:

```text
cartographer_baseline.pgm
cartographer_baseline.yaml
cartographer_yolov8n.pgm
cartographer_yolov8n.yaml
rtabmap_baseline.pgm
rtabmap_baseline.yaml
rtabmap_yolov8n.pgm
rtabmap_yolov8n.yaml
```

---

## Reproducibility notes

- Keep the robot model, Gazebo world, ROS topic structure, TF conventions, and simulation-time settings unchanged across all configurations.
- Use `use_sim_time:=true` for the SLAM, YOLOv8n, fusion, and trajectory-logger nodes.
- Use the same navigation/teleoperation strategy for all compared configurations.
- Start each RTAB-Map run with a clean database.
- Store each repeated run in a separate, clearly named folder before aggregation.
- The EVO `STD` output describes the spread of trajectory-error samples within one evaluated trajectory; it is not a between-run standard deviation.

A recommended naming convention for future repeated experiments is:

```text
metrics/
├── cartographer/run_01 ... run_04
├── cartographer_yolo/run_01 ... run_04
├── rtabmap/run_01 ... run_04
└── rtab_yolo/run_01 ... run_04
```

---

## Data and code availability

The repository is intended to include:

- ROS 2 launch files and configuration files
- `semantic_fusion` source code
- trajectory loggers
- final TUM trajectory files
- EVO evaluation outputs
- occupancy-grid maps
- manuscript figures

For an archival release, create a tagged GitHub release and archive it in Zenodo to obtain a permanent DOI.

---

## Citation

If you use this repository, please cite the associated manuscript:

```text
Abdullah Mohamed Abdelftah El-Banna, Bahaa Nasser,
Mohamed Sabry Saraya, and Mohamed T. Eraky.
Comparative Analysis of Real-Time Appearance-Based Mapping and
Cartographer Algorithms Using Deep Learning Object Detection.
[Journal / DOI to be added after publication]
```

---

## License

Add a license before public release. For an academic code repository, one possible option is the MIT License. For data or figures that should not be reused freely, specify a separate data/figure license.

---

## Contact

**Abdullah Mohamed Abdelftah El-Banna**  
Mechatronics Engineering Program, Faculty of Engineering, Mansoura University, Egypt  
Email: abdullah.elbanna@must.edu.eg
