from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.color_proposal_detector import MissionColorProposalDetector
from autonomy.mission_vision_plan import create_mission_vision_plan


def test_mission_color_detector_finds_blue_when_prompt_mentions_blue() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (120, 80), (210, 150), (255, 0, 0), -1)
    plan = create_mission_vision_plan("Search for a blue boat")
    detection = MissionColorProposalDetector(plan).detect(image)
    assert detection.detected
    assert detection.bbox is not None


def test_mission_color_detector_ignores_blue_when_prompt_mentions_orange() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (120, 80), (210, 150), (255, 0, 0), -1)
    plan = create_mission_vision_plan("Search for an orange life jacket")
    detection = MissionColorProposalDetector(plan).detect(image)
    assert not detection.detected


def test_mission_color_detector_does_not_guess_color_when_none_named() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (120, 80), (210, 150), (255, 255, 255), -1)
    plan = create_mission_vision_plan("Search for a person")
    detection = MissionColorProposalDetector(plan).detect(image)
    assert not detection.detected


if __name__ == "__main__":
    tests = [
        test_mission_color_detector_finds_blue_when_prompt_mentions_blue,
        test_mission_color_detector_ignores_blue_when_prompt_mentions_orange,
        test_mission_color_detector_does_not_guess_color_when_none_named,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
