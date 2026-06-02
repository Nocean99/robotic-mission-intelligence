#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${AUTONOMY_CONFIG:-$ROOT_DIR/config/autonomy.yaml}"
CAMERA_TOPIC="${CAMERA_TOPIC:-/camera/image_raw}"

cd "$ROOT_DIR"
python3 -m autonomy.debug_camera --config "$CONFIG" --camera-topic "$CAMERA_TOPIC" "$@"
