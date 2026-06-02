from __future__ import annotations

import math

from autonomy.types import MissionConfig, Position, SafetyAction, SafetyStatus


class SafetyMonitor:
    def __init__(self, config: MissionConfig) -> None:
        self.config = config
        self.emergency_stop = False
        self.battery_low_placeholder = False

    def trigger_emergency_stop(self) -> None:
        self.emergency_stop = True

    def clear_emergency_stop(self) -> None:
        self.emergency_stop = False

    def check(
        self,
        *,
        position: Position | None,
        home: Position | None,
        local_position_valid: bool,
        is_offboard: bool,
        mission_requires_offboard: bool,
        waypoint_timed_out: bool,
    ) -> SafetyStatus:
        if self.emergency_stop:
            return SafetyStatus(SafetyAction.EMERGENCY_LAND, "Emergency stop flag set")
        if not local_position_valid or position is None:
            return SafetyStatus(SafetyAction.LAND_NOW, "Missing or invalid local position")
        if -position.z > self.config.max_altitude_m:
            return SafetyStatus(SafetyAction.LAND_NOW, "Altitude limit exceeded")
        if home is not None:
            distance = math.hypot(position.x - home.x, position.y - home.y)
            if distance > self.config.max_distance_from_home_m:
                return SafetyStatus(SafetyAction.RETURN_HOME, "Maximum distance from home exceeded")
        if waypoint_timed_out:
            return SafetyStatus(SafetyAction.RETURN_HOME, "Waypoint timeout")
        if mission_requires_offboard and not is_offboard:
            return SafetyStatus(SafetyAction.RETURN_HOME, "Offboard mode lost")
        if self.battery_low_placeholder:
            return SafetyStatus(SafetyAction.RETURN_HOME, "Battery placeholder low")
        return SafetyStatus()

