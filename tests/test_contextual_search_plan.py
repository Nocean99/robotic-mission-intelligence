from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.contextual_search_plan import create_contextual_search_plan


def test_boat_mission_prioritizes_water_context() -> None:
    plan = create_contextual_search_plan("Search the harbor for a sinking wooden ship")
    names = [item.name for item in plan.likely_locations]
    assert "water surfaces" in names
    assert "shoreline and docks" in names
    assert "water-associated regions" in names
    assert plan.routing_guidance
    assert plan.required_context_sources


def test_vehicle_mission_prioritizes_access_routes() -> None:
    plan = create_contextual_search_plan("Search near the treeline for an overturned red vehicle")
    names = [item.name for item in plan.likely_locations]
    assert "roads and road edges" in names
    assert "turnouts and clearings" in names
    assert "dense vegetation" in [item.name for item in plan.deprioritized_locations]


def test_underspecified_mission_keeps_context_collection_step() -> None:
    plan = create_contextual_search_plan("Search the area for anything unusual")
    assert plan.likely_locations[0].name == "mission-described area"
    assert "terrain/scene segmentation masks" in " ".join(plan.required_context_sources)


if __name__ == "__main__":
    tests = [
        test_boat_mission_prioritizes_water_context,
        test_vehicle_mission_prioritizes_access_routes,
        test_underspecified_mission_keeps_context_collection_step,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
