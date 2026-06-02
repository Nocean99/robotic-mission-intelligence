#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m autonomy.vision_report_viewer "$@"
