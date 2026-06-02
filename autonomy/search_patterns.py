from __future__ import annotations

from autonomy.types import Position, SearchConfig, Waypoint


def generate_search_waypoints(config: SearchConfig, explicit_waypoints: list[Waypoint] | None = None) -> list[Waypoint]:
    pattern = config.pattern.lower()
    if pattern in {"waypoint", "waypoints", "waypoint_list"}:
        if not explicit_waypoints:
            raise ValueError("waypoint list search requires explicit waypoints")
        return explicit_waypoints
    if pattern in {"lawnmower", "grid"}:
        return _lawnmower(config)
    if pattern in {"expanding_square", "square"}:
        return _expanding_square(config)
    raise ValueError(f"Unsupported search pattern: {config.pattern}")


def _lawnmower(config: SearchConfig) -> list[Waypoint]:
    altitude_z = -abs(config.altitude_m)
    half_w = config.area_width_m / 2
    half_h = config.area_height_m / 2
    y = -half_h
    lane = 0
    waypoints: list[Waypoint] = []
    while y <= half_h + 1e-6:
        x_start, x_end = (-half_w, half_w) if lane % 2 == 0 else (half_w, -half_w)
        waypoints.append(Waypoint(x_start, y, altitude_z, 0.0, 0.0))
        waypoints.append(Waypoint(x_end, y, altitude_z, 0.0, 0.0))
        y += config.lane_spacing_m
        lane += 1
    return waypoints


def _expanding_square(config: SearchConfig) -> list[Waypoint]:
    altitude_z = -abs(config.altitude_m)
    max_x = config.area_width_m / 2
    max_y = config.area_height_m / 2
    step = max(config.lane_spacing_m, 0.5)
    waypoints = [Waypoint(0.0, 0.0, altitude_z, 0.0, 0.0)]
    x = y = 0.0
    leg = step
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    direction_index = 0
    while abs(x) < max_x or abs(y) < max_y:
        for _ in range(2):
            dx, dy = directions[direction_index % 4]
            x = _clamp(x + dx * leg, -max_x, max_x)
            y = _clamp(y + dy * leg, -max_y, max_y)
            waypoints.append(Waypoint(x, y, altitude_z, 0.0, 0.0))
            direction_index += 1
        leg += step
        if len(waypoints) > 200:
            break
    return waypoints


def approach_setpoint(position: Position, detection_center: tuple[int, int], image_size: tuple[int, int], speed_mps: float, dt_s: float) -> Position:
    width, height = image_size
    error_x = detection_center[0] - width / 2
    error_y = detection_center[1] - height / 2
    scale = max(width, height)
    vx = max(-speed_mps, min(speed_mps, speed_mps * (1.0 - abs(error_x) / scale)))
    vy = max(-speed_mps, min(speed_mps, speed_mps * error_x / scale))
    vz = max(-0.2, min(0.2, speed_mps * error_y / scale * 0.25))
    return Position(position.x + vx * dt_s, position.y + vy * dt_s, position.z + vz * dt_s, position.yaw)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))

