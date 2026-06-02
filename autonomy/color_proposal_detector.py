from __future__ import annotations

import cv2
import numpy as np

from autonomy.types import MissionVisionPlan, TargetDetection


COLOR_RANGES = {
    "red": [((0, 45, 45), (18, 255, 255)), ((162, 45, 45), (180, 255, 255))],
    "orange": [((8, 40, 45), (30, 255, 255))],
    "yellow": [((22, 35, 45), (45, 255, 255))],
    "green": [((38, 35, 35), (95, 255, 255))],
    "blue": [((85, 35, 35), (135, 255, 255))],
    "purple": [((125, 35, 35), (165, 255, 255))],
    "brown": [((5, 35, 25), (30, 190, 170))],
    "tan": [((15, 20, 80), (40, 155, 230))],
    "black": [((0, 0, 0), (180, 255, 75))],
    "white": [((0, 0, 175), (180, 80, 255))],
    "gray": [((0, 0, 75), (180, 65, 210))],
    "grey": [((0, 0, 75), (180, 65, 210))],
    "silver": [((0, 0, 100), (180, 75, 235))],
}


class MissionColorProposalDetector:
    def __init__(self, plan: MissionVisionPlan, *, min_area_px: int = 75, allow_broad_fallback: bool = False) -> None:
        self.plan = plan
        self.min_area_px = min_area_px
        self.allow_broad_fallback = allow_broad_fallback

    def detect(self, bgr_image: np.ndarray) -> TargetDetection:
        detections = self.detect_all(bgr_image, max_regions=1)
        return detections[0] if detections else TargetDetection(False)

    def detect_all(self, bgr_image: np.ndarray, *, max_regions: int = 5) -> list[TargetDetection]:
        if bgr_image is None or bgr_image.size == 0:
            return []
        mask = self.mask(bgr_image)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        proposals: list[TargetDetection] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area_px:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w <= 0 or h <= 0:
                continue
            image_area = float(bgr_image.shape[0] * bgr_image.shape[1])
            rect_area = float(w * h)
            area_ratio = rect_area / image_area
            rectangularity = area / rect_area
            confidence = min(0.88, 0.22 + min(area / max(self.min_area_px * 8, 1), 1.0) * 0.25 + rectangularity * 0.25 + min(area_ratio / 0.08, 1.0) * 0.18)
            proposals.append(
                TargetDetection(
                    detected=True,
                    confidence=round(confidence, 3),
                    bbox=(x, y, w, h),
                    center_px=(int(x + w / 2), int(y + h / 2)),
                    area_px=area,
                    area_ratio=area_ratio,
                )
            )
        proposals.sort(key=lambda item: item.confidence, reverse=True)
        return proposals[:max_regions]

    def mask(self, bgr_image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        colors = self.plan.important_colors
        if not colors and self.allow_broad_fallback:
            colors = _default_high_visibility_colors()
        if not colors:
            return mask
        for color in colors:
            for lower, upper in COLOR_RANGES.get(color, []):
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array(lower), np.array(upper)))
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _default_high_visibility_colors() -> list[str]:
    return ["red", "orange", "yellow", "blue", "white"]
