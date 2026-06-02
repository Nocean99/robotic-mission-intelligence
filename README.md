# Autonomous Site-Monitoring Drone MVP

This workspace contains a simulation-first prototype for an autonomous site-monitoring drone. It is not flight-control firmware and should not be connected to real motors. The goal is to prove mission logic, safety behavior, perception events, telemetry, and dashboard workflows before moving to PX4/ArduPilot, ROS 2, and a real simulator.

## What This MVP Includes

- Simulated drone state: position, altitude, battery, link quality, GPS quality, vibration, temperature, mission phase
- Autonomous takeoff, waypoint patrol, return-to-home, and landing
- Geofence checks
- Emergency stop and manual override commands
- Low-battery and signal-loss return-to-home triggers
- Obstacle and anomaly simulation
- Object/anomaly event logging with timestamp and location
- Browser dashboard with map, live simulated camera, mission status, health, alerts, abort, RTH, and manual override controls
- JSON flight logs written to `logs/`

## Run It

```bash
python3 server.py
```

Then open:

```text
http://localhost:8000
```

## Fast Headless Scenario Tests

To evaluate simulator behavior without the live dashboard:

```bash
./scripts/run_fast_sim_tests.sh
```

This runs takeoff/patrol, return-home, abort, manual override, high-wind return, and detection-injection scenarios. Reports are saved to `logs/sim_scenarios_<timestamp>.json` and `.csv`.

## API

- `GET /api/state` returns the latest drone state and recent events.
- `POST /api/command` accepts:
  - `{"command": "start"}`
  - `{"command": "pause"}`
  - `{"command": "rth"}`
  - `{"command": "abort"}`
  - `{"command": "manual_override", "enabled": true}`
  - `{"command": "manual_override", "enabled": false}`

## Current Architecture

```text
Dashboard
   |
HTTP API
   |
Simulation Engine
   |
Mission Controller + Safety Monitor + Perception Stub + Flight Logger
```

## Recommended Next Integration Steps

1. Replace the simulated movement layer with PX4 SITL or ArduPilot SITL.
2. Add ROS 2 nodes for mission control, safety monitoring, perception, and telemetry.
3. Bridge simulator telemetry into this dashboard API.
4. Replace simulated detections with camera frames and an OpenCV/YOLO-style detector.
5. Add authentication, audit logs, encrypted command transport, and Remote ID/compliance checks before any field testing.

## PX4/Gazebo Track

For professional real simulation, use the PX4/Gazebo setup guide:

- `docs/PX4_GAZEBO_SETUP.md`
- `docs/ARCHITECTURE.md`
- `docs/PORTFOLIO_TEST_PLAN.md`
- `docs/AUTONOMY_STACK.md`
- `docs/DOCKER_ROS2.md`

Useful helper scripts:

```bash
./scripts/check_px4_env.sh
./scripts/run_px4_gazebo.sh
./scripts/run_gazebo_world.sh
./scripts/run_windy_gazebo_world.sh
./scripts/run_px4_standalone.sh
./scripts/run_dashboard.sh
./scripts/run_uxrce_agent.sh
./scripts/run_autonomy_node.sh
./scripts/run_visual_debugger.sh
./scripts/run_search_mission.sh
./scripts/run_red_block_world.sh
./scripts/run_red_block_gui.sh
./scripts/run_px4_camera_standalone.sh
./scripts/check_ros2_env.sh
./scripts/start_camera_bridge.sh
./scripts/verify_camera_feed.sh
./scripts/run_camera_bridge.sh
./scripts/debug_camera_frame.sh
./scripts/list_camera_topics.sh
./scripts/export_world_model_demo.sh
./scripts/docker_build_ros2.sh
./scripts/docker_shell_ros2.sh
./scripts/docker_check_ros2.sh
```

## Autonomy Stack

The new autonomy layer is in `autonomy/`:

- `PX4ControllerInterface`: ROS 2/PX4 Offboard wrapper
- `MissionManager`: state machine
- `WaypointPlanner`: validated waypoint mission and interpolation
- `SafetyMonitor`: safety checks and responses
- `MissionLogger`: structured CSV logs

Mission config lives at:

```text
config/autonomy.yaml
```

Run core tests without ROS 2:

```bash
python3 tests/test_autonomy_stack.py
python3 tests/test_search_mission.py
```

Search-and-detect mode uses classical OpenCV HSV thresholding to find a red block in the simulated camera feed. Configure it in `config/autonomy.yaml` under `target`, `search`, and `approach`.

The search mission also maintains an internal grid-based `WorldModel` for searched cells, target confidence, placeholder obstacle/risk scores, safety zones, JSON snapshots, and heatmap images.

Search mission run modes:

