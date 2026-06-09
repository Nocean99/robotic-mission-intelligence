from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
DEFAULT_STATS_JSON = "datasets/benchmarks/vehicles/dronevehicle_stats.json"
DEFAULT_ANALYSIS_DOC = "docs/DRONEVEHICLE_BENCHMARK_ANALYSIS.md"
DEFAULT_RGB_LABELS = "datasets/benchmarks/vehicles/dronevehicle_rgb_labels.csv"
DEFAULT_IR_LABELS = "datasets/benchmarks/vehicles/dronevehicle_ir_labels.csv"
SOURCE_DATASET = "dronevehicle"
TARGET_VEHICLE_CLASSES = {
    "car",
    "truck",
    "bus",
    "van",
    "freight car",
    "small vehicle",
    "large vehicle",
}
CLASS_ALIASES = {
    "small-vehicle": "small vehicle",
    "large-vehicle": "large vehicle",
    "feright": "freight car",
    "feright car": "freight car",
    "truvk": "truck",
}


@dataclass(frozen=True)
class ModalitySplit:
    split: str
    modality: str
    image_dir: Path
    annotation_dir: Path


def analyze_dronevehicle_benchmark(
    *,
    dataset_dir: str | Path,
    stats_json: str | Path = DEFAULT_STATS_JSON,
    analysis_doc: str | Path = DEFAULT_ANALYSIS_DOC,
) -> dict:
    dataset_path = Path(dataset_dir)
    stats = build_dronevehicle_stats(dataset_path)
    stats_path = Path(stats_json)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(public_stats(stats), indent=2), encoding="utf-8")
    doc_path = Path(analysis_doc)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(render_analysis_doc(stats), encoding="utf-8")
    return public_stats(stats)


def import_dronevehicle_vehicle_benchmark(
    *,
    dataset_dir: str | Path,
    rgb_output_csv: str | Path = DEFAULT_RGB_LABELS,
    ir_output_csv: str | Path = DEFAULT_IR_LABELS,
    stats_json: str | Path = DEFAULT_STATS_JSON,
    analysis_doc: str | Path = DEFAULT_ANALYSIS_DOC,
) -> dict:
    dataset_path = Path(dataset_dir)
    stats = build_dronevehicle_stats(dataset_path)
    write_modality_labels_csv(
        rows=label_rows_for_modality(stats=stats, modality="rgb"),
        output_csv=Path(rgb_output_csv),
    )
    write_modality_labels_csv(
        rows=label_rows_for_modality(stats=stats, modality="infrared"),
        output_csv=Path(ir_output_csv),
    )
    stats["outputs"] = {
        "rgb_labels_csv": str(rgb_output_csv),
        "ir_labels_csv": str(ir_output_csv),
        "stats_json": str(stats_json),
        "analysis_doc": str(analysis_doc),
    }
    stats_path = Path(stats_json)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(public_stats(stats), indent=2), encoding="utf-8")
    doc_path = Path(analysis_doc)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(render_analysis_doc(stats), encoding="utf-8")
    return public_stats(stats)


