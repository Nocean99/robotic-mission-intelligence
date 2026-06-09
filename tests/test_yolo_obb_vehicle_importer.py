from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.yolo_obb_vehicle_importer import (
    generate_yolo_obb_vehicle_labels_csv,
    read_class_names,
    vehicle_class_ids_from_names,
)


def test_reads_vehicle_class_list_from_data_yaml() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "data.yaml").write_text(
            """
names:
  0: small-vehicle
  1: large-vehicle
  2: building
""",
            encoding="utf-8",
        )

        class_names = read_class_names(root)
        assert class_names == {0: "small-vehicle", 1: "large-vehicle", 2: "building"}
        assert vehicle_class_ids_from_names(class_names) == {0, 1}


def test_yolo_obb_vehicle_importer_writes_labels_and_stats() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "data.yaml").write_text(
            """
nc: 3
names:
  0: small-vehicle
  1: large-vehicle
  2: building
""",
            encoding="utf-8",
        )
        train_images = root / "train" / "images"
        train_labels = root / "train" / "labels"
        val_images = root / "val" / "images"
        val_labels = root / "val" / "labels"
        train_images.mkdir(parents=True)
        train_labels.mkdir(parents=True)
        val_images.mkdir(parents=True)
        val_labels.mkdir(parents=True)

        (train_images / "small_vehicle.jpg").write_bytes(b"fake image")
        (train_images / "large_vehicle.jpg").write_bytes(b"fake image")
        (train_images / "building_only.jpg").write_bytes(b"fake image")
        (val_images / "missing_label.jpg").write_bytes(b"fake image")

        obb_points = "0.1 0.1 0.2 0.1 0.2 0.2 0.1 0.2"
        (train_labels / "small_vehicle.txt").write_text(f"0 {obb_points}\n", encoding="utf-8")
        (train_labels / "large_vehicle.txt").write_text(f"1 {obb_points}\n", encoding="utf-8")
        (train_labels / "building_only.txt").write_text(f"2 {obb_points}\n", encoding="utf-8")

        labels_csv, stats = generate_yolo_obb_vehicle_labels_csv(
            dataset_dir=root,
            output_csv=root / "vehicle_labels.csv",
            stats_json=root / "vehicle_labels_stats.json",
        )

        rows = list(csv.DictReader(labels_csv.open(newline="", encoding="utf-8")))
        by_name = {Path(row["image_path"]).name: row for row in rows}
        assert by_name["small_vehicle.jpg"]["expected_match"] == "true"
        assert by_name["large_vehicle.jpg"]["expected_match"] == "true"
        assert by_name["building_only.jpg"]["expected_match"] == "false"
        assert by_name["missing_label.jpg"]["expected_match"] == "false"
        assert by_name["small_vehicle.jpg"]["label"] == "positive"
        assert by_name["building_only.jpg"]["label"] == "negative"

        assert stats["images_processed"] == 4
        assert stats["positive_images"] == 2
        assert stats["negative_images"] == 2
        assert stats["missing_label_files"] == 1
        assert stats["annotations_total"] == 3
        assert stats["vehicle_annotations"] == 2
        assert stats["class_counts"] == {"building": 1, "large-vehicle": 1, "small-vehicle": 1}
        saved_stats = json.loads((root / "vehicle_labels_stats.json").read_text(encoding="utf-8"))
        assert saved_stats["vehicle_class_names"] == ["small-vehicle", "large-vehicle"]


if __name__ == "__main__":
    tests = [
        test_reads_vehicle_class_list_from_data_yaml,
        test_yolo_obb_vehicle_importer_writes_labels_and_stats,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
