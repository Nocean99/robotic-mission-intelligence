# PX4 SITL + Gazebo Setup

This guide turns the current dashboard project into a real software-in-the-loop drone simulation workflow.

The target stack is:

```text
PX4 Autopilot SITL
+ Gazebo Harmonic simulation
+ simulated X500 quadcopter
+ simulated sensors/camera
+ this dashboard for mission status, safety events, and portfolio demos
```

## Why PX4 SITL

PX4 SITL runs the real PX4 autopilot as software on your computer. Gazebo provides the simulated vehicle, physics, world, wind, and sensors. That means you can test professional flight behavior before touching physical hardware.

Official references:

- PX4 macOS development environment: https://docs.px4.io/main/en/dev_setup/dev_env_mac
- PX4 Gazebo simulation: https://docs.px4.io/main/en/sim_gazebo_gz/
- PX4 simulation overview: https://docs.px4.io/main/en/simulation/

## Install Prerequisites On macOS

Run these from a normal terminal, not inside the dashboard.

```bash
xcode-select --install
```

Install Homebrew if it is not already installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Increase the open-file limit before installing Gazebo. In the current terminal, run:

```bash
ulimit -S -n 4096
```

To make this persistent for Bash, add it to `~/.bash_profile`:

```bash
echo 'ulimit -S -n 4096' >> ~/.bash_profile
```

Then open a new terminal.

## Clone PX4

This keeps PX4 next to your dashboard project:

```bash
cd "$HOME/Documents"
git clone https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot
git submodule update --init --recursive
```

## Install PX4 Dependencies

PX4 provides a macOS setup script:

```bash
cd "$HOME/Documents/PX4-Autopilot"
bash ./Tools/setup/macos.sh --sim-tools
```

The `--sim-tools` flag matters. Without it, PX4 installs the build toolchain but skips Gazebo, Protobuf, XQuartz, and related simulator packages.

Restart your terminal after the script completes.

## Launch The First Real Simulation

```bash
cd "$HOME/Documents/PX4-Autopilot"
source "$HOME/Documents/PX4-Autopilot/.venv/bin/activate"
make px4_sitl gz_x500
```

Expected result:

- PX4 starts in SITL mode.
- Gazebo opens with an X500 quadcopter.
- PX4 console output appears in the terminal.

## Useful Simulation Commands

Inside the PX4 console:

```text
commander takeoff
commander land
commander mode hold
commander mode return
```

If the simulation opens correctly, your machine is ready for real SITL work.

## Troubleshooting

### `ninja: error: unknown target 'gz_x500'`

PX4 documents this as a generated-build-cache issue. Clean the PX4 build tree and try again:

```bash
cd "$HOME/Documents/PX4-Autopilot"
source "$HOME/Documents/PX4-Autopilot/.venv/bin/activate"
make distclean
make px4_sitl gz_x500
```

### `cmake: command not found`

Install the build tools:

```bash
brew install cmake ninja
```

### `gz: command not found`

Gazebo is missing or not on your shell path. Re-run PX4's setup script, then restart Terminal:

```bash
cd "$HOME/Documents/PX4-Autopilot"
bash ./Tools/setup/macos.sh --sim-tools
```

If that still does not install Gazebo, install it directly:

```bash
brew tap osrf/simulation
ulimit -S -n 4096
brew install osrf/simulation/gz-harmonic
```

If Homebrew says `The maximum number of open files on this system has been reached`, run the `ulimit` command above and repeat the install command.

Verify:

```bash
gz sim --versions
```

Then rebuild PX4:

```bash
cd "$HOME/Documents/PX4-Autopilot"
source "$HOME/Documents/PX4-Autopilot/.venv/bin/activate"
make distclean
make px4_sitl gz_x500
```

### Protobuf `Resize` Deprecation Build Error

If the build fails in `GZMixingInterfaceESC.cpp` or `GZMixingInterfaceWheel.cpp` with a Protobuf `Resize` deprecation error, Homebrew has installed a newer Protobuf than PX4 currently expects. Patch the local PX4 checkout:

```bash
python3 - <<'PY'
from pathlib import Path

replacements = {
    Path.home() / "Documents/PX4-Autopilot/src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp": (
        "\t\trotor_velocity_message.mutable_velocity()->Resize(active_output_count, 0);",
        "\t\tfor (unsigned i = 0; i < active_output_count; i++) {\n"
        "\t\t\trotor_velocity_message.add_velocity(0);\n"
        "\t\t}",
    ),
    Path.home() / "Documents/PX4-Autopilot/src/modules/simulation/gz_bridge/GZMixingInterfaceWheel.cpp": (
        "\t\twheel_velocity_message.mutable_velocity()->Resize(active_output_count, 0);",
        "\t\tfor (unsigned i = 0; i < active_output_count; i++) {\n"
        "\t\t\twheel_velocity_message.add_velocity(0);\n"
        "\t\t}",
    ),
}

for path, (old, new) in replacements.items():
    text = path.read_text()
    if old not in text:
        print(f"Already patched or pattern missing: {path}")
        continue
    path.write_text(text.replace(old, new))
    print(f"Patched {path}")
PY
```

Then rebuild:

```bash
cd "$HOME/Documents/PX4-Autopilot"
source "$HOME/Documents/PX4-Autopilot/.venv/bin/activate"
make px4_sitl gz_x500
```

### `Timed out waiting for Gazebo world`

This means PX4 started, but Gazebo did not create the world before PX4 gave up. Start Gazebo and PX4 separately.

Terminal 1:

```bash
cd "$HOME/Documents/PX4-Autopilot/Tools/simulation/gz"
python3 simulation-gazebo --world default --gz_ip 127.0.0.1
```

Wait for Gazebo to open and load the world.

Terminal 2:

```bash
cd "$HOME/Documents/PX4-Autopilot"
source "$HOME/Documents/PX4-Autopilot/.venv/bin/activate"
PX4_GZ_STANDALONE=1 GZ_IP=127.0.0.1 make px4_sitl gz_x500
```

The helper scripts in this repo do the same thing:

```bash
./scripts/run_gazebo_world.sh
./scripts/run_px4_standalone.sh
```

For wind testing, start the windy world instead:

```bash
./scripts/run_windy_gazebo_world.sh
```

## Connect This Dashboard

In a second terminal:

```bash
cd "$HOME/Documents/autonomous drone"
python3 server.py
```

Open:

```text
http://localhost:8000
```

At first, the dashboard still uses its local simulated data. The next engineering step is to replace that local data source with PX4 telemetry from MAVLink/ROS 2.

## Recommended Portfolio Milestones

1. PX4 X500 takes off, hovers, lands in Gazebo.
2. Add wind and show the autopilot holding position.
3. Add a waypoint mission and show path tracking.
4. Add a simulated camera view.
5. Run detection on simulated camera frames.
6. Send detection alerts to this dashboard.
7. Add failure tests: low battery, link loss, GPS degradation, geofence violation, obstacle stop.
8. Record a polished demo video with dashboard + Gazebo side by side.

## If macOS Becomes Painful

PX4 supports macOS, but robotics stacks are usually smoothest on Ubuntu. If Gazebo or ROS 2 dependency issues get annoying, use:

- Ubuntu 22.04/24.04 on a dedicated machine
- Ubuntu VM
- Docker-based PX4 development container

The portfolio result is the same: professional SITL simulation, reproducible tests, and a clean dashboard.
