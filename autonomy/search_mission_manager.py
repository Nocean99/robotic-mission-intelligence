from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from autonomy.camera_interface import CameraFrameSource
from autonomy.candidate_manager import CandidateManager
from autonomy.mission_command import create_mission_command
from autonomy.mission_manager import ControllerProtocol
from autonomy.red_block_detector import DetectionConfirmation, RedBlockDetector
from autonomy.search_patterns import approach_setpoint, generate_search_waypoints
from autonomy.safety_monitor import SafetyMonitor
from autonomy.semantic_vision import LocalSemanticVisionScorer, SemanticVisionScorer, crop_detection, save_candidate_crop
from autonomy.types import MissionCommand, Position, SafetyAction, SearchMissionConfig, SearchMissionState, TargetDetection, Waypoint
from autonomy.waypoint_planner import interpolate_position
from autonomy.world_model import WorldModel


LOGGER = logging.getLogger(__name__)


class SearchMissionManager:
    def __init__(
        self,
        *,
        controller: ControllerProtocol,
        config: SearchMissionConfig,
        camera: CameraFrameSource,
        log_dir: str = "logs",
        image_rate_hz: float = 5.0,
        world_model: WorldModel | None = None,
        mission_request: str | None = None,
        mission_command: MissionCommand | None = None,
        semantic_scorer: SemanticVisionScorer | None = None,
        proposal_mode: str = "high-recall",
    ) -> None:
        self.controller = controller
        self.config = config
        self.camera = camera
        self.detector = RedBlockDetector(config.target)
        self.confirmation = DetectionConfirmation(config.target.required_confirm_frames)
        self.semantic_scorer = semantic_scorer or LocalSemanticVisionScorer()
        self.proposal_mode = proposal_mode
        self.safety = SafetyMonitor(config.mission)
        self.state = SearchMissionState.TAKEOFF
        self.home: Position | None = None
        self.target: Position | None = None
        self.search_waypoints = generate_search_waypoints(config.search, config.mission.waypoints)
        self.world_model = world_model or WorldModel(search_config=config.search, log_dir=log_dir)
        self.mission_command = mission_command or create_mission_command(
            mission_request or "Search the area for the configured target"
        )
        self.objective = self.mission_command.objective
        self.candidate_manager = CandidateManager(self.objective, log_dir=log_dir)
        self.search_index = 0
        self.started_at = 0.0
        self.state_entered_at = 0.0
        self.last_image_at = 0.0
        self.image_period_s = 1.0 / image_rate_hz
        self.last_detection = TargetDetection(False)
        self.last_frame: np.ndarray | None = None
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.log_path = self.log_dir / f"search_mission_{self.run_stamp}.csv"
        self._log_file = self.log_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._log_file,
            fieldnames=[
                "timestamp",
                "state",
                "x",
                "y",
                "z",
                "detection_confidence",
                "bbox",
                "active_search_waypoint",
                "target_confirmed",
                "target_x",
                "target_y",
                "target_z",
                "safety_action",
                "safety_reason",
                "searched_cells",
                "unsearched_cells",
                "world_target_candidates",
                "confirmed_world_target",
            ],
        )
        self._writer.writeheader()
        self.marked_snapshot_path: Path | None = None
        self.offboard_setpoint_count = 0
        self._offboard_command_sent = False
        self._arm_command_sent = False
        self._closed = False
        self.world_model_json_path = self.log_dir / f"world_model_{self.run_stamp}.json"
        self.world_model_heatmap_path = self.log_dir / f"world_model_{self.run_stamp}.png"
        self.debug_snapshot_path = self.log_dir / f"debug_camera_{self.run_stamp}.png"
        self.target_snapshot_path = self.log_dir / f"target_{self.run_stamp}.png"
        self.candidates_path = self.log_dir / f"candidates_{self.run_stamp}.json"
        self.mission_command_path = self.log_dir / f"mission_command_{self.run_stamp}.json"
        self._candidate_counter = 0

    def start(self, now_s: float | None = None) -> None:
        now = now_s if now_s is not None else time.monotonic()
        self.started_at = now
        self.state_entered_at = now
        LOGGER.info("Search mission started")

    def close(self) -> None:
        if self._closed:
            return
        self.export_artifacts()
        self._log_file.close()
        self._closed = True

    def export_artifacts(self) -> dict[str, str | None]:
        artifacts: dict[str, str | None] = {
            "search_log": str(self.log_path),
            "world_model_json": str(self.world_model.save_snapshot_json(self.world_model_json_path)),
            "world_model_heatmap": str(self.world_model.save_heatmap(self.world_model_heatmap_path)),
            "debug_camera": None,
            "target_snapshot": None,
            "candidates": str(self.candidate_manager.save(self.candidates_path)),
            "mission_command": str(self._save_mission_command()),
        }
        if self.last_frame is not None:
            self.detector.save_snapshot(self.last_frame, self.debug_snapshot_path, self.last_detection)
            artifacts["debug_camera"] = str(self.debug_snapshot_path)
            if self.last_detection.detected or self.world_model.confirmed_target_location is not None:
                self.detector.save_snapshot(self.last_frame, self.target_snapshot_path, self.last_detection)
                self.marked_snapshot_path = self.target_snapshot_path
                artifacts["target_snapshot"] = str(self.target_snapshot_path)
        LOGGER.info("Search mission artifacts exported: %s", artifacts)
        return artifacts

    def _save_mission_command(self) -> Path:
        self.mission_command_path.write_text(
            json.dumps(asdict(self.mission_command), indent=2, default=str),
            encoding="utf-8",
        )
        return self.mission_command_path

    def tick(self, now_s: float | None = None, dt_s: float = 0.05) -> SearchMissionState:
        now = now_s if now_s is not None else time.monotonic()
        position = self.controller.get_position()
        if self.home is None and position is not None and self.controller.has_valid_local_position():
            self.home = position
            self.world_model.set_home(position)
            self.world_model.set_safety_radius(self.config.mission.max_distance_from_home_m)
        self.world_model.update_pose(position, self.state, now)

        safety = self.safety.check(
            position=position,
            home=self.home,
            local_position_valid=self.controller.has_valid_local_position(),
            is_offboard=self.controller.is_offboard(),
            mission_requires_offboard=self.state not in {SearchMissionState.TAKEOFF, SearchMissionState.LAND, SearchMissionState.COMPLETE},
            waypoint_timed_out=False,
        )
        if safety.action in {SafetyAction.LAND_NOW, SafetyAction.EMERGENCY_LAND}:
            self._transition(SearchMissionState.LAND, now, safety.reason)
        elif safety.action == SafetyAction.RETURN_HOME:
            self._transition(SearchMissionState.RETURN_HOME, now, safety.reason)

        if now - self.started_at > self.config.search.timeout_s and self.state not in {SearchMissionState.RETURN_HOME, SearchMissionState.LAND, SearchMissionState.COMPLETE}:
            self._transition(SearchMissionState.RETURN_HOME, now, "Search timeout")

        if now - self.last_image_at >= self.image_period_s:
            self._process_camera(now)

        if self.state == SearchMissionState.TAKEOFF:
            self._takeoff(now, position, dt_s)
        elif self.state == SearchMissionState.SEARCH_PATTERN:
            self._search_pattern(now, position, dt_s)
        elif self.state == SearchMissionState.DETECT_TARGET:
            self._detect_target(now)
        elif self.state == SearchMissionState.CONFIRM_TARGET:
            self._confirm_target(now)
        elif self.state == SearchMissionState.APPROACH_TARGET:
            self._approach_target(now, position, dt_s)
        elif self.state == SearchMissionState.MARK_LOCATION:
            self._mark_location(now, position)
        elif self.state == SearchMissionState.RETURN_HOME:
            self._return_home(now, position, dt_s)
        elif self.state == SearchMissionState.LAND:
            self.controller.land()
            if position is not None and position.altitude_m <= 0.25:
                self._transition(SearchMissionState.COMPLETE, now, "Landed")

        self._log(safety)
        self.world_model.log_update()
        return self.state

    def _takeoff(self, now: float, position: Position | None, dt_s: float) -> None:
        if position is None:
            return
        target = Position(position.x, position.y, -abs(self.config.search.altitude_m), position.yaw)
        setpoint = interpolate_position(position, target, self.config.search.search_speed_mps, dt_s)
        self._publish(setpoint)
        self.offboard_setpoint_count += 1
        warmup_required = max(10, int(self.config.mission.control_rate_hz * 0.6))
        if self.offboard_setpoint_count >= warmup_required and not self._offboard_command_sent:
            self.controller.set_offboard_mode()
            self._offboard_command_sent = True
        if self._offboard_command_sent and not self._arm_command_sent:
            self.controller.arm()
            self._arm_command_sent = True
        if not (self.controller.is_armed() and self.controller.is_offboard()):
            return
        if abs(position.z - target.z) <= self.config.mission.waypoint_tolerance_m:
            self._transition(SearchMissionState.SEARCH_PATTERN, now, "Search altitude reached")

    def _search_pattern(self, now: float, position: Position | None, dt_s: float) -> None:
        if self.last_detection.detected:
            self._transition(SearchMissionState.DETECT_TARGET, now, "Candidate target detected")
            return
        if position is None:
            self._transition(SearchMissionState.RETURN_HOME, now, "Search pattern complete")
            return
        waypoint = self._next_search_target(position)
        if waypoint is None:
            self._transition(SearchMissionState.RETURN_HOME, now, "No unsearched cells remain")
            return
        setpoint = interpolate_position(position, waypoint, self.config.search.search_speed_mps, dt_s)
        self._publish(setpoint)
        if self.search_index < len(self.search_waypoints) and _distance(position, waypoint) <= self.config.mission.waypoint_tolerance_m:
            self.search_index += 1

    def _detect_target(self, now: float) -> None:
        if not self.last_detection.detected:
            self._transition(SearchMissionState.SEARCH_PATTERN, now, "Detection lost")
            return
        self._transition(SearchMissionState.CONFIRM_TARGET, now, "Confirming persistent detection")

    def _confirm_target(self, now: float) -> None:
        if self.confirmation.confirmed:
            if self.config.approach.enabled:
                self._transition(SearchMissionState.APPROACH_TARGET, now, "Target confirmed; approaching")
            else:
                self._transition(SearchMissionState.MARK_LOCATION, now, "Target confirmed")
        elif not self.last_detection.detected:
            self._transition(SearchMissionState.SEARCH_PATTERN, now, "Confirmation failed")

    def _approach_target(self, now: float, position: Position | None, dt_s: float) -> None:
        if position is None:
            return
        detection = self.last_detection
        if not detection.detected or detection.center_px is None or self.last_frame is None:
            self._transition(SearchMissionState.SEARCH_PATTERN, now, "Target lost during approach")
            return
        height, width = self.last_frame.shape[:2]
        center_error = abs(detection.center_px[0] - width / 2)
        if detection.area_ratio >= self.config.approach.stop_area_ratio:
            self._transition(SearchMissionState.MARK_LOCATION, now, "Target close enough")
            return
        if center_error <= self.config.approach.center_tolerance_px:
            setpoint = approach_setpoint(position, detection.center_px, (width, height), self.config.approach.max_speed_mps, dt_s)
            setpoint = Position(setpoint.x, setpoint.y, -abs(self.config.search.altitude_m), setpoint.yaw)
            self._publish(setpoint)
        else:
            yaw_adjust = (detection.center_px[0] - width / 2) / width * 0.25
            self._publish(Position(position.x, position.y, -abs(self.config.search.altitude_m), position.yaw + yaw_adjust))

    def _mark_location(self, now: float, position: Position | None) -> None:
        if position is not None:
            self.target = position
        self.world_model.confirm_target(position, self.last_detection, now)
        if self.last_frame is not None:
            self.marked_snapshot_path = self.target_snapshot_path
            self.detector.save_snapshot(self.last_frame, self.marked_snapshot_path, self.last_detection)
        LOGGER.info("Target marked at %s confidence=%.3f snapshot=%s", self.target, self.last_detection.confidence, self.marked_snapshot_path)
        self._transition(SearchMissionState.RETURN_HOME, now, "Target marked")

    def _return_home(self, now: float, position: Position | None, dt_s: float) -> None:
        if position is None or self.home is None:
            self._transition(SearchMissionState.LAND, now, "No position/home for return")
            return
        target = Position(self.home.x, self.home.y, -abs(self.config.mission.return_home_altitude_m), self.home.yaw)
        self._publish(interpolate_position(position, target, self.config.search.search_speed_mps, dt_s))
        if _distance_xy(position, self.home) <= self.config.mission.waypoint_tolerance_m:
            self._transition(SearchMissionState.LAND, now, "Home reached")

    def _process_camera(self, now: float) -> None:
        self.last_image_at = now
        try:
            frame = self.camera.latest_frame()
        except Exception as exc:
            LOGGER.warning("Camera frame read failed: %s", exc)
            frame = None
        if frame is None:
            self.last_detection = TargetDetection(False)
            self.confirmation.update(self.last_detection)
            self.world_model.update_detection(self.last_detection, self.controller.get_position(), now)
            return
        self.last_frame = frame
        self.last_detection = self.detector.detect_high_recall(frame) if self.proposal_mode == "high-recall" else self.detector.detect(frame)
        self.confirmation.update(self.last_detection)
        self.world_model.update_detection(self.last_detection, self.controller.get_position(), now)
        crop = crop_detection(frame, self.last_detection)
        semantic_result = self.semantic_scorer.score(
            objective=self.objective,
            frame_bgr=frame,
            crop_bgr=crop,
            detection=self.last_detection,
        )
        crop_path = None
        if self.last_detection.detected:
            self._candidate_counter += 1
            crop_path = save_candidate_crop(
                crop,
                self.log_dir / f"candidate_{self.run_stamp}_{self._candidate_counter:04d}.png",
            )
        self.candidate_manager.add_detection(
            detection=self.last_detection,
            position=self.controller.get_position(),
            source="red_block_hsv",
            crop_path=crop_path,
            explanation=semantic_result.explanation,
            semantic_result=semantic_result,
        )

    def _publish(self, position: Position) -> None:
        self.controller.publish_position_setpoint(position.x, position.y, position.z, position.yaw)

    def _transition(self, state: SearchMissionState, now: float, reason: str) -> None:
        if self.state == state:
            return
        LOGGER.info("Search transition: %s -> %s (%s)", self.state.value, state.value, reason)
        self.state = state
        self.world_model.mission_state = state
        self.state_entered_at = now

    def _next_search_target(self, position: Position) -> Position | None:
        if self.search_index < len(self.search_waypoints):
            return self.search_waypoints[self.search_index]
        return self.world_model.next_unsearched_waypoint(self.config.search.altitude_m)

    def _log(self, safety) -> None:
        position = self.controller.get_position()
        self._writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state": self.state.value,
                "x": None if position is None else position.x,
                "y": None if position is None else position.y,
                "z": None if position is None else position.z,
                "detection_confidence": self.last_detection.confidence,
                "bbox": self.last_detection.bbox,
                "active_search_waypoint": self.search_index,
                "target_confirmed": self.confirmation.confirmed,
                "target_x": None if self.target is None else self.target.x,
                "target_y": None if self.target is None else self.target.y,
                "target_z": None if self.target is None else self.target.z,
                "safety_action": safety.action.value,
                "safety_reason": safety.reason,
                "searched_cells": len(self.world_model.searched_cells),
                "unsearched_cells": len(self.world_model.unsearched_cells),
                "world_target_candidates": len(self.world_model.target_candidates),
                "confirmed_world_target": self.world_model.confirmed_target_location,
            }
        )
        self._log_file.flush()


def _distance(a: Position, b: Position) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _distance_xy(a: Position, b: Position) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
