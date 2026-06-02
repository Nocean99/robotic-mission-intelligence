#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_CAMERA_TOPIC="${ROS_CAMERA_TOPIC:-/camera/image_raw}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ERROR: ros2 is not on PATH."
  echo "Source ROS 2 first:"
  echo "  source /opt/ros/<distro>/setup.bash"
  exit 1
fi

echo "ROS 2 topics:"
ros2 topic list -t
echo

if ! ros2 topic list | grep -Fx "$ROS_CAMERA_TOPIC" >/dev/null 2>&1; then
  echo "ERROR: expected camera topic not found: $ROS_CAMERA_TOPIC"
  echo "Use scripts/list_camera_topics.sh to compare Gazebo and ROS 2 topics."
  exit 1
fi

echo "Camera topic found: $ROS_CAMERA_TOPIC"
ros2 topic info "$ROS_CAMERA_TOPIC"
echo

if [ "${SAVE_DEBUG_FRAME:-1}" = "1" ]; then
  cd "$ROOT_DIR"
  ./scripts/debug_camera_frame.sh --camera-topic "$ROS_CAMERA_TOPIC" --wait-s "${CAMERA_WAIT_S:-15}"
fi
