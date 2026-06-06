from __future__ import annotations

import argparse
import csv
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def generate_yolo_person_labels_csv(
    *,
    dataset_dir: str | Path,
    output_csv: str | Path = "datasets/benchmarks/people/sard_labels.csv",
    person_class_id: int = 0,
) -> Path:
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        raise ValueError(f"Dataset folder not found: {dataset_path}")
    image_paths = collect_yolo_images(dataset_path)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "expected_match", "label"])
        writer.writeheader()
        for image_path in image_paths:
            has_person = yolo_image_has_class(
                image_path=image_path,
                dataset_dir=dataset_path,
                class_id=person_class_id,
            )
            writer.writerow(
                {
                    "image_path": str(image_path.relative_to(dataset_path)),
                    "expected_match": "true" if has_person else "false",
                    "label": "positive" if has_person else "negative",
                }
            )
    return output_path


def collect_yolo_images(dataset_dir: Path) -> list[Path]:
    images_root = dataset_dir / "images"
    search_root = images_root if images_root.exists() else dataset_dir
    return sorted(
        path
        for path in search_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def yolo_image_has_class(*, image_path: Path, dataset_dir: Path, class_id: int) -> bool:
    label_path = label_path_for_image(image_path=image_path, dataset_dir=dataset_dir)
    if label_path is None or not label_path.exists():
        return False
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        try:
            annotation_class = int(float(parts[0]))
        except ValueError:
            continue
        if annotation_class == class_id:
            return True
    return False


def label_path_for_image(*, image_path: Path, dataset_dir: Path) -> Path | None:
    stem_path = image_path.with_suffix(".txt")
    if stem_path.exists():
        return stem_path
    split_label_path = split_label_path_for_image(image_path=image_path, dataset_dir=dataset_dir)
    if split_label_path is not None:
        return split_label_path
    try:
        relative = image_path.relative_to(dataset_dir / "images")
        return dataset_dir / "labels" / relative.with_suffix(".txt")
    except ValueError:
        pass
    try:
        relative = image_path.relative_to(dataset_dir)
        if relative.parts and relative.parts[0] == "images":
            return dataset_dir / "labels" / Path(*relative.parts[1:]).with_suffix(".txt")
        return dataset_dir / "labels" / relative.with_suffix(".txt")
    except ValueError:
        return None


def split_label_path_for_image(*, image_path: Path, dataset_dir: Path) -> Path | None:
    try:
        relative = image_path.relative_to(dataset_dir)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) >= 3 and parts[1] == "images":
        return dataset_dir / parts[0] / "labels" / Path(*parts[2:]).with_suffix(".txt")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert YOLOv8 person labels into an Aegis benchmark labels CSV.")
    parser.add_argument("dataset_dir", help="YOLO dataset folder containing images/ and labels/ folders")
    parser.add_argument(
        "--output-csv",
        default="datasets/benchmarks/people/sard_labels.csv",
        help="Output Aegis labels CSV path",
    )
    parser.add_argument("--person-class-id", type=int, default=0, help="YOLO class id for person. Defaults to 0.")
    args = parser.parse_args()
    output_path = generate_yolo_person_labels_csv(
        dataset_dir=args.dataset_dir,
        output_csv=args.output_csv,
        person_class_id=args.person_class_id,
    )
    print(f"Aegis labels CSV saved: {output_path}")


if __name__ == "__main__":
    main()
