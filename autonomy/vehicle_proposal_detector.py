from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from autonomy.types import TargetDetection


VEHICLE_TERMS = {
    "vehicle",
    "small vehicle",
    "large vehicle",
    "car",
    "truck",
    "van",
    "bus",
    "freight",
    "freight car",
    "jeep",
    "suv",
    "pickup",
}


class VehicleProposalDetector:
    """Lightweight vehicle proposal layer for aerial RGB and infrared imagery."""

    def __init__(self, min_area_px: int = 12, max_area_ratio: float = 0.08) -> None:
        self.min_area_px = min_area_px
        self.max_area_ratio = max_area_ratio

    def detect(self, frame_bgr: np.ndarray, *, modality: str = "rgb", allow_fallback: bool = True) -> TargetDetection:
        if frame_bgr is None or frame_bgr.size == 0:
            return TargetDetection(False, sensor_modality=modality)
        if modality == "infrared":
            candidates = self._ir_candidates(frame_bgr)
        else:
            candidates = self._rgb_candidates(frame_bgr)
        if candidates:
            return max(candidates, key=lambda item: item.confidence)
        if allow_fallback:
            return self.full_frame_fallback(frame_bgr, modality=modality)
        return TargetDetection(False, sensor_modality=modality)

    def mask(self, frame_bgr: np.ndarray, *, modality: str = "rgb") -> np.ndarray:
        if frame_bgr is None or frame_bgr.size == 0:
            return np.zeros((1, 1), dtype=np.uint8)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if modality == "infrared":
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        edges = cv2.Canny(gray, 45, 130)
        contrast = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, np.ones((9, 9), np.uint8))
        _, contrast_mask = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.bitwise_or(edges, contrast_mask)

    def full_frame_fallback(self, frame_bgr: np.ndarray, *, modality: str) -> TargetDetection:
        height, width = frame_bgr.shape[:2]
        return TargetDetection(
            True,
            confidence=0.32,
            bbox=None,
            center_px=(width // 2, height // 2),
            area_px=float(width * height),
            area_ratio=1.0,
            sensor_modality=modality,
            proposal_reason="full-frame fallback",
        )

    def _rgb_candidates(self, frame_bgr: np.ndarray) -> list[TargetDetection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        masks = []
        edges = cv2.Canny(gray, 40, 130)
        masks.append(cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1))
        contrast = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, np.ones((11, 11), np.uint8))
        _, contrast_mask = cv2.threshold(contrast, max(18, int(np.percentile(contrast, 92))), 255, cv2.THRESH_BINARY)
        masks.append(cv2.morphologyEx(contrast_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)))
        return self._detections_from_masks(
            masks=masks,
            frame_shape=gray.shape,
            modality="rgb",
            default_reason="small high-contrast object",
            rectangle_reason="rectangle-like aerial object",
        )

    def _ir_candidates(self, frame_bgr: np.ndarray) -> list[TargetDetection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        high = max(20, int(np.percentile(blurred, 92)))
        _, hot_mask = cv2.threshold(blurred, high, 255, cv2.THRESH_BINARY)
        local_contrast = cv2.morphologyEx(blurred, cv2.MORPH_TOPHAT, np.ones((13, 13), np.uint8))
        _, contrast_mask = cv2.threshold(local_contrast, max(10, int(np.percentile(local_contrast, 88))), 255, cv2.THRESH_BINARY)
        masks = [
            cv2.morphologyEx(hot_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)),
            cv2.morphologyEx(contrast_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)),
        ]
        return self._detections_from_masks(
            masks=masks,
            frame_shape=gray.shape,
            modality="infrared",
            default_reason="hot IR blob",
            rectangle_reason="hot IR blob",
        )

    def _detections_from_masks(
        self,
        *,
        masks: list[np.ndarray],
        frame_shape: tuple[int, int],
        modality: str,
        default_reason: str,
        rectangle_reason: str,
    ) -> list[TargetDetection]:
        height, width = frame_shape
        frame_area = float(height * width)
        detections = []
        for mask in masks:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = float(cv2.contourArea(contour))
                if area < self.min_area_px:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                if w <= 1 or h <= 1:
                    continue
                area_ratio = (w * h) / frame_area
                if area_ratio > self.max_area_ratio:
                    continue
                aspect = w / float(h)
                if aspect < 0.25 or aspect > 4.5:
                    continue
                extent = area / float(max(1, w * h))
                rectangle_like = 0.35 <= extent <= 1.05 and 0.35 <= aspect <= 3.2
                contrast_score = min(1.0, area / max(self.min_area_px, 1) / 8.0)
                shape_score = 0.18 if rectangle_like else 0.0
                confidence = min(0.86, 0.42 + contrast_score * 0.28 + shape_score)
                reason = rectangle_reason if rectangle_like else default_reason
                detections.append(
                    TargetDetection(
                        True,
                        confidence=round(confidence, 3),
                        bbox=(int(x), int(y), int(w), int(h)),
                        center_px=(int(x + w / 2), int(y + h / 2)),
                        area_px=area,
                        area_ratio=area_ratio,
                        sensor_modality=modality,
                        proposal_reason=reason,
                    )
                )
        return detections


def is_vehicle_mission_text(text: str) -> bool:
    normalized = text.lower().replace("-", " ")
    return any(term in normalized for term in VEHICLE_TERMS)


def is_vehicle_vision_plan(vision_plan) -> bool:
    categories = {str(item).lower().replace("-", " ") for item in getattr(vision_plan, "possible_categories", [])}
    return bool(categories & VEHICLE_TERMS)


def infer_sensor_modality(source_path: str | Path | None, frame_bgr: np.ndarray | None = None) -> str:
    path_text = "" if source_path is None else str(source_path).lower()
    if any(term in path_text for term in ("rgb", "visible", "trainimg", "valimg", "testimg", "dronevehicle_rgb")):
        return "rgb"
    if any(term in path_text for term in ("infrared", "thermal", "ir_", "_ir", "imgr", "labelr", "dronevehicle_ir")):
        return "infrared"
    if frame_bgr is not None and frame_bgr.size:
        channels = cv2.split(frame_bgr)
        channel_delta = max(float(np.mean(cv2.absdiff(channels[0], channels[1]))), float(np.mean(cv2.absdiff(channels[1], channels[2]))))
        if channel_delta < 1.5:
            return "infrared"
    return "rgb"
