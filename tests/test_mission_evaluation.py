from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.mission_evaluation import effective_full_frame_semantic_mode, run_mission_evaluation


def red_block_image() -> np.ndarray:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[:] = (30, 50, 30)
    cv2.rectangle(image, (120, 80), (200, 150), (0, 0, 255), -1)
    return image


def test_mission_evaluation_writes_combined_report() -> None:
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        image_path = folder / "positive.png"
        labels = folder / "labels.csv"
        cv2.imwrite(str(image_path), red_block_image())
        labels.write_text("image_path,expected_match,label\npositive.png,true,target\n", encoding="utf-8")

        report_path = run_mission_evaluation(
            mission_request="Search the shoreline for a red rescue marker",
            paths=[str(image_path)],
            output_dir=folder / "out",
            labels_csv=labels,
            eval_threshold=0.1,
            save_only_detections=True,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))

        assert report_path.exists()
        assert report_path.with_name("mission_evaluation_report.html").exists()
        assert report["command"]["raw_request"].startswith("Search the shoreline")
        assert report["contextual_search_plan"]["likely_locations"]
        assert report["vision_summary"]["processed"] == 1
        assert report["vision_summary"]["detections"] == 1
        assert report["mission_memory"]["false_positive_patterns"] == []
        assert report["mission_memory"]["recommended_data"]
        assert report["stage_summary"]["error"] == 0


def test_mission_evaluation_contains_failures_without_crashing_report() -> None:
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        report_path = run_mission_evaluation(
            mission_request="Search for anything unusual",
            paths=[str(folder / "missing")],
            operating_mode="unknown-mode",
            output_dir=folder / "out",
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))

        assert report["stage_summary"]["error"] >= 1
        assert report["stage_summary"]["skipped"] == 1
        assert report["evidence_count"] == 0
        assert any(stage["name"] == "mission_command" and stage["status"] == "error" for stage in report["stages"])
        assert report_path.with_name("mission_evaluation_report.html").exists()


def test_openai_mission_evaluation_defaults_to_reviewing_detector_misses() -> None:
    assert effective_full_frame_semantic_mode("openai", "off") == "misses"
    assert effective_full_frame_semantic_mode("openai", "all") == "all"
    assert effective_full_frame_semantic_mode("local", "off") == "off"


if __name__ == "__main__":
    tests = [
        test_mission_evaluation_writes_combined_report,
        test_mission_evaluation_contains_failures_without_crashing_report,
        test_openai_mission_evaluation_defaults_to_reviewing_detector_misses,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
