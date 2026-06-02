from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Protocol

from autonomy.mission_logger import MissionLogger
from autonomy.safety_monitor import SafetyMonitor
from autonomy.types import MissionConfig, MissionLogRow, MissionState, Position, SafetyAction, SafetyStatus
from autonomy.types import VehicleStatusSnapshot
from autonomy.waypoint_planner import WaypointPlanner, interpolate_position


LOGGER = logging.getLogger(__name__)


class ControllerProtocol(Protocol):
    def arm(self) -> None: ...
    def disarm(self) -> None: ...
    def set_offboard_mode(self) -> None: ...
    def land(self) -> None: ...
    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float) -> None: ...
    def get_position(self) -> Position | None: ...
    def get_vehicle_status(self) -> VehicleStatusSnapshot: ...
    def is_armed(self) -> bool: ...
    def is_offboard(self) -> bool: ...
    def has_valid_local_position(self) -> bool: ...


class MissionManager:
    def __init__(
        self,
        *,
        controller: ControllerProtocol,
        config: MissionConfig,
        planner: WaypointPlanner | None = None,
        safety_monitor: SafetyMonitor | None = None,
        mission_logger: MissionLogger | None = None,
    ) -> None:
        self.controller = controller
        self.config = config
        self.planner = planner or WaypointPlanner(config)
        self.safety_monitor = safety_monitor or SafetyMonitor(config)
        self.logger = mission_logger
        self.state = MissionState.IDLE
        self.home: Position | None = None
        self.current_target: Position | None = None
        self.state_entered_at = 0.0
        self.offboard_setpoint_count = 0
        self.last_safety_status = SafetyStatus()
        self._offboard_command_sent = False
        self._arm_command_sent = False
        self._land_command_sent = False

    def start(self, now_s: float | None = None) -> None:
        self._transition(MissionState.PRE_FLIGHT_CHECK, now_s or time.monotonic(), "Mission start requested")

    def tick(self, now_s: float | None = None, dt_s: float | None = None) -> MissionState:
        now = now_s if now_s is not None else time.monotonic()
        dt = dt_s if dt_s is not None else 1.0 / self.config.control_rate_hz
        position = self.controller.get_position()
        status = self.controller.get_vehicle_status()
        requires_offboard = self.state in {
            MissionState.ARMING,
            MissionState.TAKEOFF,
            MissionState.HOVER,
            MissionState.MISSION,
            MissionState.RETURN_HOME,
        }
        self.last_safety_status = self.safety_monitor.check(
            position=position,
            home=self.home,
            local_position_valid=self.controller.has_valid_local_position(),
            is_offboard=self.controller.is_offboard(),
            mission_requires_offboard=requires_offboard and self.offboard_setpoint_count > self.config.control_rate_hz,
            waypoint_timed_out=self.planner.progress.timed_out,
        )
        self._apply_safety(now, self.last_safety_status)

        if self.state == MissionState.PRE_FLIGHT_CHECK:
            self._preflight(now, position)
        elif self.state == MissionState.ARMING:
            self._arming(now, position)
        elif self.state == MissionState.TAKEOFF:
            self._takeoff(now, position, dt)
        elif self.state == MissionState.HOVER:
            self._hover(now)
        elif self.state == MissionState.MISSION:
            self._mission(now, position, dt)
        elif self.state == MissionState.RETURN_HOME:
            self._return_home(now, position, dt)
        elif self.state == MissionState.LANDING:
            self._landing(now, position)
        elif self.state == MissionState.EMERGENCY:
            self._emergency()

        self._publish_current_target()
        self._write_log(status)
        return self.state

    def _preflight(self, now_s: float, position: Position | None) -> None:
        if position is None or not self.controller.has_valid_local_position():
            LOGGER.info("Waiting for valid local position")
            return
        self.home = position
        takeoff_z = -abs(self.config.takeoff_altitude_m)
        self.current_target = Position(position.x, position.y, takeoff_z, position.yaw)
        self.offboard_setpoint_count = 0
        self._transition(MissionState.ARMING, now_s, "Local position valid; home stored")

    def _arming(self, now_s: float, position: Position | None) -> None:
        if self.current_target is None:
            return
        self.offboard_setpoint_count += 1
        warmup_required = max(10, int(self.config.control_rate_hz * 0.6))
        if self.offboard_setpoint_count < warmup_required:
            return
        if not self._offboard_command_sent:
            self.controller.set_offboard_mode()
            self._offboard_command_sent = True
        if not self._arm_command_sent:
            self.controller.arm()
            self._arm_command_sent = True
        if self.controller.is_armed() and self.controller.is_offboard():
            self._transition(MissionState.TAKEOFF, now_s, "PX4 armed and Offboard active")

    def _takeoff(self, now_s: float, position: Position | None, dt_s: float) -> None:
        if position is None or self.current_target is None:
            return
        self.current_target = interpolate_position(position, self.current_target, self.config.cruise_speed_mps, dt_s)
        if abs(position.z - (-abs(self.config.takeoff_altitude_m))) <= self.config.waypoint_tolerance_m:
            self._transition(MissionState.HOVER, now_s, "Takeoff altitude reached")

    def _hover(self, now_s: float) -> None:
        if now_s - self.state_entered_at >= self.config.hover_time_s:
            self.planner.reset(now_s)
            self._transition(MissionState.MISSION, now_s, "Hover complete; starting waypoint mission")

    def _mission(self, now_s: float, position: Position | None, dt_s: float) -> None:
        if position is None:
            return
        target = self.planner.target_setpoint(position, now_s, dt_s)
        if target is None:
            self._transition(MissionState.RETURN_HOME, now_s, "Waypoint mission complete")
            return
        self.current_target = target

    def _return_home(self, now_s: float, position: Position | None, dt_s: float) -> None:
        if position is None or self.home is None:
            self._transition(MissionState.LANDING, now_s, "No home/position; landing")
            return
        target = Position(self.home.x, self.home.y, -abs(self.config.return_home_altitude_m), self.home.yaw)
        self.current_target = interpolate_position(position, target, self.config.cruise_speed_mps, dt_s)
        distance_xy = math.hypot(position.x - self.home.x, position.y - self.home.y)
        if distance_xy <= self.config.waypoint_tolerance_m:
            self._transition(MissionState.LANDING, now_s, "Home reached")

    def _landing(self, now_s: float, position: Position | None) -> None:
        if not self._land_command_sent:
            self.controller.land()
            self._land_command_sent = True
        if position is not None and position.altitude_m <= 0.25:
            if self.controller.is_armed():
                self.controller.disarm()
            self._transition(MissionState.LANDED, now_s, "Landing complete")

    def _emergency(self) -> None:
        if not self._land_command_sent:
            self.controller.land()
            self._land_command_sent = True

    def _apply_safety(self, now_s: float, safety_status: SafetyStatus) -> None:
        if safety_status.action == SafetyAction.NONE:
            return
        LOGGER.warning("Safety action %s: %s", safety_status.action.value, safety_status.reason)
        if safety_status.action == SafetyAction.RETURN_HOME and self.state not in {MissionState.RETURN_HOME, MissionState.LANDING, MissionState.LANDED}:
            self._transition(MissionState.RETURN_HOME, now_s, safety_status.reason)
        elif safety_status.action == SafetyAction.LAND_NOW and self.state not in {MissionState.LANDING, MissionState.LANDED}:
            self._transition(MissionState.LANDING, now_s, safety_status.reason)
        elif safety_status.action == SafetyAction.EMERGENCY_LAND and self.state != MissionState.EMERGENCY:
            self._transition(MissionState.EMERGENCY, now_s, safety_status.reason)

    def _publish_current_target(self) -> None:
        if self.current_target is None:
            return
        if self.state in {MissionState.ARMING, MissionState.TAKEOFF, MissionState.HOVER, MissionState.MISSION, MissionState.RETURN_HOME}:
            self.controller.publish_position_setpoint(
                self.current_target.x,
                self.current_target.y,
                self.current_target.z,
                self.current_target.yaw,
            )

    def _transition(self, new_state: MissionState, now_s: float, reason: str) -> None:
        if self.state == new_state:
            return
        LOGGER.info("Mission transition: %s -> %s (%s)", self.state.value, new_state.value, reason)
        self.state = new_state
        self.state_entered_at = now_s
        if new_state in {MissionState.LANDING, MissionState.EMERGENCY}:
            self._land_command_sent = False

    def _write_log(self, status: VehicleStatusSnapshot) -> None:
        if self.logger is None:
            return
        position = self.controller.get_position()
        target = self.current_target
        self.logger.write(
            MissionLogRow(
                timestamp=datetime.now(timezone.utc).isoformat(),
                mission_state=self.state.value,
                x=None if position is None else position.x,
                y=None if position is None else position.y,
                z=None if position is None else position.z,
                yaw=None if position is None else position.yaw,
                target_x=None if target is None else target.x,
                target_y=None if target is None else target.y,
                target_z=None if target is None else target.z,
                target_yaw=None if target is None else target.yaw,
                active_waypoint_index=self.planner.active_index,
                safety_action=self.last_safety_status.action.value,
                safety_reason=self.last_safety_status.reason,
                nav_state=status.nav_state,
                arming_state=status.arming_state,
            )
        )

