# Docker ROS 2 Environment

This is the easiest way to get `ros2`, `ros_gz_bridge`, `sensor_msgs`, and `cv_bridge` available without installing ROS 2 directly on macOS.

## Build

Make sure Docker Desktop is running, then:

```bash
cd "/Users/noah/Documents/autonomous drone"
./scripts/docker_build_ros2.sh
```

## Check ROS 2

```bash
./scripts/docker_check_ros2.sh
```

Expected:

```text
[ok] ros2
[ok] ROS_DISTRO=jazzy
[ok] ros_gz_bridge
[ok] sensor_msgs
[ok] cv_bridge
```

## Open A ROS 2 Shell

```bash
./scripts/docker_shell_ros2.sh
```

Inside the container:

```bash
./scripts/check_ros2_env.sh
python3 tests/test_search_mission.py
```

## Notes

The project folder is mounted into the container at:

```text
/workspace/autonomous-drone
```

The macOS terminal will still say `ros2 command not found`; that is expected. ROS 2 exists inside the container.

Live Gazebo camera bridging from macOS Gazebo into Docker may require extra networking. If topic discovery does not cross the Docker boundary, the reliable fallback is to run the Gazebo/ROS side together inside the Ubuntu container or move the full stack to an Ubuntu VM.
