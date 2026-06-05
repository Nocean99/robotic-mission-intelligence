from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from autonomy.mission_objective import parse_mission_request
from autonomy.mission_vision_plan import _extract_contexts
from autonomy.types import ContextualSearchPlan, MissionObjective, SearchPriority


CATEGORY_LOCATION_RULES = {
    "person": {
        "likely": [
            ("trails and paths", "Missing or injured people are often found near routes of travel.", ["trail", "path", "road edge"]),
            ("shelter and clearings", "People may seek visible or protected places while waiting for help.", ["clearing", "structure", "open area"]),
            ("hazard boundaries", "Searches should prioritize edges where terrain changes or movement gets constrained.", ["shoreline", "treeline", "slope"]),
        ],
        "deprioritized": [
            ("featureless open areas", "Large empty areas are lower priority unless the request or evidence points there.", ["uniform field", "open water"]),
        ],
    },
    "vehicle": {
        "likely": [
            ("roads and road edges", "Vehicles are most likely near travel corridors or places reachable by vehicle.", ["road", "driveway", "parking"]),
            ("turnouts and clearings", "Stopped or stranded vehicles may be near pull-offs or open ground.", ["turnout", "lot", "clearing"]),
            ("crash or debris zones", "Damaged or overturned vehicles may appear near disturbed terrain.", ["debris", "skid mark", "wreckage"]),
        ],
        "deprioritized": [
            ("dense vegetation", "Dense vegetation is lower priority unless the mission suggests a crash or off-road path.", ["heavy tree cover"]),
        ],
    },
    "boat": {
        "likely": [
            ("water surfaces", "Boats and sinking vessels are most likely on navigable water.", ["water", "wake", "hull"]),
            ("shoreline and docks", "Boats may drift, ground, or be moored near edges and dock structures.", ["shoreline", "dock", "marina"]),
            ("channels and harbors", "Traffic lanes and protected water are high-value search areas.", ["channel", "harbor", "marina"]),
        ],
        "deprioritized": [
            ("inland dry terrain", "Dry inland terrain is lower priority for active boat searches unless flood or debris context is present.", ["field", "road"]),
        ],
    },
    "aircraft": {
        "likely": [
            ("open impact zones", "Aircraft incidents may leave visible debris in clearings or fields.", ["field", "clearing", "wreckage"]),
            ("tree breaks and debris trails", "Crashes can create linear disturbance through vegetation.", ["treeline", "debris", "broken canopy"]),
        ],
        "deprioritized": [
            ("undisturbed built-up areas", "Built-up areas are lower priority unless witness reports or telemetry point there.", ["building cluster"]),
        ],
    },
    "debris": {
        "likely": [
            ("disturbed terrain", "Debris is often near impact, flood, collapse, or damage patterns.", ["wreckage", "scattered objects"]),
            ("downwind or downstream paths", "Debris can move with wind, current, slope, or traffic flow.", ["current line", "drift path"]),
        ],
        "deprioritized": [
            ("orderly repeated objects", "Regular infrastructure patterns are lower priority unless they match the mission.", ["parked cars", "roof rows"]),
        ],
    },
    "signal": {
        "likely": [
            ("high-visibility areas", "Signals are often placed where searchers can see them.", ["clearing", "shoreline", "roof"]),
            ("near people or shelter", "Signals often sit close to the person or group needing help.", ["camp", "structure", "trail"]),
        ],
        "deprioritized": [
            ("visually cluttered backgrounds", "Clutter makes small signals harder to confirm and should be secondary.", ["dense brush"]),
        ],
    },
}


CONTEXT_LOCATION_RULES = {
    "water": ("water-associated regions", "The mission mentions water context, so water surfaces and their edges should be searched early.", ["water", "shoreline", "dock"]),
    "shoreline": ("shoreline boundary", "Shorelines are high-value boundaries where targets, people, and debris can collect.", ["beach", "riverbank", "coast"]),
    "forest": ("trails, clearings, and treelines", "Forested searches should prioritize navigable paths, breaks, and visible openings.", ["trail", "clearing", "treeline"]),
    "road": ("roads, shoulders, and access points", "Road context points to vehicle access routes and nearby stopping points.", ["road", "shoulder", "driveway"]),
    "field": ("open fields and field edges", "Open fields are quick to clear and field edges often collect clues.", ["field", "fence line", "edge"]),
    "debris": ("damage and debris fields", "Damage language suggests searching disturbed areas and spread patterns first.", ["wreckage", "scattered debris"]),
}


def create_contextual_search_plan(request_or_objective: str | MissionObjective) -> ContextualSearchPlan:
    objective = (
        parse_mission_request(request_or_objective)
        if isinstance(request_or_objective, str)
        else request_or_objective
    )
    contexts = _extract_contexts(objective.raw_request)
    likely = []
    deprioritized = []
    for category in objective.extracted_categories:
        rule = CATEGORY_LOCATION_RULES.get(category)
        if not rule:
            continue
        likely.extend(_priority_items(rule["likely"], base_priority=90))
        deprioritized.extend(_priority_items(rule["deprioritized"], base_priority=30))
    for context in contexts:
        rule = CONTEXT_LOCATION_RULES.get(context)
        if rule:
            likely.append(SearchPriority(name=rule[0], priority=95, rationale=rule[1], cues=list(rule[2])))
    if not likely:
        likely.append(
            SearchPriority(
                name="mission-described area",
                priority=70,
                rationale="The request does not include enough target or terrain cues, so start with the described search area and collect context evidence early.",
                cues=objective.extracted_keywords[:6],
            )
        )
    likely = _dedupe_priorities(likely)
    deprioritized = _dedupe_priorities(deprioritized)
    return ContextualSearchPlan(
        likely_locations=likely,
        deprioritized_locations=deprioritized,
        routing_guidance=[
            "Search high-priority context zones before running a uniform full-area grid.",
            "Use the first pass to classify terrain and scene context, then tighten the route around likely zones.",
            "Keep a low-rate coverage pass for deprioritized areas when safety, time, and battery allow.",
        ],
        required_context_sources=[
            "mission text",
            "live or recorded imagery",
            "map or operator-defined search boundary when available",
            "future terrain/scene segmentation masks",
        ],
        notes=[
            "This is contextual planning guidance, not yet a geographic mask.",
            "A later route planner should convert likely locations into search polygons or waypoint priorities.",
        ],
    )


def _priority_items(items: list[tuple[str, str, list[str]]], *, base_priority: int) -> list[SearchPriority]:
    priorities = []
    for offset, (name, rationale, cues) in enumerate(items):
        priorities.append(
            SearchPriority(
                name=name,
                priority=max(1, base_priority - offset * 8),
                rationale=rationale,
                cues=list(cues),
            )
        )
    return priorities


def _dedupe_priorities(items: list[SearchPriority]) -> list[SearchPriority]:
    by_name = {}
    for item in items:
        existing = by_name.get(item.name)
        if existing is None or item.priority > existing.priority:
            by_name[item.name] = item
    return sorted(by_name.values(), key=lambda item: (-item.priority, item.name))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create contextual search priorities from a mission request")
    parser.add_argument("request", nargs="+")
    args = parser.parse_args()
    plan = create_contextual_search_plan(" ".join(args.request))
    print(json.dumps(asdict(plan), indent=2, default=str))


if __name__ == "__main__":
    main()
