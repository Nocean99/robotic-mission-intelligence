from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from pathlib import Path


def create_balanced_sample(
    *,
    dataset_dir: str | Path,
    labels_csv: str | Path,
    output_dir: str | Path = "logs/benchmark_samples/sard_api_sample_100",
    max_images: int = 100,
    seed: int = 7,
) -> Path:
    dataset_path = Path(dataset_dir)
    labels_path = Path(labels_csv)
    output_path = Path(output_dir)
    image_output = output_path / "images"
    image_output.mkdir(parents=True, exist_ok=True)
    rows = read_label_rows(labels_path)
    positives = [row for row in rows if row["expected_match"].strip().lower() == "true"]
    negatives = [row for row in rows if row["expected_match"].strip().lower() == "false"]
    rng = random.Random(seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)

    positive_target = min(len(positives), max_images // 2)
    negative_target = min(len(negatives), max_images - positive_target)
    selected = positives[:positive_target] + negatives[:negative_target]
    if len(selected) < max_images:
        remaining = positives[positive_target:] + negatives[negative_target:]
        rng.shuffle(remaining)
        selected.extend(remaining[: max_images - len(selected)])
    selected = selected[:max_images]
    rng.shuffle(selected)

    output_rows = []
    used_names: set[str] = set()
    for index, row in enumerate(selected, start=1):
        source = dataset_path / row["image_path"]
        if not source.exists():
            continue
        name = unique_name(f"{index:04d}_{source.name}", used_names)
        target = image_output / name
        link_or_copy(source, target)
        output_rows.append(
            {
                "image_path": f"images/{name}",
                "expected_match": row["expected_match"],
                "label": row["label"],
            }
        )

    output_labels = output_path / "labels.csv"
    with output_labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "expected_match", "label"])
        writer.writeheader()
        writer.writerows(output_rows)
    return output_labels


