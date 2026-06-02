#!/usr/bin/env bash
set -euo pipefail

PX4_GZ_WORLD=windy "$(dirname "$0")/run_gazebo_world.sh"
