from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.mission_memory import build_mission_memory, mission_memory_snapshot


def test_mission_memory_summarizes_reports_and_reviews() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "logs" / "vision_lab" / "run"
        run.mkdir(parents=True)
        (run / "vision_report.json").write_text(
            json.dumps(
                {
                    "timestamp": "test",
                    "mission_request": "Search for vehicles",
                    "objective": {
                        "mission_type": "search_and_rescue",
                        "extracted_categories": ["vehicle"],
                    },
                    "summary": {"processed": 2, "shortlist_count": 1},
                    "evaluation": {
                        "precision": 0.5,
                        "recall": 1.0,
                        "f1": 0.667,
                        "false_positives": [{"image_path": "just grass.jpg"}],
                        "false_negatives": [{"image_path": "white truck.jpg"}],
                        "analyst_capture": {"recall": 1.0, "f1": 0.8},
                    },
                }
            ),
            encoding="utf-8",
        )
        (run / "candidate_reviews.json").write_text(
            json.dumps({"white truck.jpg::": {"status": "approved", "notes": "vehicle"}}),
            encoding="utf-8",
        )

        memory = build_mission_memory(root)
        assert memory["report_count"] == 1
        assert memory["review_statuses"]["approved"] == 1
        assert memory["category_metrics"]["vehicle"]["avg_capture_recall"] == 1.0
        assert "grass" in memory["common_false_positive_terms"]
        assert "truck" in memory["common_false_negative_terms"]
        assert "mission_memory_v1" in memory
        assert memory["recommendations"]


def test_mission_memory_snapshot_uses_report_patterns() -> None:
    snapshot = mission_memory_snapshot(
        {
            "objective": {"extracted_categories": ["boat"]},
            "evaluation": {
                "false_positives": [{"image_path": "bright shoreline debris.jpg"}],
                "false_negatives": [{"image_path": "small distant boat.jpg"}],
                "analyst_capture": {"recall": 0.5},
            },
        },
        {"candidate-1": {"decision": "reject", "reason": "shoreline debris"}},
    )
    assert "debris" in snapshot["false_positive_patterns"]
    assert "boat" in snapshot["miss_patterns"]
    assert "boat" in snapshot["weak_categories"]
    assert snapshot["recommended_data"]


if __name__ == "__main__":
    tests = [test_mission_memory_summarizes_reports_and_reviews, test_mission_memory_snapshot_uses_report_patterns]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
