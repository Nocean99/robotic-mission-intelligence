#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"
docker compose run --rm ros2 bash -lc 'source /opt/ros/jazzy/setup.bash && ./scripts/check_ros2_env.sh'