def build_dronevehicle_stats(dataset_dir: Path) -> dict:
    if not dataset_dir.exists():
        raise ValueError(f"Dataset folder not found: {dataset_dir}")

    modality_splits = discover_modality_splits(dataset_dir)
    if not modality_splits:
        raise ValueError(f"No DroneVehicle RGB/IR split folders found in {dataset_dir}")

    modalities = {
        "rgb": empty_modality_stats(),
        "infrared": empty_modality_stats(),
    }
    split_counts: dict[str, dict] = {}
    total_class_distribution: Counter[str] = Counter()
    annotation_format = "Pascal VOC XML with oriented polygon points"

    for split in sorted({item.split for item in modality_splits}):
        split_counts[split] = {}

    for spec in modality_splits:
        images = collect_images(spec.image_dir)
        image_stems = {image.stem for image in images}
        annotation_files = sorted(spec.annotation_dir.glob("*.xml")) if spec.annotation_dir.exists() else []
        annotation_stems = {path.stem for path in annotation_files}
        annotated_images = 0
        unannotated_images = 0
        vehicle_positive_images = 0
        class_distribution: Counter[str] = Counter()
        annotation_count = 0
        label_rows = []

        for image in images:
            annotation_path = spec.annotation_dir / f"{image.stem}.xml"
            parsed = parse_dronevehicle_annotation(annotation_path)
            annotation_count += parsed["annotation_count"]
            class_distribution.update(parsed["class_distribution"])
            total_class_distribution.update(parsed["class_distribution"])
            has_annotation = parsed["annotation_count"] > 0
            has_vehicle = parsed["vehicle_annotation_count"] > 0
            annotated_images += 1 if has_annotation else 0
            unannotated_images += 0 if has_annotation else 1
            vehicle_positive_images += 1 if has_vehicle else 0
            label_rows.append(
                {
                    "image_path": str(image.relative_to(dataset_dir)),
                    "expected_match": "true" if has_vehicle else "false",
                    "label": "positive" if has_vehicle else "negative",
                    "modality": spec.modality,
                    "source_dataset": SOURCE_DATASET,
                    "split": spec.split,
                    "annotation_count": parsed["annotation_count"],
                }
            )

        modality_stats = modalities[spec.modality]
        modality_stats["total_images"] += len(images)
        modality_stats["images_with_annotations"] += annotated_images
        modality_stats["images_without_annotations"] += unannotated_images
        modality_stats["positive_images"] += vehicle_positive_images
        modality_stats["negative_images"] += len(images) - vehicle_positive_images
        modality_stats["total_annotations"] += annotation_count
        modality_stats["class_distribution"].update(class_distribution)
        modality_stats["label_rows"].extend(label_rows)
        split_counts[spec.split][spec.modality] = {
            "images": len(images),
            "annotation_files": len(annotation_files),
            "images_with_annotation_files": len(image_stems & annotation_stems),
            "images_without_annotation_files": len(image_stems - annotation_stems),
        }

    pair_counts = pair_counts_by_split(dataset_dir)
    total_images = sum(item["total_images"] for item in modalities.values())
    total_annotations = sum(item["total_annotations"] for item in modalities.values())
    total_positive = sum(item["positive_images"] for item in modalities.values())
    total_negative = sum(item["negative_images"] for item in modalities.values())
    precision_measurable = total_negative > 0

    clean_modalities = {}
    for modality, data in modalities.items():
        clean_modalities[modality] = {
            key: (dict(value.most_common()) if isinstance(value, Counter) else value)
            for key, value in data.items()
            if key != "label_rows"
        }

    return {
        "dataset_dir": str(dataset_dir),
        "source_dataset": SOURCE_DATASET,
        "folder_structure": folder_structure_summary(dataset_dir),
        "annotation_format": annotation_format,
        "target_vehicle_classes": sorted(TARGET_VEHICLE_CLASSES),
        "class_aliases": CLASS_ALIASES,
        "total_rgb_images": modalities["rgb"]["total_images"],
        "total_ir_images": modalities["infrared"]["total_images"],
        "total_annotations": total_annotations,
        "class_distribution": dict(total_class_distribution.most_common()),
        "images_with_annotations": sum(item["images_with_annotations"] for item in modalities.values()),
        "images_without_annotations": sum(item["images_without_annotations"] for item in modalities.values()),
        "positive_images": total_positive,
        "negative_images": total_negative,
        "rgb_ir_pair_counts": pair_counts,
        "splits": split_counts,
        "modalities": clean_modalities,
        "precision_can_be_measured_directly": precision_measurable,
        "recall_focused_benchmark": not precision_measurable,
        "recommended_benchmark_strategy": recommended_benchmark_strategy(precision_measurable),
        "_label_rows": {
            "rgb": modalities["rgb"]["label_rows"],
            "infrared": modalities["infrared"]["label_rows"],
        },
    }


