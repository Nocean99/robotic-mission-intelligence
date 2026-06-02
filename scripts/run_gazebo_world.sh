#!/usr/bin/env bash
set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/Documents/PX4-Autopilot}"
WORLD="${PX4_GZ_WORLD:-default}"

cd "$PX4_DIR/Tools/simulation/gz"
python3 simulation-gazebo --world "$WORLD" --gz_ip 127.0.0.1
