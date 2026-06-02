from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from autonomy.types import Position, SearchConfig, SearchMissionState, TargetDetection


@dataclass
class GridCell:
    visited: bool = False
    last_seen_time: float | None = None
    target_confidence: float = 0.0
    obstacle_confidence: float = 0.0
    risk_score: float = 0.0


@dataclass
class TargetCandidate:
    x: float
    y: float
    z: float
    confidence: float
    last_seen_time: float
    bbox: tuple[int, int, int, int] | None = None
    bearing_rad: float | None = None


@dataclass
class SafetyZone:
    name: str
    center_x: float
    center_y: float
    radius_m: float
    zone_type: str


@dataclass
class WorldModelSnapshot:
    timestamp: str
    mission_state: str
    drone_pose: dict | None
    home_position: dict | None
    confirmed_target_location: dict | None
    searched_cells: int
    unsearched_cells: int
    target_candidates: list[dict]
    safety_zones: list[dict]


class WorldModel:
    def __init__(
        self,
        *,
        search_config: SearchConfig,
        cell_size_m: float | None = None,
        confidence_decay_per_s: float = 0.02,
        log_dir: str = "logs",
    ) -> None:
        self.search_config = search_config
        self.cell_size_m = cell_size_m or max(0.5, search_config.lane_spacing_m)
        self.width_m = search_config.area_width_m
        self.height_m = search_config.area_height_m
        self.cols = max(1, math.ceil(self.width_m / self.cell_size_m))
        self.rows = max(1, math.ceil(self.height_m / self.cell_size_m))
        self.origin_x = -self.width_m / 2
        self.origin_y = -self.height_m / 2
        self.grid = [[GridCell() for _ in range(self.cols)] for _ in range(self.rows)]
        self.drone_pose: Position | None = None
        self.home_position: Position | None = None
        self.mission_state: SearchMissionState | str = SearchMissionState.TAKEOFF
        self.target_candidates: list[TargetCandidate] = []
        self.confirmed_target_location: Position | None = None
        self.obstacle_placeholders: list[dict] = []
        self.safety_zones: list[SafetyZone] = []
        self.confidence_decay_per_s = confidence_decay_per_s
        self._last_decay_time: float | None = None
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.update_log_path = self.log_dir / "world_model_updates.jsonl"

    @property
    def searched_cells(self) -> list[tuple[int, int]]:
        return [(row, col) for row in range(self.rows) for col in range(self.cols) if self.grid[row][col].visited]

    @property
    def unsearched_cells(self) -> list[tuple[int, int]]:
        return [(row, col) for row in range(self.rows) for col in range(self.cols) if not self.grid[row][col].visited]

    def set_home(self, home: Position | None) -> None:
        self.home_position = home

    def set_safety_radius(self, radius_m: float) -> None:
        self.safety_zones = [zone for zone in self.safety_zones if zone.name != "home_radius"]
        self.safety_zones.append(SafetyZone("home_radius", 0.0, 0.0, radius_m, "max_distance"))

    def update_pose(self, pose: Position | None, mission_state: SearchMissionState | str, now_s: float) -> None:
        self.drone_pose = pose
        self.mission_state = mission_state
        if pose is None:
            return
        index = self.cell_for_position(pose.x, pose.y)
        if index is not None:
            row, col = index
            cell = self.grid[row][col]
            cell.visited = True
            cell.last_seen_time = now_s
            cell.risk_score = max(cell.risk_score, cell.obstacle_confidence)

    def update_detection(self, detection: TargetDetection, pose: Position | None, now_s: float) -> None:
        if pose is None:
            return
        if detection.detected:
            target_x, target_y = self._estimate_target_xy(pose, detection)
            index = self.cell_for_position(target_x, target_y)
            if index is not None:
                row, col = index
                cell = self.grid[row][col]
                cell.target_confidence = min(1.0, max(cell.target_confidence, detection.confidence) + 0.08)
                cell.last_seen_time = now_s
            self.target_candidates.append(
                TargetCandidate(
                    x=target_x,
                    y=target_y,
                    z=pose.z,
                    confidence=detection.confidence,
                    last_seen_time=now_s,
                    bbox=detection.bbox,
                    bearing_rad=detection.bearing_rad,
                )
            )
            self.target_candidates = sorted(self.target_candidates, key=lambda item: item.confidence, reverse=True)[:20]
        else:
            self.decay_confidence(now_s)

    def decay_confidence(self, now_s: float) -> None:
        if self._last_decay_time is None:
            self._last_decay_time = now_s
            return
        dt = max(0.0, now_s - self._last_decay_time)
        self._last_decay_time = now_s
        decay = self.confidence_decay_per_s * dt
        for row in self.grid:
            for cell in row:
                cell.target_confidence = max(0.0, cell.target_confidence - decay)
                cell.obstacle_confidence = max(0.0, cell.obstacle_confidence - decay * 0.5)
                cell.risk_score = max(cell.obstacle_confidence, cell.risk_score - decay * 0.25)

    def confirm_target(self, pose: Position | None, detection: TargetDetection | None, now_s: float) -> None:
        if pose is None:
            return
        if detection and detection.detected:
            target_x, target_y = self._estimate_target_xy(pose, detection)
            self.confirmed_target_location = Position(target_x, target_y, pose.z, pose.yaw)
            index = self.cell_for_position(target_x, target_y)
            if index is not None:
                row, col = index
                self.grid[row][col].target_confidence = 1.0
                self.grid[row][col].last_seen_time = now_s
        else:
            self.confirmed_target_location = pose

    def next_unsearched_waypoint(self, altitude_m: float) -> Position | None:
        if not self.unsearched_cells:
            return None
        if self.drone_pose is None:
            row, col = self.unsearched_cells[0]
            x, y = self.center_for_cell(row, col)
            return Position(x, y, -abs(altitude_m), 0.0)
        best = min(
            self.unsearched_cells,
            key=lambda idx: (self.center_for_cell(*idx)[0] - self.drone_pose.x) ** 2
            + (self.center_for_cell(*idx)[1] - self.drone_pose.y) ** 2,
        )
        x, y = self.center_for_cell(*best)
        return Position(x, y, -abs(altitude_m), self.drone_pose.yaw)

    def cell_for_position(self, x: float, y: float) -> tuple[int, int] | None:
        col = int((x - self.origin_x) / self.cell_size_m)
        row = int((y - self.origin_y) / self.cell_size_m)
        if row < 0 or col < 0 or row >= self.rows or col >= self.cols:
            return None
        return row, col

    def center_for_cell(self, row: int, col: int) -> tuple[float, float]:
        x = self.origin_x + (col + 0.5) * self.cell_size_m
        y = self.origin_y + (row + 0.5) * self.cell_size_m
        return x, y

    def snapshot(self) -> WorldModelSnapshot:
        return WorldModelSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mission_state=self.mission_state.value if isinstance(self.mission_state, SearchMissionState) else str(self.mission_state),
            drone_pose=None if self.drone_pose is None else asdict(self.drone_pose),
            home_position=None if self.home_position is None else asdict(self.home_position),
            confirmed_target_location=None if self.confirmed_target_location is None else asdict(self.confirmed_target_location),
            searched_cells=len(self.searched_cells),
            unsearched_cells=len(self.unsearched_cells),
            target_candidates=[asdict(candidate) for candidate in self.target_candidates],
            safety_zones=[asdict(zone) for zone in self.safety_zones],
        )

    def save_snapshot_json(self, path: str | Path | None = None) -> Path:
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = self.log_dir / f"world_model_{stamp}.json"
        output = {
            **asdict(self.snapshot()),
            "grid": [[asdict(cell) for cell in row] for row in self.grid],
            "obstacle_placeholders": self.obstacle_placeholders,
        }
        Path(path).parent.mkdir(exist_ok=True)
        Path(path).write_text(json.dumps(output, indent=2), encoding="utf-8")
        return Path(path)

    def save_heatmap(self, path: str | Path | None = None) -> Path:
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = self.log_dir / f"world_model_{stamp}.png"
        image = np.zeros((self.rows, self.cols, 3), dtype=np.uint8)
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.grid[row][col]
                if cell.visited:
                    image[row, col] = (90, 120, 90)
                target = int(min(255, cell.target_confidence * 255))
                risk = int(min(255, cell.risk_score * 255))
                image[row, col, 2] = max(image[row, col, 2], target)
                image[row, col, 1] = max(image[row, col, 1], int(cell.visited) * 100)
                image[row, col, 0] = max(image[row, col, 0], risk)
        image = cv2.resize(image, (max(320, self.cols * 24), max(320, self.rows * 24)), interpolation=cv2.INTER_NEAREST)
        Path(path).parent.mkdir(exist_ok=True)
        cv2.imwrite(str(path), image)
        return Path(path)

    def log_update(self) -> None:
        with self.update_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(self.snapshot()), separators=(",", ":")) + "\n")

    def _estimate_target_xy(self, pose: Position, detection: TargetDetection) -> tuple[float, float]:
        bearing = detection.bearing_rad or 0.0
        estimated_range_m = max(1.0, min(10.0, 1.0 / max(detection.area_ratio, 0.02)))
        yaw = pose.yaw + bearing
        return pose.x + math.cos(yaw) * estimated_range_m, pose.y + math.sin(yaw) * estimated_range_m
