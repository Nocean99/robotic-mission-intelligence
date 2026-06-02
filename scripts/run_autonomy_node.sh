#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${AUTONOMY_CONFIG:-$ROOT_DIR/config/autonomy.yaml}"

cd "$ROOT_DIR"
python3 -m autonomy.run_autonomy --config "$CONFIG"
