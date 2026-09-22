# Comparative Analysis Of Real-Time Appearance-Based Mapping And Cartographer Algorithms Using Deep Learning Object Detection

This repository contains the ROS 2 simulation, SLAM, monitoring, trajectory-processing, and evaluation code associated with the manuscript:

> **Comparative Analysis Of Real-Time Appearance-Based Mapping And Cartographer Algorithms Using Deep Learning Object Detection**

The study compares two complete ROS 2 SLAM pipelines—Cartographer and RTAB-Map—under baseline conditions and while a separate YOLOv8n object-detection node runs concurrently on the CPU.

## Study scope

Four configurations were analyzed:

1. Cartographer
2. Cartographer + YOLOv8n
3. RTAB-Map
4. RTAB-Map + YOLOv8n

Ten analyzed runs were completed for each configuration (**40 runs total**).

YOLOv8n is used only as a concurrent perception workload. Its detections are **not** supplied to Cartographer or RTAB-Map for scan matching, pose estimation, loop closure, graph optimization, or occupancy-grid generation. Legacy source/package/window names containing `fusion` refer to visualization code only and do not indicate semantic fusion into the SLAM back ends.

## Reproducibility archive

The complete 40-run reproducibility package, aggregate outputs, configuration snapshots, evaluation scripts, runtime logs, and integrity manifests are archived on Zenodo:

**Version-specific DOI:** https://doi.org/10.5281/zenodo.22878936

Zenodo record: **v1.1.0**

The Zenodo archive is the authoritative source for the full analyzed dataset used in the revised manuscript. This GitHub repository provides the corresponding source code and lightweight project material.

## Experimental platform

| Component | Configuration |
|---|---|
| Robot | TurtleBot3 Waffle Pi |
| OS | Ubuntu 22.04 LTS |
| ROS | ROS 2 Humble Hawksbill |
| Simulator | Gazebo Classic 11.10.2 |
| World | `small_house.world` |
| Cartographer ROS | `cartographer_ros` 2.0.9002 |
| TurtleBot3 Cartographer | 2.3.6 |
| TurtleBot3 Gazebo | 2.3.8 |
| RTAB-Map ROS | `rtabmap_ros` / `rtabmap_slam` 0.22.1 |
| Trajectory evaluation | evo v1.34.3 |
| Object detector | YOLOv8n, CPU-only |

TurtleBot3 source commit:

```text
da785b7201d317e6e2a662e41bb3d3fd50ebd503
```

TurtleBot3 simulations source commit:

```text
a35a56c8b04877dc89772b598084d8ce648a9023
```

## Simulation and sensor model

The evaluated Gazebo setup used:

- ODE physics engine
- `max_step_size = 0.001 s`
- target `real_time_factor = 1.0`
- `real_time_update_rate = 1000 Hz`
- Waffle Pi wheel-contact ODE friction: `mu = 100000`, `mu2 = 100000`

### 2D LiDAR

- topic: `/scan`
- nominal update rate: 8 Hz
- 360 horizontal samples
- range: 0.12–4.5 m
- range resolution: 0.015 m
- Gaussian range noise: mean 0 m, SD 0.01 m

### RGB camera

- topics: `/camera/image_raw`, `/camera/camera_info`
- resolution: 640 × 480
- nominal update rate: 30 Hz
- horizontal FOV: 1.085595 rad
- Gaussian image noise SD: 0.007

## Odometry and ground-truth isolation

The Gazebo differential-drive plugin uses:

```text
odometry_source = 0
```

Therefore `/odom` represents simulated wheel/encoder odometry.

Independent simulator ground truth is produced by a separate Gazebo P3D plugin under `/ground_truth` and is used **only for evaluation**. Neither Cartographer nor RTAB-Map subscribes to `/ground_truth/odom`.

### Cartographer inputs

- `/scan`
- `/odom`
- IMU disabled

Key retained configuration values include:

- `tracking_frame = base_footprint`
- `use_odometry = true`
- `use_imu_data = false`
- LiDAR range: 0.12–4.5 m

The retained final Cartographer Lua configuration is included in the reproducibility archive. A separate per-run hash of the Cartographer Lua file was not preserved for every run, so per-run cryptographic identity of that file is not claimed.

### RTAB-Map inputs

- `/scan`
- `/odom`
- RGB image and camera info
- depth / RGB-D disabled
- IMU intentionally excluded

The archived RTAB-Map launch file was identical across all 20 RTAB-Map-related analyzed runs. Its SHA-256 was:

```text
f7b41954430f3b907f554b36ee09c5dc4c10e18adf537b0db6d17ee006cada5a
```

The evaluated RTAB-Map pipeline uses external `/odom` together with 2D LiDAR ICP geometric registration and RGB appearance information. It should not be described as an ICP-odometry front end because local odometry is supplied externally.

## Trajectory logging and evaluation

Ground-truth and SLAM trajectories are stored in TUM format:

```text
timestamp tx ty tz qx qy qz qw
```

Before evaluation, both reference and estimated trajectories are converted to a planar **x-y-yaw** representation.

