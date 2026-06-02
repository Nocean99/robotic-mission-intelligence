#!/usr/bin/env bash
set -euo pipefail

if ! command -v MicroXRCEAgent >/dev/null 2>&1; then
  echo "MicroXRCEAgent is not installed or not on PATH."
  echo "Install/source the PX4 ROS 2 bridge tooling, then rerun this script."
  exit 1
fi

MicroXRCEAgent udp4 -p 8888
