from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.candidate_manager import CandidateManager
from autonomy.mission_objective import objective_to_prompt, parse_mission_request
from autonomy.types import CandidateStatus, Position, TargetDetection


def test_parse_free_text_mission_request() -> None:
    objective = parse_mission_request("Search the area for an overturned red vehicle near the treeline")
    assert objective.raw_request
    assert "red" in objective.extracted_colors
    assert "vehicle" in objective.extracted_categories
    assert "treeline" in (objective.search_area_description or "")
    assert objective.confirmation_required


def test_objective_prompt_preserves_raw_description() -> None:
    objective = parse_mission_request("Find anything matching the caller's description along the shoreline")
    prompt = objective_to_prompt(objective)
    assert "caller" in prompt
    assert "shoreline" in prompt


def test_candidate_manager_review_workflow() -> None:
    objective = parse_mission_request("Locate a possible survivor signal")
    with TemporaryDirectory() as tmp:
        manager = CandidateManager(objective, log_dir=tmp)
        candidate = manager.add_detection(
            detection=TargetDetection(True, confidence=0.72, bbox=(1, 2, 3, 4)),
            position=Position(1, 2, -5, 0),
            source="test_detector",
        )
        assert candidate is not None
        assert manager.unreviewed()
        manager.review(candidate.id, CandidateStatus.NEEDS_CLOSER_LOOK, "Responder requested closer look")
        assert manager.get(candidate.id).status == CandidateStatus.NEEDS_CLOSER_LOOK
        path = manager.save()
        assert path.exists()


if __name__ == "__main__":
    tests = [
        test_parse_free_text_mission_request,
        test_objective_prompt_preserves_raw_description,
        test_candidate_manager_review_workflow,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