def create_api_review_sample(
    *,
    local_report: str | Path,
    dataset_dir: str | Path,
    labels_csv: str | Path,
    output_dir: str | Path = "logs/benchmark_samples/sard_api_review_sample_200",
    max_images: int = 200,
    seed: int = 11,
) -> Path:
    report_path = Path(local_report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    vision_report = report.get("vision_report") or report
    results = [item for item in vision_report.get("results", []) if "error" not in item]
    rng = random.Random(seed)
    selected: dict[str, dict] = {}

    quota = max(1, max_images // 5)
    add_results(
        selected,
        sorted(results, key=lambda item: float(item.get("review_priority") or 0.0), reverse=True),
        quota,
        "top_review_priority",
    )
    add_results(
        selected,
        sorted(results, key=lambda item: float(item.get("uncertainty_score") or 0.0), reverse=True),
        quota,
        "high_uncertainty",
    )
    false_positive_candidates = [
        item
        for item in results
        if item.get("label", {}).get("expected_match") is False and is_captured_for_review_like(item)
    ]
    add_results(selected, false_positive_candidates, quota, "local_false_positive")
    miss_candidates = [
        item
        for item in results
        if str(item.get("final_decision")) == "REJECT"
        or (item.get("label", {}).get("expected_match") is True and not is_captured_for_review_like(item))
    ]
    add_results(selected, miss_candidates, quota, "local_miss_or_reject")

    remaining_slots = max_images - len(selected)
    if remaining_slots > 0:
        balanced_rows = balanced_label_rows(labels_csv=Path(labels_csv), max_images=remaining_slots, rng=rng)
        for row in balanced_rows:
            key = row["image_path"]
            selected.setdefault(
                key,
                {
                    "image_path": str(Path(dataset_dir) / row["image_path"]),
                    "label": {
                        "expected_match": row["expected_match"].strip().lower() == "true",
                        "label": row["label"],
                    },
                    "selection_reasons": ["balanced_benchmark_sample"],
                },
            )

    return write_selected_sample(
        selected_items=list(selected.values())[:max_images],
        output_dir=Path(output_dir),
    )


def add_results(selected: dict[str, dict], candidates: list[dict], limit: int, reason: str) -> None:
    for item in candidates:
        if len([entry for entry in selected.values() if reason in entry.get("selection_reasons", [])]) >= limit:
            return
        key = str(item.get("image_path") or item.get("candidate_id") or "")
        if not key:
            continue
        entry = selected.setdefault(key, {**item, "selection_reasons": []})
        if reason not in entry["selection_reasons"]:
            entry["selection_reasons"].append(reason)


def balanced_label_rows(*, labels_csv: Path, max_images: int, rng: random.Random) -> list[dict]:
    rows = read_label_rows(labels_csv)
    positives = [row for row in rows if row["expected_match"].strip().lower() == "true"]
    negatives = [row for row in rows if row["expected_match"].strip().lower() == "false"]
    rng.shuffle(positives)
    rng.shuffle(negatives)
    positive_count = min(len(positives), max_images // 2)
    negative_count = min(len(negatives), max_images - positive_count)
    selected = positives[:positive_count] + negatives[:negative_count]
    if len(selected) < max_images:
        remaining = positives[positive_count:] + negatives[negative_count:]
        rng.shuffle(remaining)
        selected.extend(remaining[: max_images - len(selected)])
    rng.shuffle(selected)
    return selected[:max_images]


def write_selected_sample(*, selected_items: list[dict], output_dir: Path) -> Path:
    image_output = output_dir / "images"
    image_output.mkdir(parents=True, exist_ok=True)
    output_rows = []
    manifest = []
    used_names: set[str] = set()
    for index, item in enumerate(selected_items, start=1):
        source = Path(str(item.get("image_path") or ""))
        if not source.exists():
            continue
        name = unique_name(f"{index:04d}_{source.name}", used_names)
        target = image_output / name
        link_or_copy(source, target)
        label = item.get("label") or {}
        expected = label.get("expected_match", False)
        if isinstance(expected, str):
            expected = expected.strip().lower() == "true"
        output_rows.append(
            {
                "image_path": f"images/{name}",
                "expected_match": "true" if expected else "false",
                "label": "positive" if expected else "negative",
            }
        )
        manifest.append(
            {
                "image_path": f"images/{name}",
                "source_image_path": str(source),
                "expected_match": bool(expected),
                "selection_reasons": item.get("selection_reasons", []),
                "review_priority": item.get("review_priority"),
                "uncertainty_score": item.get("uncertainty_score"),
                "final_decision": item.get("final_decision"),
            }
        )

    output_labels = output_dir / "labels.csv"
    with output_labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "expected_match", "label"])
        writer.writeheader()
        writer.writerows(output_rows)
    (output_dir / "selection_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output_labels


def is_captured_for_review_like(item: dict) -> bool:
    decision = str(item.get("final_decision") or "")
    if decision in {"LIKELY_MATCH", "POSSIBLE_MATCH"}:
        return True
    if decision == "NEEDS_REVIEW":
        return float(item.get("final_score") or 0.0) >= 0.2
    return False


def read_label_rows(labels_csv: Path) -> list[dict]:
    with labels_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"image_path", "expected_match", "label"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Labels CSV missing columns: {', '.join(sorted(missing))}")
        return [row for row in reader]


def unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while True:
        candidate = f"{stem}_{index}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def link_or_copy(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        target.unlink()
    source = source.resolve()
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a small balanced image sample from an Aegis labels CSV.")
    parser.add_argument("dataset_dir", help="Dataset root that image_path values are relative to")
    parser.add_argument("--labels-csv", default="datasets/benchmarks/people/sard_labels.csv")
    parser.add_argument("--output-dir", default="logs/benchmark_samples/sard_api_sample_100")
    parser.add_argument("--max-images", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--from-local-report", default=None, help="Create an API-review sample from a previous local mission report.")
    args = parser.parse_args()
    if args.from_local_report:
        labels_path = create_api_review_sample(
            local_report=args.from_local_report,
            dataset_dir=args.dataset_dir,
            labels_csv=args.labels_csv,
            output_dir=args.output_dir,
            max_images=args.max_images,
            seed=args.seed,
        )
    else:
        labels_path = create_balanced_sample(
            dataset_dir=args.dataset_dir,
            labels_csv=args.labels_csv,
            output_dir=args.output_dir,
            max_images=args.max_images,
            seed=args.seed,
        )
    print(f"Sample labels CSV saved: {labels_path}")
    print(f"Sample images folder: {labels_path.parent / 'images'}")


if __name__ == "__main__":
    main()
