from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MissionState(str, Enum):
    IDLE = "IDLE"
    PRE_FLIGHT_CHECK = "PRE_FLIGHT_CHECK"
    ARMING = "ARMING"
    TAKEOFF = "TAKEOFF"
    HOVER = "HOVER"
    MISSION = "MISSION"
    RETURN_HOME = "RETURN_HOME"
    LANDING = "LANDING"
    LANDED = "LANDED"
    EMERGENCY = "EMERGENCY"


class SearchMissionState(str, Enum):
    TAKEOFF = "TAKEOFF"
    SEARCH_PATTERN = "SEARCH_PATTERN"
    DETECT_TARGET = "DETECT_TARGET"
    APPROACH_TARGET = "APPROACH_TARGET"
    CONFIRM_TARGET = "CONFIRM_TARGET"
    MARK_LOCATION = "MARK_LOCATION"
    RETURN_HOME = "RETURN_HOME"
    LAND = "LAND"
    COMPLETE = "COMPLETE"
    EMERGENCY = "EMERGENCY"


class SafetyAction(str, Enum):
    NONE = "NONE"
    RETURN_HOME = "RETURN_HOME"
    LAND_NOW = "LAND_NOW"
    EMERGENCY_LAND = "EMERGENCY_LAND"


class CandidateStatus(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    NEEDS_CLOSER_LOOK = "NEEDS_CLOSER_LOOK"


class OperatingMode(str, Enum):
    CONNECTED_SUPERVISED = "CONNECTED_SUPERVISED"
    AUTONOMOUS_RETURN_REPORT = "AUTONOMOUS_RETURN_REPORT"


class LinkLossAction(str, Enum):
    HOLD_AND_WAIT = "HOLD_AND_WAIT"
    CONTINUE_THEN_RETURN = "CONTINUE_THEN_RETURN"
    RETURN_HOME = "RETURN_HOME"
    LAND_NOW = "LAND_NOW"


class ConfirmationMode(str, Enum):
    LIVE_OPERATOR = "LIVE_OPERATOR"
    STORE_FOR_REVIEW = "STORE_FOR_REVIEW"
    AUTO_MARK_HIGH_CONFIDENCE = "AUTO_MARK_HIGH_CONFIDENCE"


class SemanticDecision(str, Enum):
    REJECT = "REJECT"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    LIKELY_MATCH = "LIKELY_MATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float
    yaw: float = 0.0

    @property
    def altitude_m(self) -> float:
        return max(0.0, -self.z)


@dataclass(frozen=True)
class Waypoint(Position):
    hold_time_s: float = 0.0


@dataclass
class VehicleStatusSnapshot:
    arming_state: int | None = None
    nav_state: int | None = None
    failsafe: bool = False
    connected: bool = False


@dataclass
class MissionConfig:
    takeoff_altitude_m: float
    hover_time_s: float
    control_rate_hz: int
    waypoint_tolerance_m: float
    yaw_tolerance_rad: float
    max_altitude_m: float
    max_distance_from_home_m: float
    waypoint_timeout_s: float
    return_home_altitude_m: float
    cruise_speed_mps: float
    waypoints: list[Waypoint] = field(default_factory=list)


@dataclass(frozen=True)
class TargetDetection:
    detected: bool
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] | None = None
    center_px: tuple[int, int] | None = None
    area_px: float = 0.0
    area_ratio: float = 0.0
    bearing_rad: float | None = None


@dataclass(frozen=True)
class MissionObjective:
    raw_request: str
    mission_type: str = "search_and_rescue"
    target_description: str = ""
    search_area_description: str | None = None
    urgency: str = "normal"
    confirmation_required: bool = True
    extracted_keywords: list[str] = field(default_factory=list)
    extracted_colors: list[str] = field(default_factory=list)
    extracted_categories: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LinkLossPolicy:
    action: LinkLossAction
    max_disconnected_s: float
    require_return_with_report: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportRequirements:
    save_mission_log: bool = True
    save_world_model: bool = True
    save_candidate_images: bool = True
    save_candidate_json: bool = True
    save_debug_frames: bool = True
    require_human_review: bool = True


@dataclass(frozen=True)
class MissionCommand:
    raw_request: str
    operating_mode: OperatingMode
    objective: MissionObjective
    confirmation_mode: ConfirmationMode
    link_loss_policy: LinkLossPolicy
    report_requirements: ReportRequirements
    autonomy_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticVisionResult:
    score: float
    decision: SemanticDecision
    explanation: str
    model_name: str
    tags: list[str] = field(default_factory=list)
    needs_human_review: bool = True


@dataclass(frozen=True)
class MissionVisionPlan:
    target_description: str
    important_colors: list[str] = field(default_factory=list)
    possible_categories: list[str] = field(default_factory=list)
    context_hints: list[str] = field(default_factory=list)
    proposal_modes: list[str] = field(default_factory=list)
    semantic_prompt: str = ""
    full_frame_scan_interval_s: float = 2.0
    review_threshold: float = 0.35
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SearchPriority:
    name: str
    priority: int
    rationale: str
    cues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextualSearchPlan:
    likely_locations: list[SearchPriority] = field(default_factory=list)
    deprioritized_locations: list[SearchPriority] = field(default_factory=list)
    routing_guidance: list[str] = field(default_factory=list)
    required_context_sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class CandidateTarget:
    id: str
    timestamp: str
    position: Position | None
    source: str
    status: CandidateStatus = CandidateStatus.UNREVIEWED
    match_score: float = 0.0
    confidence_breakdown: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    semantic_score: float | None = None
    semantic_decision: SemanticDecision | None = None
    semantic_tags: list[str] = field(default_factory=list)
    image_path: str | None = None
    crop_path: str | None = None
    bbox: tuple[int, int, int, int] | None = None
    mission_objective: str | None = None


@dataclass(frozen=True)
class TargetConfig:
    type: str
    hsv_lower_1: tuple[int, int, int]
    hsv_upper_1: tuple[int, int, int]
    hsv_lower_2: tuple[int, int, int]
    hsv_upper_2: tuple[int, int, int]
    min_area_px: int
    required_confirm_frames: int


@dataclass(frozen=True)
class SearchConfig:
    pattern: str
    area_width_m: float
    area_height_m: float
    lane_spacing_m: float
    altitude_m: float
    search_speed_mps: float
    timeout_s: float


@dataclass(frozen=True)
class ApproachConfig:
    enabled: bool
    max_speed_mps: float
    stop_area_ratio: float
    center_tolerance_px: int


@dataclass(frozen=True)
class SearchMissionConfig:
    mission: MissionConfig
    target: TargetConfig
    search: SearchConfig
    approach: ApproachConfig


@dataclass
class SafetyStatus:
    action: SafetyAction = SafetyAction.NONE
    reason: str = "OK"

    @property
    def ok(self) -> bool:
        return self.action == SafetyAction.NONE


@dataclass
class MissionLogRow:
    timestamp: str
    mission_state: str
    x: float | None
    y: float | None
    z: float | None
    yaw: float | None
    target_x: float | None
    target_y: float | None
    target_z: float | None
    target_yaw: float | None
    active_waypoint_index: int | None
    safety_action: str
    safety_reason: str
    nav_state: int | None
    arming_state: int | None

    def as_csv_row(self) -> dict[str, Any]:
        return self.__dict__.copy()
