#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m autonomy.mission_vision_plan "$@"
