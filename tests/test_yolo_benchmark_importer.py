from __future__ import annotations

import csv
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.yolo_benchmark_importer import (
    generate_yolo_person_labels_csv,
    label_path_for_image,
    yolo_image_has_class,
)


def test_yolo_importer_generates_aegis_people_labels_csv() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        images = root / "images" / "train"
        labels = root / "labels" / "train"
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        (images / "person.jpg").write_bytes(b"fake image")
        (images / "vehicle.jpg").write_bytes(b"fake image")
        (images / "empty.jpg").write_bytes(b"fake image")
        (images / "missing_label.jpg").write_bytes(b"fake image")
        (labels / "person.txt").write_text("0 0.5 0.5 0.2 0.3\n2 0.2 0.2 0.1 0.1\n", encoding="utf-8")
        (labels / "vehicle.txt").write_text("2 0.5 0.5 0.2 0.3\n", encoding="utf-8")
        (labels / "empty.txt").write_text("", encoding="utf-8")

        output = generate_yolo_person_labels_csv(dataset_dir=root, output_csv=root / "sard_labels.csv")
        rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))

        by_name = {Path(row["image_path"]).name: row for row in rows}
        assert by_name["person.jpg"] == {
            "image_path": "images/train/person.jpg",
            "expected_match": "true",
            "label": "positive",
        }
        assert by_name["vehicle.jpg"]["expected_match"] == "false"
        assert by_name["vehicle.jpg"]["label"] == "negative"
        assert by_name["empty.jpg"]["expected_match"] == "false"
        assert by_name["missing_label.jpg"]["expected_match"] == "false"


def test_yolo_importer_supports_custom_person_class_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "images").mkdir()
        (root / "labels").mkdir()
        image = root / "images" / "target.png"
        image.write_bytes(b"fake image")
        (root / "labels" / "target.txt").write_text("3 0.5 0.5 0.2 0.2\n", encoding="utf-8")

        assert not yolo_image_has_class(image_path=image, dataset_dir=root, class_id=0)
        assert yolo_image_has_class(image_path=image, dataset_dir=root, class_id=3)


def test_label_path_for_image_maps_images_tree_to_labels_tree() -> None:
    root = Path("/dataset")
    image = root / "images" / "val" / "sample.jpg"
    assert label_path_for_image(image_path=image, dataset_dir=root) == root / "labels" / "val" / "sample.txt"


def test_label_path_for_image_maps_split_images_to_split_labels() -> None:
    root = Path("/dataset")
    image = root / "train" / "images" / "sample.jpg"
    assert label_path_for_image(image_path=image, dataset_dir=root) == root / "train" / "labels" / "sample.txt"


if __name__ == "__main__":
    tests = [
        test_yolo_importer_generates_aegis_people_labels_csv,
        test_yolo_importer_supports_custom_person_class_id,
        test_label_path_for_image_maps_images_tree_to_labels_tree,
        test_label_path_for_image_maps_split_images_to_split_labels,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
