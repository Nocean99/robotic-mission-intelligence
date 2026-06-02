from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import cv2

from autonomy.camera_interface import ROS2CameraSubscriber, SyntheticRedBlockSource, VideoFileFrameSource
from autonomy.config_loader import load_search_mission_config
from autonomy.red_block_detector import RedBlockDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Save raw/mask/overlay debug frame from search camera")
    parser.add_argument("--config", default="config/autonomy.yaml")
    parser.add_argument("--camera-topic", default="/camera/image_raw")
    parser.add_argument("--video")
    parser.add_argument("--synthetic-camera", action="store_true")
    parser.add_argument("--output-dir", default="logs")
    parser.add_argument("--no-require-camera-topic", action="store_true")
    parser.add_argument("--wait-s", type=float, default=10.0)
    args = parser.parse_args()

    config = load_search_mission_config(args.config)
    detector = RedBlockDetector(config.target)
    if args.synthetic_camera:
        camera = SyntheticRedBlockSource()
    elif args.video:
        camera = VideoFileFrameSource(args.video, loop=False)
    else:
        camera = ROS2CameraSubscriber(args.camera_topic, require_topic=not args.no_require_camera_topic)

    frame = None
    attempts = max(1, int(args.wait_s / 0.1))
    for _ in range(attempts):
        frame = camera.latest_frame()
        if frame is not None:
            break
        import time
        time.sleep(0.1)
    if frame is None:
        raise RuntimeError("No camera frame received. Check the camera topic and Gazebo bridge.")

    detection = detector.detect(frame)
    debug = detector.debug_frame(frame, detection)
    Path(args.output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(args.output_dir) / f"debug_camera_{timestamp}.png"
    cv2.imwrite(str(path), debug)
    print(f"Saved debug camera frame: {path}")
    print(f"Detection: detected={detection.detected} confidence={detection.confidence} bbox={detection.bbox}")


if __name__ == "__main__":
    main()