### Timestamp association

Maximum association difference:

```text
--t_max_diff 0.02
```

No interpolation is performed. Samples without a match inside the 20 ms tolerance are excluded.

### APE translation

```bash
evo_ape tum GT EST \
  --t_max_diff 0.02 \
  --align_origin \
  -r trans_part
```

### APE yaw

```bash
evo_ape tum GT EST \
  --t_max_diff 0.02 \
  --align_origin \
  -r angle_deg
```

APE uses **origin alignment only**. No full-trajectory SE(3)/Umeyama best-fit alignment is used.

### RPE translation at 1 m

```bash
evo_rpe tum GT EST \
  --t_max_diff 0.02 \
  --delta 1 \
  --delta_unit m \
  --all_pairs \
  -r trans_part
```

### RPE yaw at 1 m

```bash
evo_rpe tum GT EST \
  --t_max_diff 0.02 \
  --delta 1 \
  --delta_unit m \
  --all_pairs \
  -r angle_deg
```

RPE uses no global alignment.

## Repeated-run statistics

Each configuration contains 10 analyzed runs. Metrics are computed separately for each run and then summarized as:

**mean ± between-run sample standard deviation (n = 10)**

The revised manuscript reports both translation and yaw APE/RPE. Individual run-level values are provided in Supplementary Table S1 and the complete archived run outputs are available in Zenodo.

## Runtime and resource monitoring

The final workflow records:

- SLAM process CPU and resident memory (RSS)
- YOLO process CPU and RSS in workload runs
- combined monitored process CPU/RSS
- LiDAR rate
- camera source rate
- SLAM TF publication rate
- LiDAR-to-global-TF wall-time latency proxy
- Gazebo real-time factor
- YOLO effective FPS
- YOLO inference time
- camera-to-YOLO source-timestamp coverage

`psutil` process CPU may exceed 100% because it follows multicore semantics.

YOLOv8n ran on CPU; CUDA/GPU inference was not used in the analyzed workload runs.

## Important interpretation limits

The robot was manually teleoperated. The four groups therefore did **not** follow identical trajectories or sensor sequences. Run duration, path length, linear speed, angular speed, and accumulated rotation were quantified from ground truth.

Accordingly:

- baseline-to-YOLO localization differences are **descriptive observations**, not causal estimates of a YOLO workload effect;
- the study does not claim that one framework is intrinsically more robust to computational load;
- no matched synthetic CPU-load control was performed;
- no identical waypoint/sensor replay experiment was performed;
- occupancy maps are illustrative/reproducibility outputs only and are not used for quantitative map-quality ranking.

## Repository layout

The revised repository separates the authoritative reproducibility material from legacy files retained from the initial release.

- `REPRODUCIBILITY.md` — evaluation protocol and reproduction notes.
- `CITATION.cff` — citation metadata.
- `configs/` — retained Cartographer and official RTAB-Map configurations.
- `documentation/` — evaluation protocol, software versions, simulation parameters, motion audit, dataset manifest, and provenance limitations.
- `provenance/` — source commits and configuration SHA-256 records.
- `metrics/official_aggregates/` — official 10-run aggregate and run-level summary tables for all four configurations.
- `figures/official_representative/` — representative official Run 01 trajectory outputs.
- `maps/official_representative/` — archived representative RTAB-Map Run 01 map artifacts.
- `tools/` — trajectory processing, runtime monitoring, aggregation, and plotting scripts.
- `src/` — ROS 2 source packages and the concurrent YOLOv8n workload code.

Older files retained directly under `figures/`, `maps/`, and `metrics/` originate from the initial repository release and are preserved as legacy/reference material. They should not replace the official revised results identified above.

The complete 40-run dataset and full evaluation outputs are archived on Zenodo:

**https://doi.org/10.5281/zenodo.22878936**

## Data and code availability

Full reproducibility archive:

https://doi.org/10.5281/zenodo.22878936

Source repository:

https://github.com/abdullahmhelbanna-rgb/ros2-slam-cartographer-rtabmap-yolov8n

## Citation

If you use this repository or the accompanying dataset, please cite the associated manuscript and the Zenodo archive.

**Manuscript**

Abdullah Mohamed Abdelftah El-Banna, Bahaa El-Din Mohamed Nasser, Mohamed Sabry Saraya, and Mohamed Taher Hamed Eraky. *Comparative Analysis Of Real-Time Appearance-Based Mapping And Cartographer Algorithms Using Deep Learning Object Detection.* Scientific Reports, manuscript under revision.

**Reproducibility archive**

El-Banna, A. M. A. et al. ROS 2 SLAM Benchmark Reproducibility Package for Cartographer, RTAB-Map, and YOLOv8n Evaluation, Version v1.1.0. Zenodo. https://doi.org/10.5281/zenodo.22878936 (2026).

## Contact

Abdullah Mohamed Abdelftah El-Banna  
Mechatronics Engineering Program, Faculty of Engineering, Mansoura University, Egypt  
Email: abdullah.elbanna@must.edu.eg
