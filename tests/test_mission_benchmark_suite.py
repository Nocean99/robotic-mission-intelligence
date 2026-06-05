from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.mission_benchmark_suite import run_benchmark_suite


def red_block_image() -> np.ndarray:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[:] = (30, 50, 30)
    cv2.rectangle(image, (120, 80), (200, 150), (0, 0, 255), -1)
    return image


def test_benchmark_suite_writes_aggregate_report() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        image_dir = root / "images"
        image_dir.mkdir()
        cv2.imwrite(str(image_dir / "positive.png"), red_block_image())
        labels = root / "labels.csv"
        labels.write_text("image_path,expected_match,label\npositive.png,true,target\n", encoding="utf-8")
        suite = root / "suite.json"
        suite.write_text(
            json.dumps(
                {
                    "suite_name": "test-suite",
                    "benchmarks": [
                        {
                            "id": "red_marker",
                            "enabled": True,
                            "mission_type": "signal",
                            "mission_request": "Search for a red marker",
                            "paths": [str(image_dir)],
                            "labels_csv": str(labels),
                            "semantic_vision": "local",
                            "eval_threshold": 0.1,
                        },
                        {
                            "id": "disabled_case",
                            "enabled": False,
                            "mission_type": "boat",
                            "mission_request": "Search for a boat",
                            "paths": [str(image_dir)],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        report_path = run_benchmark_suite(suite_path=suite, output_dir=root / "out")
        report = json.loads(report_path.read_text(encoding="utf-8"))

        assert report_path.exists()
        assert report_path.with_name("mission_benchmark_suite_report.html").exists()
        assert report["summary"]["completed"] == 1
        assert report["summary"]["skipped"] == 1
        assert report["summary"]["avg_confirmed_recall"] == 1.0
        assert report["summary"]["avg_capture_recall"] == 1.0
        assert report["benchmarks"][0]["status"] == "ok"


if __name__ == "__main__":
    tests = [test_benchmark_suite_writes_aggregate_report]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
