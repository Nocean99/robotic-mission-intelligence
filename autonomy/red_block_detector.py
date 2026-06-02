from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from autonomy.types import TargetConfig, TargetDetection


@dataclass
class DetectionDebugFrame:
    image: np.ndarray
    detection: TargetDetection


class RedBlockDetector:
    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    def detect(self, bgr_image: np.ndarray) -> TargetDetection:
        if bgr_image is None or bgr_image.size == 0:
            return TargetDetection(False)
        mask = self.mask(bgr_image)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return TargetDetection(False)
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        if area < self.config.min_area_px:
            return TargetDetection(False, area_px=area)
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            return TargetDetection(False, area_px=area)
        rect_area = float(w * h)
        rectangularity = area / rect_area
        aspect = w / h
        if rectangularity < 0.65 or aspect < 0.35 or aspect > 2.8:
            return TargetDetection(False, area_px=area)
        image_area = float(bgr_image.shape[0] * bgr_image.shape[1])
        area_ratio = rect_area / image_area
        confidence = min(1.0, 0.45 + rectangularity * 0.35 + min(area_ratio / 0.15, 1.0) * 0.2)
        center = (int(x + w / 2), int(y + h / 2))
        bearing = _bearing_from_center(center[0], bgr_image.shape[1])
        return TargetDetection(
            detected=True,
            confidence=round(confidence, 3),
            bbox=(x, y, w, h),
            center_px=center,
            area_px=area,
            area_ratio=area_ratio,
            bearing_rad=bearing,
        )

    def detect_high_recall(self, bgr_image: np.ndarray) -> TargetDetection:
        if bgr_image is None or bgr_image.size == 0:
            return TargetDetection(False)
        mask = self.high_recall_mask(bgr_image)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return TargetDetection(False)
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        min_area = max(25.0, self.config.min_area_px * 0.15)
        if area < min_area:
            return TargetDetection(False, area_px=area)
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            return TargetDetection(False, area_px=area)
        image_area = float(bgr_image.shape[0] * bgr_image.shape[1])
        rect_area = float(w * h)
        area_ratio = rect_area / image_area
        rectangularity = area / rect_area
        confidence = min(0.82, 0.25 + min(area / self.config.min_area_px, 1.0) * 0.25 + rectangularity * 0.2 + min(area_ratio / 0.08, 1.0) * 0.12)
        center = (int(x + w / 2), int(y + h / 2))
        bearing = _bearing_from_center(center[0], bgr_image.shape[1])
        return TargetDetection(
            detected=True,
            confidence=round(confidence, 3),
            bbox=(x, y, w, h),
            center_px=center,
            area_px=area,
            area_ratio=area_ratio,
            bearing_rad=bearing,
        )

    def mask(self, bgr_image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array(self.config.hsv_lower_1), np.array(self.config.hsv_upper_1))
        mask2 = cv2.inRange(hsv, np.array(self.config.hsv_lower_2), np.array(self.config.hsv_upper_2))
        mask = cv2.bitwise_or(mask1, mask2)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    def high_recall_mask(self, bgr_image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        ranges = [
            ((0, 45, 45), (18, 255, 255)),
            ((162, 45, 45), (180, 255, 255)),
        ]
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lower, upper in ranges:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array(lower), np.array(upper)))
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    def debug_frame(self, bgr_image: np.ndarray, detection: TargetDetection | None = None) -> np.ndarray:
        detection = detection or self.detect(bgr_image)
        overlay = bgr_image.copy()
        if detection.bbox:
            x, y, w, h = detection.bbox
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), 3)
            cv2.putText(overlay, f"red_block {detection.confidence:.2f}", (x, max(24, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        mask_bgr = cv2.cvtColor(self.mask(bgr_image), cv2.COLOR_GRAY2BGR)
        return np.hstack([bgr_image, mask_bgr, overlay])

    def save_snapshot(self, bgr_image: np.ndarray, path: str | Path, detection: TargetDetection | None = None) -> None:
        output = self.debug_frame(bgr_image, detection)
        Path(path).parent.mkdir(exist_ok=True)
        cv2.imwrite(str(path), output)


class DetectionConfirmation:
    def __init__(self, required_frames: int) -> None:
        self.required_frames = required_frames
        self.count = 0
        self.last_detection = TargetDetection(False)

    def update(self, detection: TargetDetection) -> bool:
        self.last_detection = detection
        if detection.detected:
            self.count += 1
        else:
            self.count = 0
        return self.confirmed

    @property
    def confirmed(self) -> bool:
        return self.count >= self.required_frames


def _bearing_from_center(center_x: int, image_width: int, horizontal_fov_rad: float = math.radians(90)) -> float:
    normalized = (center_x - image_width / 2) / (image_width / 2)
    return normalized * horizontal_fov_rad / 2