def discover_modality_splits(dataset_dir: Path) -> list[ModalitySplit]:
    specs = []
    for split in ("train", "val", "test"):
        split_dir = dataset_dir / split
        if not split_dir.exists():
            continue
        specs.extend(
            [
                ModalitySplit(
                    split=split,
                    modality="rgb",
                    image_dir=split_dir / f"{split}img",
                    annotation_dir=split_dir / f"{split}label",
                ),
                ModalitySplit(
                    split=split,
                    modality="infrared",
                    image_dir=split_dir / f"{split}imgr",
                    annotation_dir=split_dir / f"{split}labelr",
                ),
            ]
        )
    return [spec for spec in specs if spec.image_dir.exists()]


def empty_modality_stats() -> dict:
    return {
        "total_images": 0,
        "images_with_annotations": 0,
        "images_without_annotations": 0,
        "positive_images": 0,
        "negative_images": 0,
        "total_annotations": 0,
        "class_distribution": Counter(),
        "label_rows": [],
    }


def parse_dronevehicle_annotation(annotation_path: Path) -> dict:
    if not annotation_path.exists():
        return {
            "annotation_count": 0,
            "vehicle_annotation_count": 0,
            "class_distribution": Counter(),
        }
    try:
        root = ET.parse(annotation_path).getroot()
    except ET.ParseError:
        return {
            "annotation_count": 0,
            "vehicle_annotation_count": 0,
            "class_distribution": Counter(),
        }

    class_distribution: Counter[str] = Counter()
    vehicle_count = 0
    for obj in root.findall("object"):
        raw_name = obj.findtext("name", default="unknown")
        class_name = normalize_vehicle_class(raw_name)
        class_distribution[class_name] += 1
        if class_name in TARGET_VEHICLE_CLASSES:
            vehicle_count += 1
    return {
        "annotation_count": sum(class_distribution.values()),
        "vehicle_annotation_count": vehicle_count,
        "class_distribution": class_distribution,
    }


def normalize_vehicle_class(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower().replace("_", " ").replace("-", " "))
    return CLASS_ALIASES.get(normalized, normalized)


def collect_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        return []
    return sorted(path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def pair_counts_by_split(dataset_dir: Path) -> dict:
    counts = {}
    for split in ("train", "val", "test"):
        split_dir = dataset_dir / split
        rgb_dir = split_dir / f"{split}img"
        ir_dir = split_dir / f"{split}imgr"
        if not rgb_dir.exists() or not ir_dir.exists():
            continue
        rgb_stems = {path.stem for path in collect_images(rgb_dir)}
        ir_stems = {path.stem for path in collect_images(ir_dir)}
        counts[split] = {
            "rgb_images": len(rgb_stems),
            "ir_images": len(ir_stems),
            "paired_images": len(rgb_stems & ir_stems),
            "rgb_without_ir": len(rgb_stems - ir_stems),
            "ir_without_rgb": len(ir_stems - rgb_stems),
        }
    counts["total_pairs"] = sum(item["paired_images"] for item in counts.values())
    return counts


def folder_structure_summary(dataset_dir: Path) -> dict:
    summary = {}
    for split in ("train", "val", "test"):
        split_dir = dataset_dir / split
        if not split_dir.exists():
            continue
        summary[split] = {
            "rgb_images": str(split_dir / f"{split}img"),
            "infrared_images": str(split_dir / f"{split}imgr"),
            "rgb_annotations": str(split_dir / f"{split}label"),
            "infrared_annotations": str(split_dir / f"{split}labelr"),
        }
    return summary


def recommended_benchmark_strategy(precision_measurable: bool) -> list[str]:
    strategy = [
        "Use RGB and infrared labels as separate recall benchmarks.",
        "Run local evaluation first; reserve API review for 100-250 selected images.",
        "Keep RGB and infrared results separate because visible-light and thermal-like imagery fail differently.",
    ]
    if precision_measurable:
        strategy.append("Use negative images in this dataset to measure capture precision directly.")
    else:
        strategy.append("This dataset is all-positive for vehicle targets; add hard negatives to measure precision properly.")
    return strategy


def label_rows_for_modality(*, stats: dict, modality: str) -> list[dict]:
    return [
        {
            "image_path": row["image_path"],
            "expected_match": row["expected_match"],
            "label": row["label"],
            "modality": row["modality"],
            "source_dataset": row["source_dataset"],
        }
        for row in stats["_label_rows"][modality]
    ]


def write_modality_labels_csv(*, rows: list[dict], output_csv: Path) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "expected_match", "label", "modality", "source_dataset"])
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def public_stats(stats: dict) -> dict:
    return {key: value for key, value in stats.items() if key != "_label_rows"}


