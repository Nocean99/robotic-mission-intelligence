# Portfolio Simulation Test Plan

This is the professional story to show in a co-op portfolio: not just "a drone demo," but a safety-first autonomy validation workflow.

## Project Claim

Autonomous site-monitoring drone simulation with PX4/Gazebo SITL, mission dashboard, safety states, perception alerts, and failure-mode testing.

## Demo Structure

### 1. Baseline Mission

Goal: prove the vehicle can complete a normal patrol.

Checklist:

- Arm/takeoff in simulation.
- Climb to patrol altitude.
- Visit predefined waypoints.
- Stream mission state to dashboard.
- Return home and land.
- Save logs.

Success criteria:

- No geofence violation.
- No unsafe altitude behavior.
- Dashboard state matches simulation state.

### 2. Wind Rejection

Goal: prove the autopilot can stabilize under wind and the autonomy layer reacts when wind is too high.

Checklist:

- Run same route in calm conditions.
- Add moderate wind.
- Add gusting wind.
- Observe roll/pitch compensation.
- Trigger return-to-home when wind exceeds mission limit.

Success criteria:

- Vehicle remains stable in moderate wind.
- Mission aborts or returns home under unsafe wind.
- Dashboard records the safety trigger.

### 3. Camera Perception Reaction

Goal: prove camera events affect mission awareness.

Checklist:

- Use simulated camera or replayed video.
- Detect person, vehicle, drone-like object, and unknown object.
- Log detection class, confidence, time, and location.
- Display alert on dashboard.

Success criteria:

- No detection silently disappears.
- Alerts contain timestamp and location.
- Unknown/drone-like objects create higher-priority warnings.

### 4. Geofence Test

Goal: prove the drone refuses to leave the operating area.

Checklist:

- Define a geofence.
- Command a waypoint outside the fence.
- Verify mission refuses or reroutes.
- Trigger return-to-home if position drifts outside.

Success criteria:

- Vehicle never intentionally flies outside permitted zone.
- Dashboard shows the geofence event.

### 5. Human Override

Goal: prove autonomy can be interrupted by a human.

Checklist:

- Start autonomous patrol.
- Trigger manual override.
- Confirm autonomy stops issuing movement commands.
- Trigger return-to-home or resume.

Success criteria:

- Manual override always wins.
- Dashboard clearly shows override state.

### 6. Failure Handling

Goal: prove the system fails safely.

Checklist:

- Low battery.
- Link degradation.
- GPS quality drop.
- Obstacle detected.
- Emergency abort.

Success criteria:

- Low battery triggers return-to-home.
- Critical battery triggers landing.
- GPS loss causes hold or safe mode.
- Obstacle causes slow/hold/reroute.
- Abort state is immediate and visible.

## Portfolio Artifacts To Capture

- Architecture diagram.
- SITL launch instructions.
- Test matrix with pass/fail results.
- Screenshots of Gazebo + dashboard.
- Short demo video.
- Log files from successful and failed missions.
- Explanation of safety choices.

## Resume Bullet Drafts

- Built a PX4/Gazebo software-in-the-loop UAV simulation with autonomous waypoint patrol, return-to-home, geofence enforcement, and dashboard telemetry.
- Developed safety-state logic for low battery, signal degradation, GPS quality loss, obstacle detection, emergency abort, and manual override.
- Designed a browser-based mission control dashboard for live vehicle status, alerts, health monitoring, flight logs, and operator commands.
- Created a simulation validation plan covering wind disturbance, perception events, geofence violations, and failure-mode handling.
