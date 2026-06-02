from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.mission_command import create_mission_command, mission_command_to_json
from autonomy.types import ConfirmationMode, LinkLossAction, OperatingMode


def test_connected_supervised_uses_live_confirmation() -> None:
    command = create_mission_command(
        "Search the north field for a possible survivor signal",
        operating_mode="connected-supervised",
    )
    assert command.operating_mode == OperatingMode.CONNECTED_SUPERVISED
    assert command.confirmation_mode == ConfirmationMode.LIVE_OPERATOR
    assert command.link_loss_policy.action == LinkLossAction.RETURN_HOME
    assert command.report_requirements.require_human_review
    assert command.objective.search_area_description == "north field"


def test_autonomous_return_report_stores_candidates() -> None:
    command = create_mission_command(
        "Search the shoreline for any object matching the caller description",
        operating_mode="autonomous-return-report",
    )
    assert command.operating_mode == OperatingMode.AUTONOMOUS_RETURN_REPORT
    assert command.confirmation_mode == ConfirmationMode.STORE_FOR_REVIEW
    assert command.link_loss_policy.action == LinkLossAction.CONTINUE_THEN_RETURN
    assert command.link_loss_policy.require_return_with_report
    assert command.report_requirements.save_candidate_images


def test_mission_command_preserves_raw_language() -> None:
    request = "Find signs of a missing hiker near the ridge"
    command = create_mission_command(request, operating_mode="connected")
    payload = mission_command_to_json(command)
    assert request in payload
    assert "hiker" in command.objective.extracted_keywords


if __name__ == "__main__":
    tests = [
        test_connected_supervised_uses_live_confirmation,
        test_autonomous_return_report_stores_candidates,
        test_mission_command_preserves_raw_language,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
