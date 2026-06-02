#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4_DIR="${PX4_DIR:-$HOME/Documents/PX4-Autopilot}"

echo "Autonomous drone project: $ROOT_DIR"
echo "PX4 directory: $PX4_DIR"
echo

check_command() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "[ok] $name: $(command -v "$name")"
  else
    echo "[missing] $name"
  fi
}

check_command git
check_command make
check_command cmake
check_command ninja
check_command python3
check_command brew
check_command gz
check_command colcon

echo
if [ -d "$PX4_DIR" ]; then
  echo "[ok] PX4 repo exists"
  if [ -d "$PX4_DIR/.git" ]; then
    git -C "$PX4_DIR" rev-parse --short HEAD 2>/dev/null | sed 's/^/[ok] PX4 commit: /'
  fi
else
  echo "[missing] PX4 repo not found at $PX4_DIR"
  echo "Clone it with:"
  echo "  git clone https://github.com/PX4/PX4-Autopilot.git \"$PX4_DIR\""
fi

echo
echo "Next checks:"
echo "  1. cd \"$PX4_DIR\""
echo "  2. bash ./Tools/setup/macos.sh"
echo "  3. make px4_sitl gz_x500"
