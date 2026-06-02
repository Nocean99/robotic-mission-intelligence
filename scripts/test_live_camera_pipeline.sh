#!/usr/bin/env bash
set -u

GZ_CAMERA_TOPIC="${GZ_CAMERA_TOPIC:-/world/red_block_search/model/x500_mono_cam_0/link/camera_link/sensor/camera/image}"
ROS_CAMERA_TOPIC="${ROS_CAMERA_TOPIC:-/camera/image_raw}"

echo "Live Gazebo camera pipeline test"
echo "Gazebo topic: $GZ_CAMERA_TOPIC"
echo "ROS topic:    $ROS_CAMERA_TOPIC"
echo

failures=0

check() {
  local name="$1"
  shift
  echo "== $name =="
  "$@"
  local code=$?
  if [ "$code" -eq 0 ]; then
    echo "[ok] $name"
  else
    echo "[fail] $name"
    failures=$((failures + 1))
  fi
  echo
}

check "Gazebo camera topic exists on macOS" bash -lc \
  "GZ_IP=127.0.0.1 gz topic -l | grep -Fx '$GZ_CAMERA_TOPIC'"

check "Gazebo publishes at least one image on macOS" python3 - <<PY
import os
import subprocess
import sys

topic = os.environ.get("GZ_CAMERA_TOPIC", "$GZ_CAMERA_TOPIC")
cmd = ["bash", "-lc", f"GZ_IP=127.0.0.1 gz topic -e -t {topic} -n 1"]
try:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
except subprocess.TimeoutExpired:
    print("Timed out waiting for one Gazebo image message.")
    sys.exit(1)
if result.returncode != 0:
    print(result.stderr.strip() or result.stdout.strip())
    sys.exit(result.returncode)
print((result.stdout or "").splitlines()[0:5])
PY

if command -v docker >/dev/null 2>&1; then
  check "Docker ROS 2 can see camera topic" bash -lc \
    "docker compose run --rm ros2 bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 topic list -t | grep -F \"$ROS_CAMERA_TOPIC [sensor_msgs/msg/Image]\"'"

  check "Docker ROS 2 receives image messages" bash -lc \
    "docker compose run --rm ros2 bash -lc 'source /opt/ros/jazzy/setup.bash && timeout 12 ros2 topic hz $ROS_CAMERA_TOPIC'"
else
  echo "[skip] docker command not found"
  failures=$((failures + 1))
fi

if [ "$failures" -eq 0 ]; then
  echo "RESULT: camera pipeline looks healthy."
else
  echo "RESULT: $failures check(s) failed."
  echo
  echo "Common fixes:"
  echo "- Make sure Gazebo server is running: ./scripts/run_red_block_world.sh"
  echo "- Make sure Gazebo GUI is running/unpaused: ./scripts/run_red_block_gui.sh"
  echo "- Make sure PX4 spawned x500_mono_cam_0: ./scripts/run_px4_camera_standalone.sh"
  echo "- Make sure the bridge is running inside Docker: ./scripts/start_camera_bridge.sh"
fi

exit "$failures"
