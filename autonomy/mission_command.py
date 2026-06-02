from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from autonomy.mission_objective import objective_to_prompt, parse_mission_request
from autonomy.types import (
    ConfirmationMode,
    LinkLossAction,
    LinkLossPolicy,
    MissionCommand,
    OperatingMode,
    ReportRequirements,
)


MODE_ALIASES = {
    "connected": OperatingMode.CONNECTED_SUPERVISED,
    "connected-supervised": OperatingMode.CONNECTED_SUPERVISED,
    "supervised": OperatingMode.CONNECTED_SUPERVISED,
    "autonomous": OperatingMode.AUTONOMOUS_RETURN_REPORT,
    "autonomous-return-report": OperatingMode.AUTONOMOUS_RETURN_REPORT,
    "offline": OperatingMode.AUTONOMOUS_RETURN_REPORT,
}


def create_mission_command(
    request: str,
    *,
    operating_mode: OperatingMode | str = OperatingMode.CONNECTED_SUPERVISED,
) -> MissionCommand:
    mode = normalize_operating_mode(operating_mode)
    objective = parse_mission_request(request)
    if mode == OperatingMode.CONNECTED_SUPERVISED:
        confirmation_mode = ConfirmationMode.LIVE_OPERATOR
        link_loss_policy = LinkLossPolicy(
            action=LinkLossAction.RETURN_HOME,
            max_disconnected_s=10.0,
            notes=[
                "Live operator mode expects a dashboard connection.",
                "If the link is lost, the safe default is return home.",
            ],
        )
        report_requirements = ReportRequirements(require_human_review=True)
        notes = [
            "Use this mode when first responders can watch candidates live.",
            "The autonomy layer proposes possible matches; humans confirm or reject them.",
        ]
    else:
        confirmation_mode = ConfirmationMode.STORE_FOR_REVIEW
        link_loss_policy = LinkLossPolicy(
            action=LinkLossAction.CONTINUE_THEN_RETURN,
            max_disconnected_s=0.0,
            notes=[
                "Disconnected mode must not depend on a live dashboard.",
                "The mission should search within safety limits, return home, and preserve evidence for review.",
            ],
        )
        report_requirements = ReportRequirements(require_human_review=True)
        notes = [
            "Use this mode when the drone may be temporarily disconnected.",
            "Candidates are stored for later responder review instead of requiring live confirmation.",
        ]
    return MissionCommand(
        raw_request=request.strip(),
        operating_mode=mode,
        objective=objective,
        confirmation_mode=confirmation_mode,
        link_loss_policy=link_loss_policy,
        report_requirements=report_requirements,
        autonomy_notes=notes,
    )


def normalize_operating_mode(value: OperatingMode | str) -> OperatingMode:
    if isinstance(value, OperatingMode):
        return value
    normalized = value.strip().lower().replace("_", "-")
    if normalized in MODE_ALIASES:
        return MODE_ALIASES[normalized]
    try:
        return OperatingMode[value.strip().upper()]
    except KeyError as exc:
        valid = ", ".join(sorted(MODE_ALIASES))
        raise ValueError(f"Unknown operating mode {value!r}. Use one of: {valid}") from exc


def mission_command_to_json(command: MissionCommand) -> str:
    return json.dumps(asdict(command), indent=2, default=str)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan a natural-language SAR mission command")
    parser.add_argument("request", nargs="+")
    parser.add_argument(
        "--mode",
        default="connected-supervised",
        help="connected-supervised or autonomous-return-report",
    )
    args = parser.parse_args()
    command = create_mission_command(" ".join(args.request), operating_mode=args.mode)
    print(mission_command_to_json(command))
    print()
    print(objective_to_prompt(command.objective))


if __name__ == "__main__":
    main()
