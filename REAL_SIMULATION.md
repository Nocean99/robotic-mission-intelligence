# Real Simulation Path

Your current dashboard is a mission-control prototype. The next step is to connect it to a real software-in-the-loop simulator, where a real autopilot flies a simulated vehicle in a simulated world.

## Recommended Stack

Start with:

- PX4 SITL for the autopilot
- Gazebo for 3D vehicle physics, wind, world geometry, and simulated sensors
- ROS 2 for autonomy nodes
- This dashboard for mission status, alerts, commands, and logs

ArduPilot SITL is also a good path, especially for fast failure testing and built-in simulation parameters.

## What Changes In Real Simulation

Current prototype:

```text
Dashboard -> simple Python drone model
```

Real simulation:

```text
Dashboard
  -> autonomy/telemetry bridge
  -> ROS 2 nodes
  -> PX4 or ArduPilot SITL
  -> Gazebo simulated drone, world, wind, camera, lidar/depth
```

## Wind And Balance

A DJI-like drone does not simply fly to waypoints. It continuously stabilizes itself:

- IMU estimates roll, pitch, yaw, acceleration, and angular velocity.
- Flight controller compares the desired attitude/position to the current one.
- PID-style control loops adjust motor outputs many times per second.
- GPS/vision/optical-flow help hold position against wind.
- Mission autonomy sends high-level goals; the autopilot handles low-level balance.

So for real simulation, do not hand-code motor balancing first. Let PX4 or ArduPilot handle the low-level stabilization, then test whether your autonomy makes good decisions when wind pushes the drone around.

## Camera Testing Without Hardware

You can test camera reactions three ways:

1. Synthetic dashboard events
   Use this repo's camera test buttons to inject `person`, `vehicle`, `drone-like object`, and `unknown` detections.

2. Gazebo simulated camera
   Attach a camera sensor to the simulated drone and subscribe to the camera frames in ROS 2.

3. Recorded video replay
   Feed saved video files into the perception node as if they were live camera frames. This is useful for repeatable object-detection tests.

## First Real-Sim Milestones

1. Boot PX4 SITL with a quadcopter in Gazebo.
2. Confirm manual takeoff, hover, land, and return-to-launch in the simulator.
3. Add wind and verify the autopilot holds position.
4. Add a simulated camera and view the image stream.
5. Run a perception node on that camera stream.
6. Send detections into this dashboard as alerts.
7. Let this dashboard send start, hold, RTH, and abort commands through a bridge.

## Red Block Camera Integration Checklist

This project now includes a camera-perception integration path for finding a red block with classical OpenCV HSV thresholding.

### ROS 2 Environment Setup

Before running ROS 2 bridge or autonomy commands, source ROS 2:

```bash
source /opt/ros/<distro>/setup.bash
```

Replace `<distro>` with your installed ROS 2 distribution, for example `humble`, `jazzy`, or `kilted`.

If you built `px4_msgs`, `ros_gz_bridge`, or other packages in a workspace, source that workspace too:

```bash
source <your_ros_workspace>/install/setup.bash
```

Check the environment:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/check_ros2_env.sh
```

Expected checks:

```text
ros2 command exists
ROS_DISTRO is set
ros_gz_bridge is available
sensor_msgs is available
cv_bridge is available
```

Verify ROS 2 can list topics:

```bash
ros2 topic list
```

### Model And World

Use:

```text
PX4 model: gz_x500_mono_cam
Gazebo world: sim_assets/worlds/red_block_search.sdf
Target model: sim_assets/models/red_block
```

The red block is a simple bright red cube placed at:

```text
x: 6 m
y: 4 m
z: 0.5 m
```

### Start PX4/Gazebo

Terminal 1, start the custom Gazebo world:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/run_red_block_world.sh
```

On macOS, Gazebo server and GUI must run separately. In another terminal, open the GUI:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/run_red_block_gui.sh
```

Terminal 2, start PX4 with the RGB camera model:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/run_px4_camera_standalone.sh
```

Expected PX4 model:

```text
x500_0
```

### Confirm Gazebo Camera Topic

Run:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/list_camera_topics.sh
```

Expected Gazebo topic is usually:

```text
/world/red_block_search/model/x500_0/link/camera_link/sensor/camera/image
```

If the model name or world name differs, use the actual topic printed by `gz topic -l`.

### Start ROS 2 Camera Bridge

Terminal 3:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/start_camera_bridge.sh
```

This bridges the Gazebo camera image to:

```text
/camera/image_raw
```

Expected ROS 2 message type:

```text
sensor_msgs/msg/Image
```

Verify:

```bash
ros2 topic list -t
ros2 topic info /camera/image_raw
```

Or run the project verifier:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/verify_camera_feed.sh
```

### Start uXRCE-DDS Agent

If your PX4 ROS 2 setup needs the agent, run:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/run_uxrce_agent.sh
```

### Save A Camera Debug Frame

Before flying the full mission, verify that the detector sees the camera image:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/debug_camera_frame.sh --camera-topic /camera/image_raw
```

Expected output:

```text
logs/debug_camera_<timestamp>.png
```

The debug image is three panels:

```text
raw camera | HSV mask | detection overlay
```

### Run Full Search Mission

Terminal 4:

```bash
cd "/Users/noah/Documents/autonomous drone"
python3 -m autonomy.search_mission --camera-source ros2 --topic /camera/image_raw
```

Expected behavior:

1. PX4 receives continuous Offboard setpoints.
2. Drone takes off to search altitude.
3. Drone flies the configured search pattern.
4. Camera frames are converted to OpenCV images.
5. Red block is detected over multiple consecutive frames.
6. Mission approaches slowly if enabled.
7. Target location is marked.
8. Mission returns home and lands.

Expected logs:

```text
logs/search_mission_<timestamp>.csv
logs/world_model_<timestamp>.json
logs/world_model_<timestamp>.png
logs/target_<timestamp>.png
```

### Common Failure Cases

`ros2 is not on PATH`

Source ROS 2 before running bridge/autonomy commands.

```bash
source /opt/ros/<distro>/setup.bash
source <your_ros_workspace>/install/setup.bash
```

`ros_gz_bridge is not available`

Install/source `ros_gz_bridge`. Without it, Gazebo camera topics will not appear as ROS 2 image topics.

`Camera topic '/camera/image_raw' was not found`

Run `./scripts/list_camera_topics.sh`, confirm the Gazebo topic, then update `GZ_CAMERA_TOPIC` or `ROS_CAMERA_TOPIC`.

Example:

```bash
GZ_CAMERA_TOPIC=/world/red_block_search/model/x500_0/link/camera_link/sensor/camera/image \
ROS_CAMERA_TOPIC=/camera/image_raw \
./scripts/start_camera_bridge.sh
```

`No camera frame received`

Check that Gazebo is running, the camera model is `gz_x500_mono_cam`, and the bridge is still alive.

`Detector sees nothing`

Open `logs/debug_camera_<timestamp>.png`. If the red block is not visible in the raw frame, adjust the search path, camera angle, or target location.

`Detection is unstable`

The mission will continue searching until the target is detected for `target.required_confirm_frames` consecutive frames.

`Target not found before timeout`

The mission returns home and lands.

## Practical Choice

Use PX4 + Gazebo + ROS 2 if your priority is a modern robotics/autonomy stack.

Use ArduPilot SITL if your priority is fast autopilot failure testing, wind parameters, and broad vehicle behavior testing.

Either way, keep the same rule: the dashboard and autonomy logic should be tested in simulation long before any real propellers spin.
