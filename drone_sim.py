from __future__ import annotations

import json
import math
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MISSION_PHASES = {
    "IDLE",
    "TAKEOFF",
    "PATROL",
    "HOLD",
    "RETURN_HOME",
    "LANDING",
    "LANDED",
    "ABORTED",
}


@dataclass
class Point:
    x: float
    y: float


@dataclass
class DetectionEvent:
    id: int
    kind: str
    confidence: float
    x: float
    y: float
    timestamp: str
    severity: str
    message: str


@dataclass
class DroneState:
    phase: str = "IDLE"
    x: float = 0
    y: float = 0
    altitude_m: float = 0
    heading_deg: float = 0
    battery_percent: float = 100
    gps_quality: float = 97
    link_quality: float = 98
    vibration: float = 0.08
    temperature_c: float = 34
    current_waypoint: int = 0
    obstacle_distance_m: float = 80
    wind_speed_mps: float = 0
    wind_direction_deg: float = 0
    wind_gust_mps: float = 0
    wind_drift_x: float = 0
    wind_drift_y: float = 0
    stabilization_effort: float = 0
    roll_deg: float = 0
    pitch_deg: float = 0
    manual_override: bool = False
    emergency_stop: bool = False
    last_reason: str = "Ready"
    updated_at: str = ""
    path: list[dict[str, float]] = field(default_factory=list)


class FlightLogger:
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = self.log_dir / f"flight-{stamp}.jsonl"

    def write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")


