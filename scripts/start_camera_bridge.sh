#!/usr/bin/env bash
set -euo pipefail

GZ_CAMERA_TOPIC="${GZ_CAMERA_TOPIC:-/world/red_block_search/model/x500_0/link/camera_link/sensor/camera/image}"
ROS_CAMERA_TOPIC="${ROS_CAMERA_TOPIC:-/camera/image_raw}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ERROR: ros2 is not on PATH."
  echo "Source ROS 2 first, for example:"
  echo "  source /opt/ros/<distro>/setup.bash"
  echo "If using a workspace, also source:"
  echo "  source <workspace>/install/setup.bash"
  exit 1
fi

if ! ros2 pkg prefix ros_gz_bridge >/dev/null 2>&1; then
  echo "ERROR: ros_gz_bridge is not available in this ROS 2 environment."
  echo "Install/source ros_gz_bridge before starting the camera bridge."
  exit 1
fi

echo "Starting Gazebo -> ROS 2 camera bridge"
echo "  Gazebo: $GZ_CAMERA_TOPIC"
echo "  ROS 2:  $ROS_CAMERA_TOPIC"

ros2 run ros_gz_bridge parameter_bridge "$GZ_CAMERA_TOPIC@sensor_msgs/msg/Image@gz.msgs.Image" --ros-args -r "$GZ_CAMERA_TOPIC:=$ROS_CAMERA_TOPIC"
