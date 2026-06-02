from __future__ import annotations

import logging
import time

import cv2
import numpy as np


LOGGER = logging.getLogger(__name__)


class CameraFrameSource:
    def latest_frame(self) -> np.ndarray | None:
        raise NotImplementedError


class CvBridgeImageConverter:
    def __init__(self, bridge) -> None:
        self.bridge = bridge

    def to_bgr(self, msg) -> np.ndarray:
        return self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")


class ROS2CameraSubscriber(CameraFrameSource):
    def __init__(
        self,
        topic: str = "/camera/image_raw",
        node_name: str = "search_camera_subscriber",
        require_topic: bool = True,
        topic_timeout_s: float = 5.0,
    ) -> None:
        try:
            import rclpy
            from cv_bridge import CvBridge
            from rclpy.node import Node
            from sensor_msgs.msg import Image
        except ImportError as exc:
            raise RuntimeError("ROS 2 camera dependencies are missing. Source ROS 2 and install cv_bridge.") from exc
        if not rclpy.ok():
            rclpy.init()

        class _Node(Node):
            pass

        self._rclpy = rclpy
        self.node = _Node(node_name)
        self.converter = CvBridgeImageConverter(CvBridge())
        self.topic = topic
        self.frame: np.ndarray | None = None
        self.last_error: str | None = None
        self.first_frame_logged = False
        self.frame_count = 0
        self.started_at = time.monotonic()
        self.last_frame_at: float | None = None
        self.node.create_subscription(Image, topic, self._image_cb, 10)
        if require_topic and not self._wait_for_topic(topic, topic_timeout_s):
            available = ", ".join(name for name, _ in self.node.get_topic_names_and_types())
            raise RuntimeError(f"Camera topic '{topic}' was not found within {topic_timeout_s:.1f}s. Available topics: {available}")
        LOGGER.info("Subscribed to ROS 2 camera topic %s", topic)

    def latest_frame(self) -> np.ndarray | None:
        self._rclpy.spin_once(self.node, timeout_sec=0.0)
        return self.frame

    def _image_cb(self, msg) -> None:
        try:
            self.frame = self.converter.to_bgr(msg)
            self.last_error = None
            self.frame_count += 1
            now = time.monotonic()
            self.last_frame_at = now
            if not self.first_frame_logged:
                height, width = self.frame.shape[:2]
                LOGGER.info("First camera frame received from %s: %dx%d", self.topic, width, height)
                self.first_frame_logged = True
            elif self.frame_count % 30 == 0:
                elapsed = max(1e-6, now - self.started_at)
                LOGGER.info("Camera %s frame rate estimate: %.2f fps", self.topic, self.frame_count / elapsed)
        except Exception as exc:
            self.frame = None
            self.last_error = str(exc)
            LOGGER.warning("Camera image conversion failed on %s: %s", self.topic, exc)

    def _wait_for_topic(self, topic: str, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self._rclpy.spin_once(self.node, timeout_sec=0.1)
            names = {name for name, _ in self.node.get_topic_names_and_types()}
            if topic in names:
                return True
        return False


class GzCameraSubscriber(CameraFrameSource):
    DEFAULT_TOPIC = "/world/red_block_search/model/x500_mono_cam_0/link/camera_link/sensor/camera/image"

    def __init__(
        self,
        topic: str | None = None,
        require_topic: bool = True,
        topic_timeout_s: float = 5.0,
    ) -> None:
        try:
            import gz.transport13 as gz_transport
            from gz.msgs10.image_pb2 import Image as GzImage
        except ImportError as exc:
            raise RuntimeError(
                "Gazebo Transport Python bindings are missing. "
                "Install gz-transport13 and gz-msgs10 (and 'protobuf')."
            ) from exc

        self._gz_transport = gz_transport
        self._GzImage = GzImage
        self.topic = topic or self.DEFAULT_TOPIC
        self.frame: np.ndarray | None = None
        self.last_error: str | None = None
        self.first_frame_logged = False
        self.frame_count = 0
        self.started_at = time.monotonic()
        self.last_frame_at: float | None = None
        self._lock = __import__("threading").Lock()
        self.node = gz_transport.Node()

        if require_topic and not self._wait_for_topic(self.topic, topic_timeout_s):
            available = ", ".join(self.node.topic_list())
            raise RuntimeError(
                f"Gazebo camera topic '{self.topic}' was not found within {topic_timeout_s:.1f}s. "
                f"Available topics: {available}"
            )

        if not self.node.subscribe(GzImage, self.topic, self._image_cb):
            raise RuntimeError(f"Failed to subscribe to Gazebo topic '{self.topic}'")
        LOGGER.info("Subscribed to Gazebo camera topic %s", self.topic)

    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return self.frame

    def _image_cb(self, msg) -> None:
        try:
            frame = self._gz_image_to_bgr(msg)
            now = time.monotonic()
            with self._lock:
                self.frame = frame
                self.last_error = None
                self.frame_count += 1
                self.last_frame_at = now
                logged = self.first_frame_logged
                count = self.frame_count
                self.first_frame_logged = True
            if not logged:
                h, w = frame.shape[:2]
                LOGGER.info("First Gazebo camera frame received from %s: %dx%d", self.topic, w, h)
            elif count % 30 == 0:
                elapsed = max(1e-6, now - self.started_at)
                LOGGER.info("Gazebo camera %s frame rate estimate: %.2f fps", self.topic, count / elapsed)
        except Exception as exc:
            with self._lock:
                self.frame = None
                self.last_error = str(exc)
            LOGGER.warning("Gazebo image conversion failed on %s: %s", self.topic, exc)

    def _gz_image_to_bgr(self, msg) -> np.ndarray:
        width = int(msg.width)
        height = int(msg.height)
        pf = msg.pixel_format_type
        ft = self._GzImage.DESCRIPTOR.fields_by_name["pixel_format_type"].enum_type
        name = ft.values_by_number[pf].name if pf in ft.values_by_number else "UNKNOWN"
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        if name == "RGB_INT8":
            arr = buf.reshape((height, width, 3))
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        if name == "BGR_INT8":
            return buf.reshape((height, width, 3)).copy()
        if name == "RGBA_INT8":
            arr = buf.reshape((height, width, 4))
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        if name == "BGRA_INT8":
            arr = buf.reshape((height, width, 4))
            return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        if name == "L_INT8":
            arr = buf.reshape((height, width))
            return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        raise RuntimeError(f"Unsupported Gazebo pixel format: {name}")

    def _wait_for_topic(self, topic: str, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if topic in self.node.topic_list():
                return True
            time.sleep(0.1)
        return False


class VideoFileFrameSource(CameraFrameSource):
    def __init__(self, path: str, loop: bool = True) -> None:
        self.capture = cv2.VideoCapture(path)
        self.loop = loop
        if not self.capture.isOpened():
            raise RuntimeError(f"Could not open video source: {path}")

    def latest_frame(self) -> np.ndarray | None:
        ok, frame = self.capture.read()
        if ok:
            return frame
        if self.loop:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
            return frame if ok else None
        return None


class SyntheticRedBlockSource(CameraFrameSource):
    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.width = width
        self.height = height
        self.started = time.monotonic()

    def latest_frame(self) -> np.ndarray:
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (40, 60, 40)
        t = time.monotonic() - self.started
        x = int(self.width * 0.45 + np.sin(t) * 70)
        y = int(self.height * 0.45)
        cv2.rectangle(frame, (x, y), (x + 90, y + 70), (0, 0, 255), -1)
        return frame
