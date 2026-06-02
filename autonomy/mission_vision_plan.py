from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from autonomy.mission_objective import parse_mission_request
from autonomy.types import MissionObjective, MissionVisionPlan


CONTEXT_HINTS = {
    "shoreline": {"shoreline", "beach", "coast", "coastal", "riverbank", "lake", "water"},
    "water": {"water", "ocean", "lake", "river", "marina", "harbor", "dock", "shoreline"},
    "forest": {"forest", "woods", "tree", "treeline", "trail", "brush"},
    "road": {"road", "highway", "street", "parking", "lot", "driveway"},
    "field": {"field", "grass", "meadow", "farm"},
    "debris": {"debris", "wreckage", "crash", "damaged", "collapsed"},
}


def create_mission_vision_plan(request_or_objective: str | MissionObjective) -> MissionVisionPlan:
    objective = (
        parse_mission_request(request_or_objective)
        if isinstance(request_or_objective, str)
        else request_or_objective
    )
    colors = list(objective.extracted_colors)
    categories = list(objective.extracted_categories)
    contexts = _extract_contexts(objective.raw_request)
    proposal_modes = ["color"] if colors else ["broad_color"]
    if categories:
        proposal_modes.extend(f"{category}_proposal" for category in categories)
    proposal_modes.append("full_frame_scan")
    semantic_prompt = (
        "Does this drone image or crop contain the target described by the mission? "
        f"Mission: {objective.raw_request}. "
        "Return a match score, short explanation, and whether a human should review it."
    )
    notes = [
        "Generated locally from mission text.",
        "Use the plan to configure cheap proposal detectors before semantic scoring.",
        "Full-frame scan is included so obscure targets are not fully dependent on color proposals.",
    ]
    return MissionVisionPlan(
        target_description=objective.target_description,
        important_colors=colors,
        possible_categories=categories,
        context_hints=contexts,
        proposal_modes=sorted(set(proposal_modes)),
        semantic_prompt=semantic_prompt,
        full_frame_scan_interval_s=2.0,
        review_threshold=0.35,
        notes=notes,
    )


def _extract_contexts(text: str) -> list[str]:
    lowered = text.lower()
    contexts = []
    for context, hints in CONTEXT_HINTS.items():
        if any(hint in lowered for hint in hints):
            contexts.append(context)
    return sorted(contexts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a vision search plan from a mission request")
    parser.add_argument("request", nargs="+")
    args = parser.parse_args()
    plan = create_mission_vision_plan(" ".join(args.request))
    print(json.dumps(asdict(plan), indent=2, default=str))


if __name__ == "__main__":
    main()
