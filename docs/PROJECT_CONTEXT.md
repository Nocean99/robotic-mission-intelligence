# Project Context

## Current Direction

This project is now a mission intelligence layer for robotic and sensor systems.

The original proving ground is an autonomous drone simulation, but the product direction is broader than a drone. The goal is to convert high-level mission requests into structured search behavior, sensor collection, perception results, candidate prioritization, analyst review, and mission reports.

Current framing:

```text
Mission Request
  -> Mission Planning
  -> Sensor Collection
  -> Proposal Detection
  -> Semantic Scoring
  -> Candidate Prioritization
  -> Human Review
  -> Mission Report
```

PX4, Gazebo, cameras, videos, dashboards, and future acoustic or telemetry sources are integration points. They should not become the center of the architecture.

## Current Repository

Current local path:

```text
/Users/noah/Documents/autonomous drone
```

Current GitHub repo:

```text
https://github.com/Nocean99/autonomous-drone
```

Planned repo rename:

```text
mission-intelligence-layer
```

The repo should not include `NOCEAN99_PROFILE_README.md`. That file belongs in a separate GitHub profile repository named:

```text
Nocean99/Nocean99
```

## What Exists

Core simulation:

- Lightweight dashboard sim at `http://localhost:8000`
- Headless scenario tests for takeoff, patrol, return-home, abort, manual override, wind, and detection injection
- JSON/CSV logs under `logs/`

PX4/Gazebo track:

- PX4 SITL helper scripts
- Gazebo red-block world scripts
- Camera bridge/debug scripts
- ROS 2 environment checks
- Docker ROS 2 helper scripts

Autonomy stack:

- `PX4ControllerInterface`
- `MissionManager`
- `WaypointPlanner`
- `SafetyMonitor`
- `MissionLogger`
- `SearchMissionManager`
- `WorldModel`
- mission command parsing and operating modes

Vision/perception:

- classical red-block detector
- mission-color proposal detector
- objectness proposal detector
- semantic vision scoring interface
- optional provider-backed vision-language scoring backend
- image/video benchmark runner
- labeled evaluation with precision, recall, F1, false positives, and false negatives

Analyst workflow:

- analyst dashboard at `http://localhost:8010`
- saved report browser
- candidate images
- metrics
- approve/reject/investigate review states
- `candidate_reviews.json` saved beside each report

## Important Design Decisions

- The mission intelligence layer is the product.
- Drones are one sensor platform, not the product itself.
- High-level mission logic must not publish PX4 messages directly.
- PX4 handles low-level stabilization and flight control.
- Perception scoring does not directly control a vehicle.
- Human review is part of the intended workflow for search-and-rescue style use cases.
- Simulation and offline benchmarks should be preferred over heavy live sim runs when possible on this MacBook.
- Keep public repo wording professional: "semantic vision", "mission intelligence", "analyst workflow", "robotic systems". Avoid making the repo look like a generic AI wrapper.

## Current Known Constraints

- Codex can edit project files but currently cannot write inside `.git`, so Codex cannot locally stage/commit/push.
- Git commits must be run from Noah's normal Terminal for now.
- Shell network access from Codex is restricted.
- Full PX4/Gazebo/ROS 2 runs are heavy on this MacBook.
- Docker ROS 2 works for environment checks, but macOS Docker networking has limitations for native Gazebo Transport discovery.

## Common Commands

Run quick dashboard:

```bash
python3 server.py
```

Run fast sim tests:

```bash
./scripts/run_fast_sim_tests.sh
```

Run core tests:

```bash
python3 tests/test_autonomy_stack.py
python3 tests/test_search_mission.py
python3 tests/test_world_model.py
```

Run all lightweight tests:

```bash
for test_file in tests/test_*.py; do python3 "$test_file"; done
```

Run vision-only benchmark:

```bash
./scripts/test_vision_only.sh "/path/to/images" \
  --mission-request "Search this image set for the responder's described target"
```

Run analyst dashboard:

```bash
./scripts/run_analyst_dashboard.sh
```

Commit current development batch from Terminal:

```bash
cd "/Users/noah/Documents/autonomous drone"
git status
git add <changed files>
git commit -m "Short focused commit message"
git push
```

## Recommended Next Work

Near-term:

1. Improve the analyst dashboard as the main product surface.
2. Add a mission creation workflow from plain-English request to structured mission plan.
3. Improve semantic scoring evaluation on labeled image folders.
4. Add report generation for completed missions.
5. Keep PX4/Gazebo as a validation track, not the main bottleneck.

Medium-term:

1. Rename the repo to `mission-intelligence-layer`.
2. Add a clean sensor abstraction layer:
   - image folder
   - video
   - live camera
   - drone camera
   - future acoustic source
3. Add richer candidate review state and mission reporting.
4. Add provider-backed semantic vision tests with a small labeled benchmark.
5. Improve docs and portfolio-facing screenshots.

Do not prioritize yet:

- obstacle avoidance
- multi-drone coordination
- real hardware flight
- weaponized or military-specific behavior
- complex ML training pipelines

## Handoff Note For A New Chat

If starting a new Codex chat, say:

```text
Read /Users/noah/Documents/autonomous drone/docs/PROJECT_CONTEXT.md and continue development from there.
Focus on the mission intelligence platform direction, not just the drone simulator.
```

Then ask the new chat to inspect the current repo before editing.
