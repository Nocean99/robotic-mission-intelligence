#!/usr/bin/env bash
set -u

echo "ROS 2 environment check"
echo

if command -v ros2 >/dev/null 2>&1; then
  echo "[ok] ros2: $(command -v ros2)"
else
  echo "[missing] ros2 command not found"
  echo "  Try: source /opt/ros/<distro>/setup.bash"
fi

if [ -n "${ROS_DISTRO:-}" ]; then
  echo "[ok] ROS_DISTRO=$ROS_DISTRO"
else
  echo "[missing] ROS_DISTRO is not set"
fi

check_ros_pkg() {
  local pkg="$1"
  if command -v ros2 >/dev/null 2>&1 && ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
    echo "[ok] $pkg"
  else
    echo "[missing] $pkg"
  fi
}

check_ros_pkg ros_gz_bridge
check_ros_pkg sensor_msgs
check_ros_pkg cv_bridge

echo
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
checks = [
    ("rclpy", "ROS 2 Python client"),
    ("sensor_msgs.msg", "sensor_msgs Python messages"),
    ("cv_bridge", "cv_bridge Python module"),
]
for module, label in checks:
    try:
        __import__(module)
        print(f"[ok] Python import {module} ({label})")
    except Exception as exc:
        print(f"[missing] Python import {module} ({label}): {exc}")
PY
fi

echo
echo "If any ROS packages are missing, source your ROS install and workspace:"
echo "  source /opt/ros/<distro>/setup.bash"
echo "  source <your_ros_workspace>/install/setup.bash"