class DroneSimulation:
    def __init__(self, config_path: str = "mission_config.json") -> None:
        with open(config_path, "r", encoding="utf-8") as handle:
            self.config = json.load(handle)

        home = self.config["home"]
        self.home = Point(float(home["x"]), float(home["y"]))
        self.waypoints = [Point(float(wp["x"]), float(wp["y"])) for wp in self.config["waypoints"]]
        self.state = DroneState(x=self.home.x, y=self.home.y)
        self.state.path.append({"x": self.home.x, "y": self.home.y})
        self.events: list[DetectionEvent] = []
        self.lock = threading.Lock()
        self.running = False
        self.thread: threading.Thread | None = None
        self.event_id = 0
        self.logger = FlightLogger()
        self._last_log_at = 0.0
        self._last_detection_at = 0.0
        wind = self.config.get("wind", {})
        self.state.wind_speed_mps = float(wind.get("speed_mps", 0))
        self.state.wind_direction_deg = float(wind.get("direction_deg", 0))
        self.state.wind_gust_mps = float(wind.get("gust_mps", 0))

    def start_background(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop_background(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def command(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            if command == "start":
                if self.state.phase in {"IDLE", "LANDED"}:
                    self.state.phase = "TAKEOFF"
                    self.state.emergency_stop = False
                    self.state.last_reason = "Mission started"
                elif self.state.phase == "HOLD":
                    self.state.phase = "PATROL"
                    self.state.last_reason = "Mission resumed"
            elif command == "pause":
                if self.state.phase in {"TAKEOFF", "PATROL", "RETURN_HOME"}:
                    self.state.phase = "HOLD"
                    self.state.last_reason = "Mission paused"
            elif command == "rth":
                self._set_return_home("Return-to-home requested")
            elif command == "abort":
                self.state.emergency_stop = True
                self.state.phase = "ABORTED"
                self.state.last_reason = "Emergency stop active"
            elif command == "manual_override":
                self.state.manual_override = bool(payload.get("enabled", False))
                self.state.phase = "HOLD" if self.state.manual_override else "PATROL"
                self.state.last_reason = "Manual override enabled" if self.state.manual_override else "Autonomy restored"
            elif command == "wind":
                self.state.wind_speed_mps = self._clamp(float(payload.get("speed_mps", self.state.wind_speed_mps)), 0, 24)
                self.state.wind_direction_deg = float(payload.get("direction_deg", self.state.wind_direction_deg)) % 360
                self.state.wind_gust_mps = self._clamp(float(payload.get("gust_mps", self.state.wind_gust_mps)), 0, 10)
                self.state.last_reason = "Wind test updated"
            elif command == "inject_detection":
                kind = str(payload.get("kind", "unknown"))
                allowed = {"person", "vehicle", "drone-like object", "unknown"}
                if kind not in allowed:
                    kind = "unknown"
                severity = "warning" if kind in {"unknown", "drone-like object"} else "info"
                self._add_event(kind, 0.91, severity, f"Camera test detected {kind}")
                self.state.last_reason = "Camera input test event injected"
            else:
                return {"ok": False, "error": f"Unknown command: {command}"}
            return {"ok": True, "state": self.snapshot()}

    def snapshot(self) -> dict[str, Any]:
        state = asdict(self.state)
        state["events"] = [asdict(event) for event in self.events[-30:]]
        state["config"] = self.config
        return state

    def _loop(self) -> None:
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = min(now - last, 0.25)
            last = now
            with self.lock:
                self._tick(dt)
            time.sleep(0.08)

    def _tick(self, dt: float) -> None:
        self._update_health(dt)
        self._apply_wind_and_stabilization(dt)
        self._apply_safety_rules()

        if self.state.phase == "TAKEOFF":
            self._takeoff(dt)
        elif self.state.phase == "PATROL":
            self._patrol(dt)
        elif self.state.phase == "RETURN_HOME":
            self._return_home(dt)
        elif self.state.phase == "LANDING":
            self._land(dt)
        elif self.state.phase == "ABORTED":
            self.state.altitude_m = max(0, self.state.altitude_m - 8 * dt)

        self._simulate_perception()
        self.state.updated_at = self._now()
        self._remember_path()
        self._log_periodically()

    def _takeoff(self, dt: float) -> None:
        target_altitude = float(self.config["cruise_altitude_m"])
        self.state.altitude_m = min(target_altitude, self.state.altitude_m + 5.5 * dt)
        self.state.last_reason = "Taking off to patrol altitude"
        if self.state.altitude_m >= target_altitude - 0.2:
            self.state.phase = "PATROL"
            self.state.last_reason = "Patrolling route"

    def _patrol(self, dt: float) -> None:
        if self.state.obstacle_distance_m < 8:
            self.state.phase = "HOLD"
            self.state.last_reason = "Obstacle hold: waiting for clear route"
            self._add_event("unknown", 0.74, "warning", "Obstacle too close; holding position")
            return
        target = self.waypoints[self.state.current_waypoint]
        if self._move_toward(target, dt):
            self.state.current_waypoint = (self.state.current_waypoint + 1) % len(self.waypoints)
            self.state.last_reason = f"Reached waypoint {self.state.current_waypoint}"

    def _return_home(self, dt: float) -> None:
        return_altitude = float(self.config["return_altitude_m"])
        if self.state.altitude_m < return_altitude:
            self.state.altitude_m = min(return_altitude, self.state.altitude_m + 4.5 * dt)
        if self._move_toward(self.home, dt):
            self.state.phase = "LANDING"
            self.state.last_reason = "Home reached; landing"

    def _land(self, dt: float) -> None:
        self.state.altitude_m = max(0, self.state.altitude_m - 4.2 * dt)
        if self.state.altitude_m <= 0.1:
            self.state.altitude_m = 0
            self.state.phase = "LANDED"
            self.state.last_reason = "Landed safely"

    def _move_toward(self, target: Point, dt: float) -> bool:
        dx = target.x - self.state.x
        dy = target.y - self.state.y
        distance = math.hypot(dx, dy)
        if distance < 0.7:
            self.state.x = target.x
            self.state.y = target.y
            return True

        speed = float(self.config["speed_mps"])
        if self.state.obstacle_distance_m < 18:
            speed *= 0.35
            self.state.last_reason = "Obstacle nearby; slowing patrol"

        step = min(distance, speed * dt)
        self.state.x += (dx / distance) * step
        self.state.y += (dy / distance) * step
        self.state.heading_deg = (math.degrees(math.atan2(dy, dx)) + 360) % 360
        return False

    def _update_health(self, dt: float) -> None:
        active = self.state.phase in {"TAKEOFF", "PATROL", "RETURN_HOME", "LANDING"}
        if active:
            self.state.battery_percent = max(0, self.state.battery_percent - 0.035 * dt)
        self.state.gps_quality = self._bounded_noise(self.state.gps_quality, 48, 99, 0.7)
        self.state.link_quality = self._bounded_noise(self.state.link_quality, 26, 100, 0.9)
        self.state.vibration = self._bounded_noise(self.state.vibration, 0.04, 0.5, 0.015)
        self.state.temperature_c = self._bounded_noise(self.state.temperature_c, 28, 67, 0.08)
        self.state.obstacle_distance_m = self._bounded_noise(self.state.obstacle_distance_m, 4, 95, 5.5)
        self.state.wind_gust_mps = self._bounded_noise(self.state.wind_gust_mps, 0, 10, 0.08)

    def _apply_wind_and_stabilization(self, dt: float) -> None:
        if self.state.phase in {"IDLE", "LANDED"} or self.state.altitude_m <= 0:
            self.state.wind_drift_x = 0
            self.state.wind_drift_y = 0
            self.state.stabilization_effort = 0
            self.state.roll_deg = 0
            self.state.pitch_deg = 0
            return

        direction = math.radians(self.state.wind_direction_deg)
        gust = math.sin(time.monotonic() * 1.7) * self.state.wind_gust_mps
        effective_wind = max(0, self.state.wind_speed_mps + gust)
        raw_dx = math.cos(direction) * effective_wind
        raw_dy = math.sin(direction) * effective_wind
        gain = float(self.config.get("stabilization", {}).get("position_hold_gain", 0.34))
        max_tilt = float(self.config.get("stabilization", {}).get("max_tilt_deg", 28))

        compensation = min(0.92, gain + self.state.altitude_m / 120)
        self.state.wind_drift_x = round(raw_dx * (1 - compensation), 2)
        self.state.wind_drift_y = round(raw_dy * (1 - compensation), 2)
        self.state.x += self.state.wind_drift_x * dt
        self.state.y += self.state.wind_drift_y * dt
        self.state.stabilization_effort = round(min(100, effective_wind / 16 * 100), 1)
        self.state.roll_deg = round(self._clamp(-raw_dy * 2.3, -max_tilt, max_tilt), 1)
        self.state.pitch_deg = round(self._clamp(raw_dx * 2.3, -max_tilt, max_tilt), 1)

    def _apply_safety_rules(self) -> None:
        if self.state.manual_override or self.state.emergency_stop:
            return

        fence = self.config["geofence"]
        outside = (
            self.state.x < fence["min_x"]
            or self.state.x > fence["max_x"]
            or self.state.y < fence["min_y"]
            or self.state.y > fence["max_y"]
        )
        if outside:
            self._set_return_home("Geofence boundary exceeded")
            self._add_event("unknown", 0.88, "critical", "Geofence violation; returning home")

        if self.state.battery_percent <= float(self.config["critical_battery_percent"]):
            self.state.phase = "LANDING"
            self.state.last_reason = "Critical battery; landing immediately"
        elif self.state.battery_percent <= float(self.config["low_battery_percent"]):
            self._set_return_home("Low battery; returning home")

        if self.state.link_quality < float(self.config["minimum_link_quality"]):
            self._set_return_home("Signal quality low; returning home")
        if self.state.gps_quality < float(self.config["minimum_gps_quality"]):
            self.state.phase = "HOLD"
            self.state.last_reason = "GPS quality low; holding position"

        max_wind = float(self.config.get("stabilization", {}).get("max_wind_for_patrol_mps", 12))
        if self.state.phase == "PATROL" and self.state.wind_speed_mps + self.state.wind_gust_mps > max_wind:
            self._set_return_home("Wind too strong for patrol; returning home")
            self._add_event("unknown", 0.82, "warning", "High wind safety trigger")

    def _set_return_home(self, reason: str) -> None:
        if self.state.phase not in {"LANDING", "LANDED", "ABORTED"}:
            self.state.phase = "RETURN_HOME"
            self.state.last_reason = reason

    def _simulate_perception(self) -> None:
        now = time.monotonic()
        if self.state.phase not in {"PATROL", "RETURN_HOME"} or now - self._last_detection_at < 5:
            return
        if random.random() > 0.045:
            return
        kind = random.choice(["person", "vehicle", "drone-like object", "unknown"])
        confidence = round(random.uniform(0.62, 0.94), 2)
        severity = "warning" if kind in {"unknown", "drone-like object"} else "info"
        self._add_event(kind, confidence, severity, f"Detected {kind}")
        self._last_detection_at = now

    def _add_event(self, kind: str, confidence: float, severity: str, message: str) -> None:
        self.event_id += 1
        self.events.append(
            DetectionEvent(
                id=self.event_id,
                kind=kind,
                confidence=confidence,
                x=round(self.state.x, 2),
                y=round(self.state.y, 2),
                timestamp=self._now(),
                severity=severity,
                message=message,
            )
        )
        self.events = self.events[-100:]

    def _remember_path(self) -> None:
        if not self.state.path:
            self.state.path.append({"x": self.state.x, "y": self.state.y})
            return
        last = self.state.path[-1]
        if math.hypot(last["x"] - self.state.x, last["y"] - self.state.y) > 0.9:
            self.state.path.append({"x": round(self.state.x, 2), "y": round(self.state.y, 2)})
            self.state.path = self.state.path[-240:]

    def _log_periodically(self) -> None:
        now = time.monotonic()
        if now - self._last_log_at < 1:
            return
        self._last_log_at = now
        self.logger.write({"type": "state", "timestamp": self._now(), "state": asdict(self.state)})
        for event in self.events[-3:]:
            self.logger.write({"type": "event", "event": asdict(event)})

    @staticmethod
    def _bounded_noise(value: float, low: float, high: float, amplitude: float) -> float:
        return round(min(high, max(low, value + random.uniform(-amplitude, amplitude))), 2)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return min(high, max(low, value))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
