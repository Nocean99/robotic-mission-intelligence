# Architecture

## Current Prototype

```text
Browser dashboard
  -> local HTTP API
  -> Python simulation model
  -> local JSONL logs
```

This is useful for UI, mission-state, safety-rule, and operator-workflow testing.

## Professional SITL Target

```text
Browser dashboard
  -> telemetry/command bridge
  -> MAVLink or ROS 2
  -> PX4 SITL
  -> Gazebo X500 vehicle
  -> simulated IMU, GPS, battery, camera, lidar/depth, wind
```

## Responsibilities

Dashboard:

- Operator controls
- Mission status
- Alerts
- Health panel
- Logs and review

Autonomy layer:

- Waypoint mission policy
- Geofence policy
- Obstacle decision logic
- Perception event filtering
- Return-to-home decisions

Autopilot:

- Attitude stabilization
- Motor control
- Position hold
- Navigation primitives
- Failsafe execution

Simulator:

- Vehicle physics
- Wind and disturbances
- 3D environment
- Camera/depth/lidar feeds
- Sensor noise

## Integration Rule

Keep low-level stabilization in PX4. Keep high-level mission policy in your autonomy code. This is the professional separation of concerns.
