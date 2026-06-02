from __future__ import annotations

import re
from pathlib import Path

from autonomy.types import ApproachConfig, MissionConfig, SearchConfig, SearchMissionConfig, TargetConfig, Waypoint


def load_mission_config(path: str | Path) -> MissionConfig:
    text = Path(path).read_text(encoding="utf-8")
    data = _parse_simple_yaml(text)
    allowed = {
        "takeoff_altitude_m",
        "hover_time_s",
        "control_rate_hz",
        "waypoint_tolerance_m",
        "yaw_tolerance_rad",
        "max_altitude_m",
        "max_distance_from_home_m",
        "waypoint_timeout_s",
        "return_home_altitude_m",
        "cruise_speed_mps",
        "waypoints",
    }
    data = {key: value for key, value in data.items() if key in allowed}
    waypoints = [_waypoint_from_mapping(item) for item in data.pop("waypoints", [])]
    return MissionConfig(waypoints=waypoints, **data)


def load_search_mission_config(path: str | Path) -> SearchMissionConfig:
    parsed = _parse_simple_yaml(Path(path).read_text(encoding="utf-8"))
    mission_keys = {
        "takeoff_altitude_m",
        "hover_time_s",
        "control_rate_hz",
        "waypoint_tolerance_m",
        "yaw_tolerance_rad",
        "max_altitude_m",
        "max_distance_from_home_m",
        "waypoint_timeout_s",
        "return_home_altitude_m",
        "cruise_speed_mps",
        "waypoints",
    }
    mission_data = {key: parsed[key] for key in mission_keys if key in parsed}
    waypoints = [_waypoint_from_mapping(item) for item in mission_data.pop("waypoints", [])]
    mission = MissionConfig(waypoints=waypoints, **mission_data)
    target = TargetConfig(
        type=str(parsed["target"]["type"]),
        hsv_lower_1=tuple(parsed["target"]["hsv_lower_1"]),
        hsv_upper_1=tuple(parsed["target"]["hsv_upper_1"]),
        hsv_lower_2=tuple(parsed["target"]["hsv_lower_2"]),
        hsv_upper_2=tuple(parsed["target"]["hsv_upper_2"]),
        min_area_px=int(parsed["target"]["min_area_px"]),
        required_confirm_frames=int(parsed["target"]["required_confirm_frames"]),
    )
    search = SearchConfig(
        pattern=str(parsed["search"]["pattern"]),
        area_width_m=float(parsed["search"]["area_width_m"]),
        area_height_m=float(parsed["search"]["area_height_m"]),
        lane_spacing_m=float(parsed["search"]["lane_spacing_m"]),
        altitude_m=float(parsed["search"]["altitude_m"]),
        search_speed_mps=float(parsed["search"]["search_speed_mps"]),
        timeout_s=float(parsed["search"]["timeout_s"]),
    )
    approach = ApproachConfig(
        enabled=bool(parsed["approach"]["enabled"]),
        max_speed_mps=float(parsed["approach"]["max_speed_mps"]),
        stop_area_ratio=float(parsed["approach"]["stop_area_ratio"]),
        center_tolerance_px=int(parsed["approach"]["center_tolerance_px"]),
    )
    return SearchMissionConfig(mission=mission, target=target, search=search, approach=approach)


def _parse_simple_yaml(text: str) -> dict:
    result: dict[str, object] = {}
    current_list: str | None = None
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                result[key] = []
                current_section = key if key in {"target", "search", "approach"} else None
                if current_section:
                    result[key] = {}
                    current_list = None
                else:
                    current_list = key
            else:
                result[key] = _parse_scalar(value)
                current_list = None
                current_section = None
            continue
        if current_section and raw_line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            result[current_section][key.strip()] = _parse_scalar(value.strip())
            continue
        if current_list and line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            result[current_list].append(_parse_inline_mapping(item))
    return result


def _parse_inline_mapping(value: str) -> dict:
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"Only inline waypoint mappings are supported: {value}")
    inner = value[1:-1].strip()
    mapping = {}
    for part in re.split(r",\s*", inner):
        key, raw_value = part.split(":", 1)
        mapping[key.strip()] = _parse_scalar(raw_value.strip())
    return mapping


def _parse_scalar(value: str):
    lowered = value.lower()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item.strip()) for item in inner.split(",")]
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value or "e" in lowered:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("'\"")


def _waypoint_from_mapping(data: dict) -> Waypoint:
    return Waypoint(
        x=float(data["x"]),
        y=float(data["y"]),
        z=float(data["z"]),
        yaw=float(data.get("yaw", 0.0)),
        hold_time_s=float(data.get("hold_time_s", data.get("hold_time_seconds", 0.0))),
    )
