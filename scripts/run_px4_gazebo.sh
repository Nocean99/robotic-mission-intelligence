#!/usr/bin/env bash
set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/Documents/PX4-Autopilot}"
MODEL="${PX4_MODEL:-gz_x500}"

if [ ! -d "$PX4_DIR" ]; then
  echo "PX4 repo not found at: $PX4_DIR"
  echo "Follow docs/PX4_GAZEBO_SETUP.md first."
  exit 1
fi

cd "$PX4_DIR"
make "px4_sitl" "$MODEL"
