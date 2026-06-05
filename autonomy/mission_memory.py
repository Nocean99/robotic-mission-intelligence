from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def build_mission_memory(root: str | Path = ".") -> dict:
    root_path = Path(root)
    report_paths = sorted((root_path / "logs").glob("**/vision_report.json"), reverse=True)
    mission_counts: Counter[str] = Counter()
    review_counts: Counter[str] = Counter()
    false_positive_terms: Counter[str] = Counter()
    false_negative_terms: Counter[str] = Counter()
    category_metrics: dict[str, list[dict]] = defaultdict(list)
    recent_reports = []

    for report_path in report_paths:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        objective = report.get("objective") or {}
        categories = objective.get("extracted_categories") or ["uncategorized"]
        mission_type = objective.get("mission_type") or "unknown"
        mission_counts[mission_type] += 1

        evaluation = report.get("evaluation") or {}
        analyst_capture = evaluation.get("analyst_capture") or {}
        for category in categories:
            category_metrics[str(category)].append(
                {
                    "precision": evaluation.get("precision"),
                    "recall": evaluation.get("recall"),
                    "f1": evaluation.get("f1"),
                    "capture_recall": analyst_capture.get("recall"),
                    "capture_f1": analyst_capture.get("f1"),
                }
            )

        for item in evaluation.get("false_positives") or []:
            false_positive_terms.update(_name_terms(item))
        for item in evaluation.get("false_negatives") or []:
            false_negative_terms.update(_name_terms(item))

        review_path = report_path.with_name("candidate_reviews.json")
        if review_path.exists():
            try:
                reviews = json.loads(review_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                reviews = {}
            for review in reviews.values():
                review_counts[str(review.get("status") or "unknown")] += 1

        if len(recent_reports) < 10:
            summary = report.get("summary") or {}
            recent_reports.append(
                {
                    "path": _display_path(report_path, root_path),
                    "timestamp": report.get("timestamp"),
                    "mission_request": report.get("mission_request"),
                    "processed": summary.get("processed"),
                    "shortlist_count": summary.get("shortlist_count"),
                    "precision": evaluation.get("precision"),
                    "recall": evaluation.get("recall"),
                    "capture_recall": analyst_capture.get("recall"),
                }
            )

    return {
        "report_count": len(report_paths),
        "mission_types": dict(mission_counts.most_common()),
        "review_statuses": dict(review_counts.most_common()),
        "category_metrics": summarize_category_metrics(category_metrics),
        "common_false_positive_terms": dict(false_positive_terms.most_common(12)),
        "common_false_negative_terms": dict(false_negative_terms.most_common(12)),
        "mission_memory_v1": mission_memory_snapshot_from_patterns(
            false_positive_terms=false_positive_terms,
            false_negative_terms=false_negative_terms,
            weak_categories=_weak_categories(category_metrics),
        ),
        "recent_reports": recent_reports,
        "recommendations": memory_recommendations(false_positive_terms, false_negative_terms, category_metrics),
    }


def mission_memory_snapshot(report: dict, reviews: dict | None = None) -> dict:
    evaluation = report.get("evaluation") or {}
    objective = report.get("objective") or {}
    categories = [str(item) for item in objective.get("extracted_categories") or []]
    false_positive_terms: Counter[str] = Counter()
    false_negative_terms: Counter[str] = Counter()
    review_reasons: Counter[str] = Counter()
    for item in evaluation.get("false_positives") or []:
        false_positive_terms.update(_name_terms(item))
    for item in evaluation.get("false_negatives") or []:
        false_negative_terms.update(_name_terms(item))
    for review in (reviews or {}).values():
        reason = str(review.get("reason") or "").strip().lower()
        if reason:
            review_reasons[reason] += 1

    analyst_capture = evaluation.get("analyst_capture") or {}
    weak_categories = []
    if categories and (analyst_capture.get("recall") is not None) and float(analyst_capture.get("recall") or 0.0) < 0.9:
        weak_categories = categories

    snapshot = mission_memory_snapshot_from_patterns(
        false_positive_terms=false_positive_terms + review_reasons,
        false_negative_terms=false_negative_terms,
        weak_categories=weak_categories,
    )
    snapshot["analyst_decision_patterns"] = dict(review_reasons.most_common(8))
    return snapshot


def mission_memory_snapshot_from_patterns(
    *,
    false_positive_terms: Counter[str],
    false_negative_terms: Counter[str],
    weak_categories: list[str],
) -> dict:
    false_positive_patterns = [term for term, _ in false_positive_terms.most_common(8)]
    miss_patterns = [term for term, _ in false_negative_terms.most_common(8)]
    recommended_data = recommended_data_from_patterns(false_positive_patterns, miss_patterns, weak_categories)
    return {
        "false_positive_patterns": false_positive_patterns,
        "miss_patterns": miss_patterns,
        "weak_categories": sorted(set(weak_categories)),
        "recommended_data": recommended_data,
    }


def summarize_category_metrics(category_metrics: dict[str, list[dict]]) -> dict:
    return {
        category: {
            "runs": len(metrics),
            "avg_precision": _avg(item.get("precision") for item in metrics),
            "avg_recall": _avg(item.get("recall") for item in metrics),
            "avg_f1": _avg(item.get("f1") for item in metrics),
            "avg_capture_recall": _avg(item.get("capture_recall") for item in metrics),
            "avg_capture_f1": _avg(item.get("capture_f1") for item in metrics),
        }
        for category, metrics in sorted(category_metrics.items())
    }


def memory_recommendations(
    false_positive_terms: Counter[str],
    false_negative_terms: Counter[str],
    category_metrics: dict[str, list[dict]],
) -> list[str]:
    recommendations = []
    if false_positive_terms:
        terms = ", ".join(term for term, _ in false_positive_terms.most_common(3))
        recommendations.append(f"Review ranking should down-rank recurring false-positive cues: {terms}.")
    if false_negative_terms:
        terms = ", ".join(term for term, _ in false_negative_terms.most_common(3))
        recommendations.append(f"Keep full-frame fallback active for recurring misses involving: {terms}.")
    weak_categories = _weak_categories(category_metrics)
    if weak_categories:
        recommendations.append(f"Add more labeled examples for lower-capture categories: {', '.join(sorted(weak_categories))}.")
    if not recommendations:
        recommendations.append("Current reports show no obvious repeated failure pattern yet; add broader labeled missions next.")
    return recommendations


def recommended_data_from_patterns(
    false_positive_patterns: list[str],
    miss_patterns: list[str],
    weak_categories: list[str],
) -> list[str]:
    recommendations = []
    if weak_categories:
        recommendations.extend(f"more labeled {category} examples with hard negatives" for category in sorted(set(weak_categories)))
    if miss_patterns:
        recommendations.append(f"positive examples for recurring misses: {', '.join(miss_patterns[:3])}")
    if false_positive_patterns:
        recommendations.append(f"hard negatives for recurring false positives: {', '.join(false_positive_patterns[:3])}")
    if not recommendations:
        recommendations.append("broader labeled missions with positives, near misses, and hard negatives")
    return recommendations[:6]


def _weak_categories(category_metrics: dict[str, list[dict]]) -> list[str]:
    return [
        category
        for category, metrics in category_metrics.items()
        if (_avg(item.get("capture_recall") for item in metrics) or 0.0) < 0.9
    ]


def _name_terms(item) -> list[str]:
    if isinstance(item, dict):
        path = item.get("image_path") or ""
    else:
        path = str(item)
    name = Path(path).stem.lower()
    ignored = {"and", "with", "the", "for", "in", "on", "a", "an", "jpg", "png", "jpeg"}
    return [part for part in name.replace("-", " ").replace("_", " ").split() if len(part) > 2 and part not in ignored]


def _avg(values) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
