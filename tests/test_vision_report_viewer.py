from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.vision_report_viewer import build_report_viewer


def test_build_report_viewer_writes_html() -> None:
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        report = folder / "vision_report.json"
        report.write_text(
            json.dumps(
                {
                    "timestamp": "test",
                    "mission_request": "Search for people",
                    "proposal_mode": "mission-color",
                    "scorer": "local",
                    "vision_plan": {
                        "important_colors": [],
                        "possible_categories": ["person"],
                        "context_hints": ["field"],
                        "proposal_modes": ["full_frame_scan"],
                    },
                    "summary": {
                        "processed": 2,
                        "detections": 1,
                        "shortlist_count": 1,
                        "shortlist": [
                            {
                                "image_path": "positive.jpg",
                                "score": 0.7,
                                "decision": "POSSIBLE_MATCH",
                                "detector_confidence": 0.6,
                                "bbox": [1, 2, 3, 4],
                            }
                        ],
                    },
                    "evaluation": {
                        "precision": 0.5,
                        "recall": 1.0,
                        "f1": 0.67,
                        "false_positive": 1,
                        "false_negative": 0,
                        "false_positives": [],
                        "false_negatives": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        output = build_report_viewer(report)
        html = output.read_text(encoding="utf-8")
        assert output.exists()
        assert "Vision Benchmark Report" in html
        assert "Search for people" in html
        assert "Precision" in html


if __name__ == "__main__":
    tests = [test_build_report_viewer_writes_html]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
