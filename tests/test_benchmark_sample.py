from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.benchmark_sample import create_balanced_sample
from autonomy.benchmark_sample import create_api_review_sample


def test_create_balanced_sample_writes_images_and_labels() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = root / "dataset"
        images = dataset / "images"
        images.mkdir(parents=True)
        labels = root / "labels.csv"
        lines = ["image_path,expected_match,label\n"]
        for index in range(8):
            name = f"positive_{index}.jpg"
            (images / name).write_bytes(b"image")
            lines.append(f"images/{name},true,positive\n")
        for index in range(8):
            name = f"negative_{index}.jpg"
            (images / name).write_bytes(b"image")
            lines.append(f"images/{name},false,negative\n")
        labels.write_text("".join(lines), encoding="utf-8")

        sample_labels = create_balanced_sample(
            dataset_dir=dataset,
            labels_csv=labels,
            output_dir=root / "sample",
            max_images=10,
            seed=1,
        )
        rows = list(csv.DictReader(sample_labels.open(newline="", encoding="utf-8")))
        counts = Counter(row["expected_match"] for row in rows)
        assert len(rows) == 10
        assert counts["true"] == 5
        assert counts["false"] == 5
        assert all((sample_labels.parent / row["image_path"]).exists() for row in rows)


def test_create_api_review_sample_uses_policy_buckets() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = root / "dataset"
        images = dataset / "images"
        images.mkdir(parents=True)
        labels = root / "labels.csv"
        label_lines = ["image_path,expected_match,label\n"]
        results = []
        for index in range(12):
            name = f"image_{index}.jpg"
            source = images / name
            source.write_bytes(b"image")
            expected = index % 2 == 0
            label_lines.append(f"images/{name},{str(expected).lower()},{'positive' if expected else 'negative'}\n")
            results.append(
                {
                    "image_path": str(source),
                    "candidate_id": f"candidate-{index}",
                    "review_priority": 1.0 - index * 0.05,
                    "uncertainty_score": index / 12,
                    "final_decision": "REJECT" if index in {4, 6} else "NEEDS_REVIEW",
                    "final_score": 0.2,
                    "label": {"expected_match": expected, "label": "positive" if expected else "negative"},
                }
            )
        labels.write_text("".join(label_lines), encoding="utf-8")
        report = root / "local_report.json"
        report.write_text(
            __import__("json").dumps({"vision_report": {"results": results}}),
            encoding="utf-8",
        )

        sample_labels = create_api_review_sample(
            local_report=report,
            dataset_dir=dataset,
            labels_csv=labels,
            output_dir=root / "api_sample",
            max_images=8,
            seed=2,
        )
        rows = list(csv.DictReader(sample_labels.open(newline="", encoding="utf-8")))
        manifest = __import__("json").loads((sample_labels.parent / "selection_manifest.json").read_text(encoding="utf-8"))
        reasons = {reason for item in manifest for reason in item["selection_reasons"]}
        assert len(rows) == 8
        assert "top_review_priority" in reasons
        assert "high_uncertainty" in reasons
        assert "local_miss_or_reject" in reasons
        assert "balanced_benchmark_sample" in reasons


if __name__ == "__main__":
    tests = [test_create_balanced_sample_writes_images_and_labels, test_create_api_review_sample_uses_policy_buckets]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