```bash
python3 -m autonomy.search_mission --run-mode perception-only --camera-source gz
python3 -m autonomy.search_mission --run-mode full-px4 --camera-source ros2 --topic /camera/image_raw
python3 -m autonomy.search_mission --run-mode perception-only --camera-source gz --mission-request "Search this area for the described target"
```

Parse a natural-language mission request:

```bash
./scripts/parse_mission_request.sh "Search the shoreline for a possible survivor signal"
```

Plan a full mission command from plain English:

```bash
./scripts/plan_mission_command.sh --mode connected-supervised "Search the shoreline for a possible survivor signal"
./scripts/plan_mission_command.sh --mode autonomous-return-report "Search this area for anything matching the responder description"
```

The command planner keeps the raw user request, extracts broad search hints, chooses candidate-confirmation behavior, and saves report/link-loss policy. `connected-supervised` assumes a live responder can review candidates. `autonomous-return-report` assumes the drone may be disconnected, so it searches within safety limits, returns home, and stores candidates for later review.

Semantic vision is now represented as a candidate scoring layer. The current local scorer is a deterministic placeholder that ranks proposed image regions against the mission request and saves candidate crops. It does not yet identify arbitrary vehicle/boat/person descriptions. The next major perception upgrade is plugging in a real vision-language model to score those saved crops against the responder's plain-English target description.

Test only the vision stack, without PX4/Gazebo/Docker:

```bash
./scripts/test_vision_only.sh path/to/image_or_folder \
  --mission-request "Search this image set for the responder's described target"
```

For large folders, keep the output small:

```bash
./scripts/test_vision_only.sh path/to/image_or_folder \
  --mission-request "Search this image set for red objects that could be relevant to a rescue" \
  --save-only-detections \
  --max-saved-candidates 50
```

The default proposal mode is `mission-color`, which adapts the cheap color proposal scan to the mission text. For example, a blue-boat mission looks for blue regions, while an orange-life-jacket mission looks for orange regions. Use `--proposal-mode high-recall` for broad red-focused scanning, or `--proposal-mode precise` for stricter red-block-style detections.

Preview the generated vision search plan:

```bash
./scripts/plan_vision_search.sh "Search the shoreline for a small blue boat with a white top"
```

Outputs are saved under `logs/vision_lab/<timestamp>/`:

- `vision_report.json`
- `review_shortlist.json`
- annotated debug images
- candidate crop images

The report also includes red-audit metrics for every image, including images that were not accepted as detections. Use `summary.possible_misses` to inspect images that had red pixels but failed the detector filters.

Test a video file without running the drone:

```bash
./scripts/test_vision_only.sh "/path/to/video.mp4" \
  --video \
  --sample-every-s 1.0 \
  --mission-request "Search this video for red objects that could be relevant to a rescue" \
  --save-only-detections
```

The report stores frame indexes and timestamps so detections can be traced back to the source video.

Evaluate specific-object accuracy with labels:

```bash
cp config/vision_labels_template.csv /Users/noah/Desktop/vision_labels.csv
```

Edit the CSV so each row marks whether an image should match the mission:

```csv
image_path,expected_match,label,notes
red_vehicle_01.jpg,true,red_vehicle,clear positive
red_sign_01.jpg,false,not_target,red but not the target
```

Then run:

```bash
./scripts/test_vision_only.sh "/Users/noah/Desktop/vision_test_set" \
  --mission-request "Search these images for the specific target description" \
  --labels-csv "/Users/noah/Desktop/vision_labels.csv" \
  --eval-threshold 0.25 \
  --save-only-detections \
  --max-saved-candidates 50
```

The report will include precision, recall, F1, false positives, and false negatives. This is the realistic way to test whether a future AI vision encoder is actually improving.

Build a visual HTML review page from a report:

```bash
./scripts/build_vision_report_viewer.sh "logs/vision_lab/<timestamp>/vision_report.json"
```

Open the generated `vision_report_viewer.html` to review metrics, false positives, false negatives, and the candidate shortlist.

Optional AI vision encoder path:

```bash
export OPENAI_API_KEY="..."
export OPENAI_VISION_MODEL="your-vision-capable-model"

./scripts/test_vision_only.sh "/Users/noah/Desktop/vision_test_set" \
  --mission-request "Search these images for people who may need rescue" \
  --semantic-vision openai \
  --full-frame-semantic misses \
  --labels-csv "/Users/noah/Desktop/vision_labels.csv" \
  --save-only-detections \
  --max-saved-candidates 50
```

Use `--full-frame-semantic misses` when you want the AI model to inspect full frames only when cheap proposal detectors found nothing. Use `--full-frame-semantic all` for deeper evaluation, but expect it to be slower and more expensive.

## Safety Note

Use this only for simulation and software workflow testing. For hardware, start with bench tests, props-off tests, tethered hover, manual flight, assisted waypoint flight, and only then autonomous patrol in a legal, controlled area with permission.
