from __future__ import annotations

import argparse

from autonomy.config_loader import load_search_mission_config
from autonomy.types import Position, SearchMissionState, TargetDetection
from autonomy.world_model import WorldModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a sample world-model JSON and heatmap snapshot")
    parser.add_argument("--config", default="config/autonomy.yaml")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()

    config = load_search_mission_config(args.config)
    model = WorldModel(search_config=config.search, log_dir=args.log_dir)
    model.set_home(Position(0, 0, 0, 0))
    model.set_safety_radius(config.mission.max_distance_from_home_m)
    model.update_pose(Position(0, 0, -5, 0), SearchMissionState.SEARCH_PATTERN, now_s=1.0)
    model.update_pose(Position(3, 0, -5, 0), SearchMissionState.SEARCH_PATTERN, now_s=2.0)
    model.update_detection(
        TargetDetection(True, confidence=0.82, bbox=(250, 170, 120, 90), center_px=(320, 240), area_ratio=0.08),
        Position(3, 0, -5, 0),
        now_s=2.0,
    )
    json_path = model.save_snapshot_json()
    heatmap_path = model.save_heatmap()
    print(f"World model JSON: {json_path}")
    print(f"World model PNG heatmap: {heatmap_path}")


if __name__ == "__main__":
    main()
