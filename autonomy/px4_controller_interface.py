from __future__ import annotations

import logging
from typing import Any

from autonomy.types import Position, VehicleStatusSnapshot


LOGGER = logging.getLogger(__name__)


class PX4ControllerInterface:
    """Clean boundary for PX4 Offboard control.

    This class owns ROS 2 topic publishing/subscribing. Mission code should only
    call this interface and must not publish PX4 messages directly.
    """

    ARMING_STATE_ARMED = 2
    NAVIGATION_STATE_OFFBOARD = 14

    def __init__(self, node_name: str = "autonomy_px4_controller") -> None:
        try:
            import rclpy
            from rclpy.node import Node
            from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
            from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
            from px4_msgs.msg import VehicleLocalPosition, VehicleStatus
        except ImportError as exc:
            raise RuntimeError(
                "ROS 2 PX4 dependencies are missing. Install/source rclpy and px4_msgs, "
                "or use a mock controller for tests."
            ) from exc

        if not rclpy.ok():
            rclpy.init()

        class _Node(Node):
            pass

        self._rclpy = rclpy
        self._msgs = {
            "OffboardControlMode": OffboardControlMode,
            "TrajectorySetpoint": TrajectorySetpoint,
            "VehicleCommand": VehicleCommand,
            "VehicleLocalPosition": VehicleLocalPosition,
            "VehicleStatus": VehicleStatus,
        }
        self.node = _Node(node_name)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._offboard_pub = self.node.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", qos)
        self._trajectory_pub = self.node.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos)
        self._command_pub = self.node.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", qos)
        self.node.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position", self._position_cb, qos)
        self.node.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", self._status_cb, qos)
        self._position: Position | None = None
        self._local_position_valid = False
        self._status = VehicleStatusSnapshot()
        LOGGER.info("PX4ControllerInterface initialized")

    def spin_once(self, timeout_sec: float = 0.0) -> None:
        self._rclpy.spin_once(self.node, timeout_sec=timeout_sec)

    def arm(self) -> None:
        LOGGER.info("PX4 command: arm")
        self._publish_vehicle_command(self._msgs["VehicleCommand"].VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0)

    def disarm(self) -> None:
        LOGGER.info("PX4 command: disarm")
        self._publish_vehicle_command(self._msgs["VehicleCommand"].VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=0.0)

    def set_offboard_mode(self) -> None:
        LOGGER.info("PX4 command: set offboard mode")
        self._publish_vehicle_command(self._msgs["VehicleCommand"].VEHICLE_CMD_DO_SET_MODE, param1=1.0, param2=6.0)

    def land(self) -> None:
        LOGGER.info("PX4 command: land")
        self._publish_vehicle_command(self._msgs["VehicleCommand"].VEHICLE_CMD_NAV_LAND)

    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float) -> None:
        self._publish_offboard_control_mode()
        msg = self._msgs["TrajectorySetpoint"]()
        msg.timestamp = self._timestamp_us()
        msg.position = [float(x), float(y), float(z)]
        msg.yaw = float(yaw)
        self._trajectory_pub.publish(msg)

    def get_position(self) -> Position | None:
        return self._position

    def get_vehicle_status(self) -> VehicleStatusSnapshot:
        return self._status

    def is_armed(self) -> bool:
        return self._status.arming_state == self.ARMING_STATE_ARMED

    def is_offboard(self) -> bool:
        return self._status.nav_state == self.NAVIGATION_STATE_OFFBOARD

    def has_valid_local_position(self) -> bool:
        return self._local_position_valid

    def _publish_offboard_control_mode(self) -> None:
        msg = self._msgs["OffboardControlMode"]()
        msg.timestamp = self._timestamp_us()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        self._offboard_pub.publish(msg)

    def _publish_vehicle_command(self, command: int, **params: Any) -> None:
        msg = self._msgs["VehicleCommand"]()
        msg.timestamp = self._timestamp_us()
        msg.command = command
        msg.param1 = float(params.get("param1", 0.0))
        msg.param2 = float(params.get("param2", 0.0))
        msg.param3 = float(params.get("param3", 0.0))
        msg.param4 = float(params.get("param4", 0.0))
        msg.param5 = float(params.get("param5", 0.0))
        msg.param6 = float(params.get("param6", 0.0))
        msg.param7 = float(params.get("param7", 0.0))
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self._command_pub.publish(msg)

    def _position_cb(self, msg) -> None:
        self._position = Position(float(msg.x), float(msg.y), float(msg.z), float(getattr(msg, "heading", 0.0)))
        self._local_position_valid = bool(getattr(msg, "xy_valid", True) and getattr(msg, "z_valid", True))

    def _status_cb(self, msg) -> None:
        self._status = VehicleStatusSnapshot(
            arming_state=int(getattr(msg, "arming_state", -1)),
            nav_state=int(getattr(msg, "nav_state", -1)),
            failsafe=bool(getattr(msg, "failsafe", False)),
            connected=True,
        )

    def _timestamp_us(self) -> int:
        return int(self.node.get_clock().now().nanoseconds / 1000)


class MockPX4Controller:
    """In-process controller stub for environments without ROS 2 (e.g. native macOS).

    Simulates a perfectly tracking vehicle: get_position() lerps toward the latest
    setpoint each spin_once(), and arm/offboard/land transitions are immediate.
    Lets perception + mission state machine + world model run end-to-end against
    a live Gazebo camera without requiring rclpy / px4_msgs.
    """

    ARMING_STATE_ARMED = 2
    NAVIGATION_STATE_OFFBOARD = 14

    def __init__(self, lerp: float = 0.4, start: Position | None = None) -> None:
        self._pos = start or Position(0.0, 0.0, 0.0, 0.0)
        self._setpoint: tuple[float, float, float, float] | None = None
        self._armed = False
        self._offboard = False
        self._landed = True
        self._lerp = float(lerp)
        LOGGER.info("MockPX4Controller initialized (no ROS 2)")

    def spin_once(self, timeout_sec: float = 0.0) -> None:
        if self._setpoint is None:
            return
        sx, sy, sz, syaw = self._setpoint
        a = self._lerp
        self._pos = Position(
            self._pos.x + a * (sx - self._pos.x),
            self._pos.y + a * (sy - self._pos.y),
            self._pos.z + a * (sz - self._pos.z),
            syaw,
        )

    def arm(self) -> None:
        LOGGER.info("MockPX4: arm")
        self._armed = True
        self._landed = False

    def disarm(self) -> None:
        LOGGER.info("MockPX4: disarm")
        self._armed = False

    def set_offboard_mode(self) -> None:
        LOGGER.info("MockPX4: set offboard")
        self._offboard = True

    def land(self) -> None:
        LOGGER.info("MockPX4: land")
        self._setpoint = (self._pos.x, self._pos.y, 0.0, self._pos.yaw)
        self._landed = True

    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float) -> None:
        self._setpoint = (float(x), float(y), float(z), float(yaw))

    def get_position(self) -> Position | None:
        return self._pos

    def get_vehicle_status(self) -> VehicleStatusSnapshot:
        return VehicleStatusSnapshot(
            arming_state=self.ARMING_STATE_ARMED if self._armed else 1,
            nav_state=self.NAVIGATION_STATE_OFFBOARD if self._offboard else 0,
            failsafe=False,
            connected=True,
        )

    def is_armed(self) -> bool:
        return self._armed

    def is_offboard(self) -> bool:
        return self._offboard

    def has_valid_local_position(self) -> bool:
        return True

