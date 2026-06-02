from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.mission_vision_plan import create_mission_vision_plan


def test_vision_plan_extracts_color_category_and_context() -> None:
    plan = create_mission_vision_plan("Search the shoreline for a small blue boat with a white top")
    assert "blue" in plan.important_colors
    assert "white" in plan.important_colors
    assert "boat" in plan.possible_categories
    assert "shoreline" in plan.context_hints
    assert "water" in plan.context_hints
    assert "color" in plan.proposal_modes
    assert "full_frame_scan" in plan.proposal_modes
    assert "small blue boat" in plan.semantic_prompt


def test_vision_plan_uses_broad_color_when_no_color_is_named() -> None:
    plan = create_mission_vision_plan("Search the woods for a missing hiker")
    assert plan.important_colors == []
    assert "person" in plan.possible_categories
    assert "broad_color" in plan.proposal_modes
    assert "forest" in plan.context_hints


if __name__ == "__main__":
    tests = [
        test_vision_plan_extracts_color_category_and_context,
        test_vision_plan_uses_broad_color_when_no_color_is_named,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
