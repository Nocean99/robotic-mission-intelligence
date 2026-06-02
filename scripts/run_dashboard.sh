#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${DRONE_DASHBOARD_PORT:-8000}"

cd "$ROOT_DIR"
python3 server.py --port "$PORT"
