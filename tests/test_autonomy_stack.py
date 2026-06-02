from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.config_loader import load_mission_config
from autonomy.mission_manager import MissionManager
from autonomy.safety_monitor import SafetyMonitor
from autonomy.types import MissionState, Position, SafetyAction, VehicleStatusSnapshot
from autonomy.waypoint_planner import WaypointPlanner


class MockController:
    ARMING_STATE_ARMED = 2
    NAVIGATION_STATE_OFFBOARD = 14

    def __init__(self) -> None:
        self.position = Position(0.0, 0.0, 0.0, 0.0)
        self.status = VehicleStatusSnapshot(arming_state=0, nav_state=0, connected=True)
        self.local_position_valid = True
        self.commands: list[str] = []
        self.setpoints: list[Position] = []

    def arm(self) -> None:
        self.commands.append("arm")
        self.status.arming_state = self.ARMING_STATE_ARMED

    def disarm(self) -> None:
        self.commands.append("disarm")
        self.status.arming_state = 0

    def set_offboard_mode(self) -> None:
        self.commands.append("offboard")
        self.status.nav_state = self.NAVIGATION_STATE_OFFBOARD

    def land(self) -> None:
        self.commands.append("land")

    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float) -> None:
        self.setpoints.append(Position(x, y, z, yaw))

    def get_position(self) -> Position | None:
        return self.position

    def get_vehicle_status(self) -> VehicleStatusSnapshot:
        return self.status

    def is_armed(self) -> bool:
        return self.status.arming_state == self.ARMING_STATE_ARMED

    def is_offboard(self) -> bool:
        return self.status.nav_state == self.NAVIGATION_STATE_OFFBOARD

    def has_valid_local_position(self) -> bool:
        return self.local_position_valid

    def move_toward_last_setpoint(self, step: float = 0.8) -> None:
        if not self.setpoints:
            return
        target = self.setpoints[-1]
        dx = target.x - self.position.x
        dy = target.y - self.position.y
        dz = target.z - self.position.z
        distance = (dx * dx + dy * dy + dz * dz) ** 0.5
        if distance <= step or distance == 0:
            self.position = target
            return
        ratio = step / distance
        self.position = Position(
            self.position.x + dx * ratio,
            self.position.y + dy * ratio,
            self.position.z + dz * ratio,
            target.yaw,
        )


def test_valid_waypoint_loading() -> None:
    config = load_mission_config("config/autonomy.yaml")
    assert config.takeoff_altitude_m == 5.0
    assert len(config.waypoints) == 3
    assert config.waypoints[0].z == -5.0


def test_invalid_waypoint_rejection() -> None:
    with TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "bad.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "takeoff_altitude_m: 5.0",
                    "hover_time_s: 3.0",
                    "control_rate_hz: 20",
                    "waypoint_tolerance_m: 0.5",
                    "yaw_tolerance_rad: 0.2",
                    "max_altitude_m: 4.0",
                    "max_distance_from_home_m: 50.0",
                    "waypoint_timeout_s: 30.0",
                    "return_home_altitude_m: 5.0",
                    "cruise_speed_mps: 2.0",
                    "waypoints:",
                    "  - {x: 0.0, y: 0.0, z: -5.0, yaw: 0.0, hold_time_s: 1.0}",
                ]
            )
        )
        config = load_mission_config(config_path)
        try:
            WaypointPlanner(config)
        except ValueError as exc:
            assert "exceeds max altitude" in str(exc)
        else:
            raise AssertionError("Expected invalid waypoint rejection")


def test_state_machine_transitions_to_takeoff() -> None:
    config = load_mission_config("config/autonomy.yaml")
    controller = MockController()
    manager = MissionManager(controller=controller, config=config)
    manager.start(now_s=0.0)
    for i in range(20):
        manager.tick(now_s=i / config.control_rate_hz, dt_s=1 / config.control_rate_hz)
    assert "offboard" in controller.commands
    assert "arm" in controller.commands
    assert manager.state == MissionState.TAKEOFF
    assert len(controller.setpoints) >= 10


def test_safety_max_altitude_trigger() -> None:
    config = load_mission_config("config/autonomy.yaml")
    monitor = SafetyMonitor(config)
    status = monitor.check(
        position=Position(0, 0, -25, 0),
        home=Position(0, 0, 0, 0),
        local_position_valid=True,
        is_offboard=True,
        mission_requires_offboard=True,
        waypoint_timed_out=False,
    )
    assert status.action == SafetyAction.LAND_NOW


def test_safety_max_distance_trigger() -> None:
    config = load_mission_config("config/autonomy.yaml")
    monitor = SafetyMonitor(config)
    status = monitor.check(
        position=Position(80, 0, -5, 0),
        home=Position(0, 0, 0, 0),
        local_position_valid=True,
        is_offboard=True,
        mission_requires_offboard=True,
        waypoint_timed_out=False,
    )
    assert status.action == SafetyAction.RETURN_HOME


def test_waypoint_reached_logic() -> None:
    config = load_mission_config("config/autonomy.yaml")
    planner = WaypointPlanner(config)
    waypoint = config.waypoints[0]
    assert planner.reached(Position(5.1, 0.0, -5.0, 0.0), waypoint)
    assert not planner.reached(Position(7.0, 0.0, -5.0, 0.0), waypoint)


def test_return_home_trigger_from_waypoint_timeout() -> None:
    config = load_mission_config("config/autonomy.yaml")
    controller = MockController()
    manager = MissionManager(controller=controller, config=config)
    manager.start(now_s=0.0)
    for i in range(20):
        manager.tick(now_s=i / config.control_rate_hz, dt_s=1 / config.control_rate_hz)
    controller.position = Position(10, 0, -5, 0)
    manager.state = MissionState.MISSION
    manager.home = Position(0, 0, 0, 0)
    manager.planner.reset(0.0)
    manager.planner.progress.timed_out = True
    manager.tick(now_s=40.0, dt_s=1 / config.control_rate_hz)
    assert manager.state == MissionState.RETURN_HOME


def test_emergency_landing_trigger() -> None:
    config = load_mission_config("config/autonomy.yaml")
    controller = MockController()
    manager = MissionManager(controller=controller, config=config)
    manager.start(now_s=0.0)
    manager.safety_monitor.trigger_emergency_stop()
    manager.tick(now_s=1.0, dt_s=1 / config.control_rate_hz)
    assert manager.state == MissionState.EMERGENCY
    assert "land" in controller.commands


if __name__ == "__main__":
    tests = [
        test_valid_waypoint_loading,
        test_invalid_waypoint_rejection,
        test_state_machine_transitions_to_takeoff,
        test_safety_max_altitude_trigger,
        test_safety_max_distance_trigger,
        test_waypoint_reached_logic,
        test_return_home_trigger_from_waypoint_timeout,
        test_emergency_landing_trigger,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
