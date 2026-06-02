#!/usr/bin/env bash
set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/Documents/PX4-Autopilot}"
MODEL="${PX4_MODEL:-gz_x500}"
WORLD="${PX4_GZ_WORLD:-}"

cd "$PX4_DIR"
source "$PX4_DIR/.venv/bin/activate"
if [ -n "$WORLD" ]; then
  PX4_GZ_STANDALONE=1 PX4_GZ_WORLD="$WORLD" GZ_IP="${GZ_IP:-127.0.0.1}" make px4_sitl "$MODEL"
else
  PX4_GZ_STANDALONE=1 GZ_IP="${GZ_IP:-127.0.0.1}" make px4_sitl "$MODEL"
fi
