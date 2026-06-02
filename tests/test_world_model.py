from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.config_loader import load_search_mission_config
from autonomy.types import Position, SearchMissionState, TargetDetection
from autonomy.world_model import WorldModel


def test_world_model_marks_searched_cells() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    model = WorldModel(search_config=config.search)
    model.update_pose(Position(0, 0, -5, 0), SearchMissionState.SEARCH_PATTERN, now_s=1.0)
    assert len(model.searched_cells) == 1
    assert len(model.unsearched_cells) == model.rows * model.cols - 1


def test_world_model_updates_and_decays_target_confidence() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    model = WorldModel(search_config=config.search, confidence_decay_per_s=0.1)
    pose = Position(0, 0, -5, 0)
    detection = TargetDetection(True, confidence=0.8, bbox=(10, 10, 50, 50), center_px=(320, 240), area_ratio=0.1)
    model.update_detection(detection, pose, now_s=1.0)
    assert model.target_candidates
    confident_cells = [cell for row in model.grid for cell in row if cell.target_confidence > 0]
    assert confident_cells
    before = max(cell.target_confidence for cell in confident_cells)
    model.decay_confidence(now_s=5.0)
    after = max(cell.target_confidence for row in model.grid for cell in row)
    assert after <= before


def test_world_model_selects_unsearched_waypoint() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    model = WorldModel(search_config=config.search)
    model.update_pose(Position(0, 0, -5, 0), SearchMissionState.SEARCH_PATTERN, now_s=1.0)
    waypoint = model.next_unsearched_waypoint(altitude_m=5)
    assert waypoint is not None
    assert waypoint.z == -5
    assert model.cell_for_position(waypoint.x, waypoint.y) in model.unsearched_cells


def test_world_model_saves_snapshot_and_heatmap() -> None:
    config = load_search_mission_config("config/autonomy.yaml")
    with TemporaryDirectory() as tmp:
        model = WorldModel(search_config=config.search, log_dir=tmp)
        model.update_pose(Position(0, 0, -5, 0), SearchMissionState.SEARCH_PATTERN, now_s=1.0)
        json_path = model.save_snapshot_json()
        heatmap_path = model.save_heatmap()
        assert json_path.exists()
        assert heatmap_path.exists()
        data = json.loads(json_path.read_text())
        assert data["searched_cells"] == 1
        assert "grid" in data


if __name__ == "__main__":
    tests = [
        test_world_model_marks_searched_cells,
        test_world_model_updates_and_decays_target_confidence,
        test_world_model_selects_unsearched_waypoint,
        test_world_model_saves_snapshot_and_heatmap,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
