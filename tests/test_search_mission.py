from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.camera_interface import CameraFrameSource, CvBridgeImageConverter
from autonomy.config_loader import load_search_mission_config
from autonomy.mission_command import create_mission_command
from autonomy.red_block_detector import DetectionConfirmation, RedBlockDetector
from autonomy.search_mission_manager import SearchMissionManager
from autonomy.search_patterns import generate_search_waypoints
from autonomy.types import Position, SearchMissionState, VehicleStatusSnapshot


class MockController:
    def __init__(self) -> None:
        self.position = Position(0.0, 0.0, 0.0, 0.0)
        self.status = VehicleStatusSnapshot(arming_state=0, nav_state=0, connected=True)
        self.setpoints: list[Position] = []
        self.commands: list[str] = []

    def arm(self) -> None:
        self.commands.append("arm")
        self.status.arming_state = 2

    def disarm(self) -> None:
        self.commands.append("disarm")
        self.status.arming_state = 0

    def set_offboard_mode(self) -> None:
        self.commands.append("offboard")
        self.status.nav_state = 14

    def land(self) -> None:
        self.commands.append("land")

    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float) -> None:
        self.setpoints.append(Position(x, y, z, yaw))

    def get_position(self) -> Position:
        return self.position

    def get_vehicle_status(self) -> VehicleStatusSnapshot:
        return self.status

    def is_armed(self) -> bool:
        return self.status.arming_state == 2

    def is_offboard(self) -> bool:
        return self.status.nav_state == 14

    def has_valid_local_position(self) -> bool:
        return True


class StaticFrameSource(CameraFrameSource):
    def __init__(self, frame: np.ndarray | None) -> None:
        self.frame = frame

    def latest_frame(self):
        return self.frame


class FailingFrameSource(CameraFrameSource):
    def latest_frame(self):
        raise RuntimeError("camera unavailable")


class FakeBridge:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame

    def imgmsg_to_cv2(self, msg, desired_encoding: str):
        assert desired_encoding == "bgr8"
        assert msg == "fake_ros_image"
        return self.frame


def red_block_image(width: int = 640, height: int = 480, block: tuple[int, int, int, int] = (250, 170, 120, 90)) -> np.ndarray:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (40, 60, 40)
    x, y, w, h = block
    cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), -1)
    return image


def test_red_block_detection_from_sample_image() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    detector = RedBlockDetector(config.target)
    detection = detector.detect(red_block_image())
    assert detection.detected
    assert detection.confidence > 0.7
    assert detection.bbox is not None


def test_false_positive_filtering() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    detector = RedBlockDetector(config.target)
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (320, 240), 8, (0, 0, 255), -1)
    detection = detector.detect(image)
    assert not detection.detected


def test_search_pattern_generation() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    waypoints = generate_search_waypoints(config.search)
    assert len(waypoints) >= 10
    assert min(wp.x for wp in waypoints) == -10
    assert max(wp.x for wp in waypoints) == 10
    assert all(wp.z == -5 for wp in waypoints)


def test_target_confirmation_logic() -> None:
    confirmation = DetectionConfirmation(required_frames=5)
    config = load_search_mission_config("config/autonomy.yaml")
    detector = RedBlockDetector(config.target)
    detection = detector.detect(red_block_image())
    results = [confirmation.update(detection) for _ in range(4)]
    assert results[-1] is False
    assert confirmation.update(detection) is True


def test_timeout_return_home_behavior() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    controller = MockController()
    camera = StaticFrameSource(None)
    with TemporaryDirectory() as tmp:
        manager = SearchMissionManager(controller=controller, config=config, camera=camera, log_dir=tmp)
        manager.start(now_s=0.0)
        controller.status.arming_state = 2
        controller.status.nav_state = 14
        controller.position = Position(5.0, 0.0, -5.0, 0.0)
        manager.state = SearchMissionState.SEARCH_PATTERN
        manager.home = Position(0.0, 0.0, 0.0, 0.0)
        manager.tick(now_s=config.search.timeout_s + 1.0, dt_s=0.05)
        manager.close()
    assert manager.state == SearchMissionState.RETURN_HOME


def test_mock_ros_image_input_passes_frame_to_detector() -> None:
    frame = red_block_image()
    converter = CvBridgeImageConverter(FakeBridge(frame))
    converted = converter.to_bgr("fake_ros_image")
    config = load_search_mission_config("config/autonomy.yaml")
    detection = RedBlockDetector(config.target).detect(converted)
    assert detection.detected


