from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from autonomy.yolo_benchmark_importer import collect_yolo_images, label_path_for_image


DEFAULT_OUTPUT_CSV = "datasets/benchmarks/vehicles/vehicle_labels.csv"
DEFAULT_STATS_JSON = "datasets/benchmarks/vehicles/vehicle_labels_stats.json"
VEHICLE_NAME_TERMS = {"vehicle", "car", "truck", "bus", "van", "jeep", "suv", "pickup", "atv"}


def generate_yolo_obb_vehicle_labels_csv(
    *,
    dataset_dir: str | Path,
    output_csv: str | Path = DEFAULT_OUTPUT_CSV,
    stats_json: str | Path | None = DEFAULT_STATS_JSON,
) -> tuple[Path, dict]:
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        raise ValueError(f"Dataset folder not found: {dataset_path}")

    class_names = read_class_names(dataset_path)
    vehicle_class_ids = vehicle_class_ids_from_names(class_names)
    if not vehicle_class_ids:
        raise ValueError(f"No vehicle classes found in dataset class list: {class_names}")

    image_paths = collect_yolo_images(dataset_path)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        "dataset_dir": str(dataset_path),
        "output_csv": str(output_path),
        "class_names": {str(class_id): name for class_id, name in sorted(class_names.items())},
        "vehicle_class_ids": sorted(vehicle_class_ids),
        "vehicle_class_names": [class_names[class_id] for class_id in sorted(vehicle_class_ids)],
        "images_processed": 0,
        "positive_images": 0,
        "negative_images": 0,
        "missing_label_files": 0,
        "empty_label_files": 0,
        "annotations_total": 0,
        "vehicle_annotations": 0,
        "class_counts": {},
        "split_counts": {},
    }
    class_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "expected_match", "label"])
        writer.writeheader()
        for image_path in image_paths:
            annotation = read_obb_annotation_summary(
                image_path=image_path,
                dataset_dir=dataset_path,
                vehicle_class_ids=vehicle_class_ids,
                class_names=class_names,
            )
            expected_match = annotation["has_vehicle"]
            relative_image_path = image_path.relative_to(dataset_path)
            writer.writerow(
                {
                    "image_path": str(relative_image_path),
                    "expected_match": "true" if expected_match else "false",
                    "label": "positive" if expected_match else "negative",
                }
            )

            stats["images_processed"] += 1
            stats["positive_images"] += 1 if expected_match else 0
            stats["negative_images"] += 0 if expected_match else 1
            stats["missing_label_files"] += 1 if annotation["missing_label_file"] else 0
            stats["empty_label_files"] += 1 if annotation["empty_label_file"] else 0
            stats["annotations_total"] += annotation["annotations_total"]
            stats["vehicle_annotations"] += annotation["vehicle_annotations"]
            class_counts.update(annotation["class_counts"])
            split_counts[dataset_split(relative_image_path)] += 1

    stats["class_counts"] = dict(sorted(class_counts.items()))
    stats["split_counts"] = dict(sorted(split_counts.items()))

    if stats_json:
        stats_path = Path(stats_json)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        stats["stats_json"] = str(stats_path)

    return output_path, stats


def read_class_names(dataset_dir: Path) -> dict[int, str]:
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        raise ValueError(f"Dataset class list not found: {data_yaml}")
    lines = data_yaml.read_text(encoding="utf-8").splitlines()
    names: dict[int, str] = {}
    in_names = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("names:"):
            in_names = True
            inline = stripped[len("names:") :].strip()
            if inline.startswith("[") and inline.endswith("]"):
                for index, name in enumerate(item.strip().strip("'\"") for item in inline.strip("[]").split(",")):
                    if name:
                        names[index] = name
            continue
        if in_names:
            match = re.match(r"^(\d+):\s*['\"]?([^'\"]+)['\"]?$", stripped)
            if match:
                names[int(match.group(1))] = match.group(2).strip()
                continue
            if not line.startswith((" ", "\t", "-")):
                break
    if not names:
        raise ValueError(f"No class names found in {data_yaml}")
    return names


def vehicle_class_ids_from_names(class_names: dict[int, str]) -> set[int]:
    vehicle_ids = set()
    for class_id, name in class_names.items():
        normalized = re.sub(r"[^a-z0-9]+", " ", name.lower())
        terms = set(normalized.split())
        if terms & VEHICLE_NAME_TERMS:
            vehicle_ids.add(class_id)
    return vehicle_ids


def read_obb_annotation_summary(
    *,
    image_path: Path,
    dataset_dir: Path,
    vehicle_class_ids: set[int],
    class_names: dict[int, str],
) -> dict:
    label_path = label_path_for_image(image_path=image_path, dataset_dir=dataset_dir)
    if label_path is None or not label_path.exists():
        return empty_annotation_summary(missing_label_file=True)

    raw_lines = [line.strip() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not raw_lines:
        return empty_annotation_summary(empty_label_file=True)

    class_counts: Counter[str] = Counter()
    vehicle_annotations = 0
    annotations_total = 0
    for line in raw_lines:
        parts = line.split()
        if not parts:
            continue
        try:
            class_id = int(float(parts[0]))
        except ValueError:
            continue
        annotations_total += 1
        class_name = class_names.get(class_id, str(class_id))
        class_counts[class_name] += 1
        if class_id in vehicle_class_ids:
            vehicle_annotations += 1

    return {
        "has_vehicle": vehicle_annotations > 0,
        "missing_label_file": False,
        "empty_label_file": False,
        "annotations_total": annotations_total,
        "vehicle_annotations": vehicle_annotations,
        "class_counts": class_counts,
    }


def empty_annotation_summary(*, missing_label_file: bool = False, empty_label_file: bool = False) -> dict:
    return {
        "has_vehicle": False,
        "missing_label_file": missing_label_file,
        "empty_label_file": empty_label_file,
        "annotations_total": 0,
        "vehicle_annotations": 0,
        "class_counts": Counter(),
    }


def dataset_split(relative_image_path: Path) -> str:
    if len(relative_image_path.parts) >= 2 and relative_image_path.parts[1] == "images":
        return relative_image_path.parts[0]
    if relative_image_path.parts:
        return relative_image_path.parts[0]
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert YOLO OBB vehicle labels into an Aegis benchmark labels CSV.")
    parser.add_argument("dataset_dir", help="YOLO OBB dataset folder containing data.yaml and split image/label folders")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV, help="Output Aegis labels CSV path")
    parser.add_argument("--stats-json", default=DEFAULT_STATS_JSON, help="Output import statistics JSON path")
    args = parser.parse_args()
    output_path, stats = generate_yolo_obb_vehicle_labels_csv(
        dataset_dir=args.dataset_dir,
        output_csv=args.output_csv,
        stats_json=args.stats_json,
    )
    print(f"Aegis vehicle labels CSV saved: {output_path}")
    print(f"Import statistics saved: {stats.get('stats_json')}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
