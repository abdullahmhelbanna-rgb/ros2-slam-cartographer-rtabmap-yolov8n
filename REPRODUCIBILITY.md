# Reproducibility

## Manuscript

**Comparative Analysis Of Real-Time Appearance-Based Mapping And Cartographer Algorithms Using Deep Learning Object Detection**

## Experimental design

Four ROS 2 configurations were evaluated:

1. Cartographer
2. Cartographer + YOLOv8n
3. RTAB-Map
4. RTAB-Map + YOLOv8n

Each configuration contains 10 analyzed runs, giving 40 official analyzed runs in total.

The robot was manually teleoperated. The four experimental groups therefore do not represent matched trajectories or identical sensor sequences. Baseline-to-YOLO differences are descriptive and must not be interpreted as controlled causal estimates of computational-workload sensitivity.

## Software environment

- Ubuntu 22.04 LTS
- ROS 2 Humble
- Gazebo Classic 11.10.2
- evo 1.34.3
- Cartographer ROS 2.0.9002
- TurtleBot3 Cartographer 2.3.6
- TurtleBot3 Gazebo 2.3.8
- RTAB-Map ROS / rtabmap_slam 0.22.1
- YOLOv8n, CPU-only during official workload runs

## Source provenance

TurtleBot3 commit:

da785b7201d317e6e2a662e41bb3d3fd50ebd503

TurtleBot3 simulations commit:

a35a56c8b04877dc89772b598084d8ce648a9023

See provenance/SOURCE_COMMITS.txt.

## Official configurations

Cartographer:

configs/cartographer/turtlebot3_lds_2d.lua

RTAB-Map:

configs/rtabmap/rtab.launch.py

See provenance/CONFIG_SHA256.txt.

The RTAB-Map launch file has SHA-256:

f7b41954430f3b907f554b36ee09c5dc4c10e18adf537b0db6d17ee006cada5a

and was verified across all 20 official RTAB-Map-related runs.

The retained final Cartographer configuration is provided, but a separate per-run cryptographic hash of the Lua file was not preserved for every official run.

## Inputs and isolation

Cartographer uses:

- /scan
- /odom
- IMU disabled

RTAB-Map uses:

- /scan
- /odom
- RGB image and camera information
- depth disabled
- RGB-D disabled
- IMU excluded

Simulator ground truth is published separately under /ground_truth and is used only as an evaluation reference. Ground truth is not supplied to either SLAM back end.

YOLOv8n operates as a separate concurrent CPU perception workload. Object detections are not supplied to Cartographer or RTAB-Map for scan matching, odometry, graph optimization, loop closure, or occupancy-grid construction.

## Trajectory evaluation

Both estimated and ground-truth trajectories are converted to planar x, y, yaw representations.

Maximum timestamp association difference:

0.02 s

No trajectory interpolation is used.

### APE translation

evo_ape tum GT EST --t_max_diff 0.02 --align_origin -r trans_part

### APE yaw

evo_ape tum GT EST --t_max_diff 0.02 --align_origin -r angle_deg

APE uses origin alignment only. No unrestricted full-trajectory SE(3)/Umeyama best-fit alignment is applied.

### RPE translation at 1 m

evo_rpe tum GT EST --t_max_diff 0.02 --delta 1 --delta_unit m --all_pairs -r trans_part

### RPE yaw at 1 m

evo_rpe tum GT EST --t_max_diff 0.02 --delta 1 --delta_unit m --all_pairs -r angle_deg

RPE uses no global alignment.

## Repeated-run statistics

Each metric is computed independently for each run and then summarized as:

mean ± between-run sample standard deviation, n = 10 per configuration.

Pose samples are not treated as independent experimental replicates.

## Runtime monitoring

The official workflow records:

- SLAM process CPU and RSS
- YOLO process CPU and RSS for YOLO-active configurations
- combined monitored-process CPU and RSS
- LiDAR rate
- camera source rate
- SLAM TF publication rate
- LiDAR-to-global-TF wall-time latency proxy
- Gazebo real-time factor
- YOLO effective FPS
- YOLO inference time
- camera-to-YOLO source-timestamp coverage

psutil process CPU may exceed 100% because of multicore semantics.

## Full archived dataset

The complete official 40-run dataset, runtime logs, result tables, configuration snapshots, evaluation outputs, and integrity manifests are archived on Zenodo:

DOI: 10.5281/zenodo.22878936

https://doi.org/10.5281/zenodo.22878936

GitHub provides source code, retained configurations, lightweight representative material, and documentation. Zenodo is the authoritative archive for the complete analyzed dataset.

## YOLOv8n checkpoint

The YOLOv8n checkpoint retained in this GitHub repository is:

`yolov8n.pt`

SHA-256:

`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`

The Zenodo v1.1.0 reproducibility archive does not duplicate the `.pt` checkpoint; the GitHub repository retains this checkpoint as part of the source repository material.

### Checkpoint path used by the archived YOLO node

The archived YOLO node resolves the checkpoint from:

`~/turtlebot3_ws/yolov8n.pt`

For reproduction with the archived source unchanged, place or link the retained
`yolov8n.pt` checkpoint at that path before launching the YOLO node.
