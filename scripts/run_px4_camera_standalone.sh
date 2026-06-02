#!/usr/bin/env bash
set -euo pipefail

export PX4_MODEL="${PX4_MODEL:-gz_x500_mono_cam}"
export PX4_GZ_WORLD="${PX4_GZ_WORLD:-red_block_search}"
export GZ_IP="${GZ_IP:-127.0.0.1}"

"$(dirname "$0")/run_px4_standalone.sh"