def test_search_mission_handles_missing_camera() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    controller = MockController()
    with TemporaryDirectory() as tmp:
        manager = SearchMissionManager(controller=controller, config=config, camera=FailingFrameSource(), log_dir=tmp)
        manager.start(now_s=0.0)
        controller.status.arming_state = 2
        controller.status.nav_state = 14
        controller.position = Position(0.0, 0.0, -5.0, 0.0)
        manager.state = SearchMissionState.SEARCH_PATTERN
        manager.home = Position(0.0, 0.0, 0.0, 0.0)
        manager.tick(now_s=1.0, dt_s=0.05)
        manager.close()
    assert manager.last_detection.detected is False
    assert manager.state == SearchMissionState.SEARCH_PATTERN


def test_detection_snapshot_is_saved() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    detector = RedBlockDetector(config.target)
    image = red_block_image()
    detection = detector.detect(image)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "snapshot.png"
        detector.save_snapshot(image, path, detection)
        assert path.exists()
        saved = cv2.imread(str(path))
        assert saved is not None
        assert saved.shape[1] == image.shape[1] * 3


def test_search_mission_updates_world_model() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    controller = MockController()
    camera = StaticFrameSource(red_block_image())
    with TemporaryDirectory() as tmp:
        manager = SearchMissionManager(controller=controller, config=config, camera=camera, log_dir=tmp)
        manager.start(now_s=0.0)
        controller.status.arming_state = 2
        controller.status.nav_state = 14
        controller.position = Position(0.0, 0.0, -5.0, 0.0)
        manager.state = SearchMissionState.SEARCH_PATTERN
        manager.home = Position(0.0, 0.0, 0.0, 0.0)
        manager.tick(now_s=1.0, dt_s=0.05)
        manager.close()
    assert len(manager.world_model.searched_cells) >= 1
    assert manager.world_model.target_candidates
    assert manager.candidate_manager.candidates
    assert manager.candidate_manager.candidates[0].semantic_score is not None
    assert manager.candidate_manager.candidates[0].crop_path is not None


def test_search_mission_exports_artifacts_on_close() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    controller = MockController()
    camera = StaticFrameSource(red_block_image())
    with TemporaryDirectory() as tmp:
        manager = SearchMissionManager(controller=controller, config=config, camera=camera, log_dir=tmp)
        manager.start(now_s=0.0)
        controller.status.arming_state = 2
        controller.status.nav_state = 14
        controller.position = Position(0.0, 0.0, -5.0, 0.0)
        manager.state = SearchMissionState.SEARCH_PATTERN
        manager.home = Position(0.0, 0.0, 0.0, 0.0)
        manager.tick(now_s=1.0, dt_s=0.05)
        artifacts = manager.export_artifacts()
        manager.close()
        assert Path(artifacts["search_log"]).exists()
        assert Path(artifacts["world_model_json"]).exists()
        assert Path(artifacts["world_model_heatmap"]).exists()
        assert artifacts["debug_camera"] is not None
        assert Path(artifacts["debug_camera"]).exists()
        assert artifacts["target_snapshot"] is not None
        assert Path(artifacts["target_snapshot"]).exists()
        assert artifacts["candidates"] is not None
        assert Path(artifacts["candidates"]).exists()
        assert artifacts["mission_command"] is not None
        assert Path(artifacts["mission_command"]).exists()


def test_search_mission_accepts_autonomous_mission_command() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    controller = MockController()
    camera = StaticFrameSource(red_block_image())
    command = create_mission_command(
        "Search the shoreline for possible signs of a missing person",
        operating_mode="autonomous-return-report",
    )
    with TemporaryDirectory() as tmp:
        manager = SearchMissionManager(
            controller=controller,
            config=config,
            camera=camera,
            log_dir=tmp,
            mission_command=command,
        )
        assert manager.mission_command.operating_mode.value == "AUTONOMOUS_RETURN_REPORT"
        assert manager.objective.raw_request == command.objective.raw_request


if __name__ == "__main__":
    tests = [
        test_red_block_detection_from_sample_image,
        test_false_positive_filtering,
        test_search_pattern_generation,
        test_target_confirmation_logic,
        test_timeout_return_home_behavior,
        test_mock_ros_image_input_passes_frame_to_detector,
        test_search_mission_handles_missing_camera,
        test_detection_snapshot_is_saved,
        test_search_mission_updates_world_model,
        test_search_mission_exports_artifacts_on_close,
        test_search_mission_accepts_autonomous_mission_command,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
