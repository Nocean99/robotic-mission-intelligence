from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.candidate_ranking import rank_candidate
from autonomy.types import SemanticDecision, SemanticVisionResult, TargetDetection


def test_rank_candidate_returns_review_priority_components() -> None:
    ranking = rank_candidate(
        detection=TargetDetection(True, confidence=0.81, area_ratio=0.02),
        semantic=SemanticVisionResult(
            score=0.67,
            decision=SemanticDecision.POSSIBLE_MATCH,
            explanation="partly visible target",
            model_name="test",
        ),
        full_frame_result=None,
        final_score=0.67,
        final_decision=SemanticDecision.POSSIBLE_MATCH,
    )
    assert ranking.proposal_score >= 0.7
    assert ranking.semantic_score == 0.67
    assert ranking.uncertainty_score > 0
    assert ranking.mission_relevance_score >= 0.7
    assert ranking.review_priority >= 0.6
    assert "possible mission match" in ranking.reasons


def test_rank_candidate_preserves_scorer_errors_for_review() -> None:
    ranking = rank_candidate(
        detection=TargetDetection(False),
        semantic=SemanticVisionResult(
            score=0.2,
            decision=SemanticDecision.NEEDS_REVIEW,
            explanation="scorer failed",
            model_name="test",
        ),
        full_frame_result=None,
        final_score=0.2,
        final_decision=SemanticDecision.NEEDS_REVIEW,
        semantic_error="TimeoutError",
    )
    assert ranking.uncertainty_score >= 0.8
    assert ranking.review_priority >= 0.28
    assert "semantic scorer error preserved for review" in ranking.reasons


if __name__ == "__main__":
    tests = [
        test_rank_candidate_returns_review_priority_components,
        test_rank_candidate_preserves_scorer_errors_for_review,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
