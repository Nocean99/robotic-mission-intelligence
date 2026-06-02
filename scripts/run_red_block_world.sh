#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4_DIR="${PX4_DIR:-$HOME/Documents/PX4-Autopilot}"
WORLD_FILE="$ROOT_DIR/sim_assets/worlds/red_block_search.sdf"

if ! command -v gz >/dev/null 2>&1; then
  echo "Gazebo command 'gz' was not found. Install/source Gazebo first."
  exit 1
fi

export GZ_SIM_RESOURCE_PATH="$ROOT_DIR/sim_assets/models:$PX4_DIR/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}"
export GZ_SIM_SERVER_CONFIG_PATH="$ROOT_DIR/sim_assets/server.config"
export GZ_IP="${GZ_IP:-127.0.0.1}"

MODE="${GZ_MODE:-server}"

case "$MODE" in
  server)
    gz sim -r -s "$WORLD_FILE"
    ;;
  gui)
    gz sim -g
    ;;
  *)
    echo "Unknown GZ_MODE=$MODE. Use GZ_MODE=server or GZ_MODE=gui."
    exit 1
    ;;
esac
