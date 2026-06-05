from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyst_server


def test_create_mission_plan_payload() -> None:
    payload = analyst_server.create_mission_plan_payload(
        {
            "mission_request": "Search the shoreline for a missing person wearing an orange vest",
            "operating_mode": "autonomous-return-report",
        }
    )
    assert payload["ok"] is True
    assert payload["command"]["raw_request"].startswith("Search the shoreline")
    assert payload["command"]["operating_mode"] == "AUTONOMOUS_RETURN_REPORT"
    assert payload["command"]["confirmation_mode"] == "STORE_FOR_REVIEW"
    assert "orange" in payload["vision_plan"]["important_colors"]
    assert "person" in payload["vision_plan"]["possible_categories"]
    assert payload["contextual_search_plan"]["likely_locations"]
    assert payload["next_actions"]


def test_load_report_payload_and_save_review() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        logs = root / "logs" / "vision_lab" / "run"
        logs.mkdir(parents=True)
        report_path = logs / "vision_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "timestamp": "test",
                    "mission_request": "Search for people",
                    "summary": {"processed": 1, "detections": 1, "shortlist_count": 1},
                    "evaluation": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "results": [],
                }
            ),
            encoding="utf-8",
        )
        old_root = analyst_server.ROOT
        try:
            analyst_server.ROOT = root
            payload = analyst_server.load_report_payload("logs/vision_lab/run/vision_report.json")
            assert payload["ok"] is True
            result = analyst_server.save_review(
                {
                    "report_path": "logs/vision_lab/run/vision_report.json",
                    "candidate_key": "candidate-42",
                    "candidate_id": "candidate-42",
                    "decision": "reject",
                    "reason": "shoreline debris",
                    "notes": "Looks relevant",
                }
            )
            assert result["ok"] is True
            reviews = analyst_server.load_reviews(report_path)
            assert reviews["candidate-42"]["candidate_id"] == "candidate-42"
            assert reviews["candidate-42"]["decision"] == "reject"
            assert reviews["candidate-42"]["reason"] == "shoreline debris"
            assert reviews["candidate-42"]["updated_at"]
            memory = analyst_server.build_mission_memory(root)
            assert memory["report_count"] == 1
        finally:
            analyst_server.ROOT = old_root


if __name__ == "__main__":
    tests = [test_create_mission_plan_payload, test_load_report_payload_and_save_review]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
