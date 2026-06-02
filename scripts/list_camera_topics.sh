#!/usr/bin/env bash
set -euo pipefail

echo "Gazebo camera topics:"
if command -v gz >/dev/null 2>&1; then
  gz topic -l | grep -E 'camera|image|rgb|depth' || true
else
  echo "  gz not found"
fi

echo
echo "ROS 2 image topics:"
if command -v ros2 >/dev/null 2>&1; then
  ros2 topic list -t | grep -E 'sensor_msgs/msg/Image|camera|image|rgb|depth' || true
else
  echo "  ros2 not found. Source ROS 2 before checking bridged topics."
fi