def render_analysis_doc(stats: dict) -> str:
    class_rows = "\n".join(f"| {name} | {count:,} |" for name, count in stats["class_distribution"].items())
    split_rows = []
    for split, values in stats["splits"].items():
        rgb = values.get("rgb", {})
        ir = values.get("infrared", {})
        pairs = stats["rgb_ir_pair_counts"].get(split, {})
        split_rows.append(
            f"| {split} | {rgb.get('images', 0):,} | {ir.get('images', 0):,} | {pairs.get('paired_images', 0):,} | "
            f"{rgb.get('annotation_files', 0):,} | {ir.get('annotation_files', 0):,} |"
        )
    strategy = "\n".join(f"- {item}" for item in stats["recommended_benchmark_strategy"])
    precision_sentence = (
        "Precision can be measured directly because the dataset contains negative images."
        if stats["precision_can_be_measured_directly"]
        else "Precision cannot be measured directly from this dataset alone because every image contains at least one vehicle target."
    )
    precision_detail = (
        "Because the dataset includes negative image cases, RGB and infrared runs can report both capture recall and capture precision directly."
        if stats["precision_can_be_measured_directly"]
        else "This means the current DroneVehicle labels are best used as a recall-focused vehicle benchmark. To measure precision, Aegis needs additional hard-negative imagery such as roads without vehicles, rooftops, shadows, equipment, containers, and thermal clutter."
    )
    return f"""# DroneVehicle Benchmark Analysis

Dataset:

```text
{stats['dataset_dir']}
```

## Structure

The dataset has `train`, `val`, and `test` splits. Each split contains:

- RGB images: `<split>/<split>img`
- Infrared images: `<split>/<split>imgr`
- RGB annotations: `<split>/<split>label`
- Infrared annotations: `<split>/<split>labelr`

Annotations are Pascal/VOC-style XML files. Vehicle objects use `<object><name>...</name>` and an oriented polygon with four points. Aegis ignores the polygon geometry for benchmark label generation and only uses the object class names.

## Counts

| Split | RGB images | IR images | RGB/IR pairs | RGB annotation files | IR annotation files |
|---|---:|---:|---:|---:|---:|
{chr(10).join(split_rows)}

| Metric | Value |
|---|---:|
| Total RGB images | {stats['total_rgb_images']:,} |
| Total IR images | {stats['total_ir_images']:,} |
| RGB/IR pairs | {stats['rgb_ir_pair_counts'].get('total_pairs', 0):,} |
| Total annotations | {stats['total_annotations']:,} |
| Images with annotations | {stats['images_with_annotations']:,} |
| Images without annotations | {stats['images_without_annotations']:,} |
| Positive images | {stats['positive_images']:,} |
| Negative images | {stats['negative_images']:,} |

## Class Distribution

| Class | Annotations |
|---|---:|
{class_rows}

## Precision And Recall

{precision_sentence}

{precision_detail}

## Recommended Strategy

{strategy}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the DroneVehicle RGB/infrared benchmark dataset.")
    parser.add_argument("dataset_dir", help="DroneVehicle dataset folder")
    parser.add_argument("--stats-json", default=DEFAULT_STATS_JSON)
    parser.add_argument("--analysis-doc", default=DEFAULT_ANALYSIS_DOC)
    args = parser.parse_args()
    stats = analyze_dronevehicle_benchmark(
        dataset_dir=args.dataset_dir,
        stats_json=args.stats_json,
        analysis_doc=args.analysis_doc,
    )
    print(f"DroneVehicle stats saved: {args.stats_json}")
    print(f"DroneVehicle analysis saved: {args.analysis_doc}")
    print(json.dumps({key: stats[key] for key in ("total_rgb_images", "total_ir_images", "total_annotations", "positive_images", "negative_images", "precision_can_be_measured_directly")}, indent=2))


if __name__ == "__main__":
    main()
