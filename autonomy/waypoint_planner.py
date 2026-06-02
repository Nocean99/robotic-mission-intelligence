from __future__ import annotations

import math
from dataclasses import dataclass

from autonomy.types import MissionConfig, Position, Waypoint


@dataclass
class WaypointProgress:
    index: int = 0
    hold_started_at: float | None = None
    waypoint_started_at: float | None = None
    complete: bool = False
    timed_out: bool = False


class WaypointPlanner:
    def __init__(self, config: MissionConfig) -> None:
        self.config = config
        self.progress = WaypointProgress()
        self.validate_waypoints(config.waypoints)

    def validate_waypoints(self, waypoints: list[Waypoint]) -> None:
        if not waypoints:
            raise ValueError("Mission requires at least one waypoint")
        for index, waypoint in enumerate(waypoints):
            altitude = -waypoint.z
            if waypoint.z > 0:
                raise ValueError(f"Waypoint {index} z must use PX4 NED coordinates; altitude 5 m is z=-5.0")
            if altitude > self.config.max_altitude_m:
                raise ValueError(f"Waypoint {index} exceeds max altitude: {altitude:.1f} m")
            radius = math.hypot(waypoint.x, waypoint.y)
            if radius > self.config.max_distance_from_home_m:
                raise ValueError(f"Waypoint {index} exceeds max radius: {radius:.1f} m")
            if waypoint.hold_time_s < 0:
                raise ValueError(f"Waypoint {index} hold time cannot be negative")

    @property
    def active_index(self) -> int | None:
        return None if self.progress.complete else self.progress.index

    def reset(self, now_s: float) -> None:
        self.progress = WaypointProgress(index=0, waypoint_started_at=now_s)

    def active_waypoint(self) -> Waypoint | None:
        if self.progress.complete:
            return None
        return self.config.waypoints[self.progress.index]

    def reached(self, position: Position, waypoint: Waypoint) -> bool:
        distance = math.sqrt(
            (position.x - waypoint.x) ** 2
            + (position.y - waypoint.y) ** 2
            + (position.z - waypoint.z) ** 2
        )
        yaw_error = abs(_wrap_angle(position.yaw - waypoint.yaw))
        return distance <= self.config.waypoint_tolerance_m and yaw_error <= self.config.yaw_tolerance_rad

    def target_setpoint(self, position: Position, now_s: float, dt_s: float) -> Position | None:
        waypoint = self.active_waypoint()
        if waypoint is None:
            return None
        if self.progress.waypoint_started_at is None:
            self.progress.waypoint_started_at = now_s

        elapsed = now_s - self.progress.waypoint_started_at
        if elapsed > self.config.waypoint_timeout_s:
            self.progress.timed_out = True
            return waypoint

        if self.reached(position, waypoint):
            if self.progress.hold_started_at is None:
                self.progress.hold_started_at = now_s
            if now_s - self.progress.hold_started_at >= waypoint.hold_time_s:
                self._advance(now_s)
            return waypoint

        self.progress.hold_started_at = None
        return interpolate_position(position, waypoint, self.config.cruise_speed_mps, dt_s)

    def _advance(self, now_s: float) -> None:
        self.progress.index += 1
        self.progress.hold_started_at = None
        self.progress.waypoint_started_at = now_s
        if self.progress.index >= len(self.config.waypoints):
            self.progress.complete = True


def interpolate_position(current: Position, target: Position, speed_mps: float, dt_s: float) -> Position:
    dx = target.x - current.x
    dy = target.y - current.y
    dz = target.z - current.z
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance <= 1e-6:
        return Position(target.x, target.y, target.z, target.yaw)
    step = min(distance, max(0.01, speed_mps * dt_s))
    ratio = step / distance
    yaw_step = _wrap_angle(target.yaw - current.yaw)
    return Position(
        x=current.x + dx * ratio,
        y=current.y + dy * ratio,
        z=current.z + dz * ratio,
        yaw=current.yaw + yaw_step * min(1.0, ratio),
    )


def _wrap_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

