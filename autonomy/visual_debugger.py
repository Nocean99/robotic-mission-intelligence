from __future__ import annotations

import math
from pathlib import Path

from autonomy.config_loader import load_mission_config


def main() -> None:
    try:
        import rclpy
        from geometry_msgs.msg import Point
        from rclpy.node import Node
        from visualization_msgs.msg import Marker, MarkerArray
    except ImportError as exc:
        raise RuntimeError("ROS 2 visualization dependencies are missing. Source ROS 2 before running this node.") from exc

    class VisualDebugger(Node):
        def __init__(self) -> None:
            super().__init__("autonomy_visual_debugger")
            self.config = load_mission_config(Path("config/autonomy.yaml"))
            self.publisher = self.create_publisher(MarkerArray, "/autonomy/debug_markers", 10)
            self.timer = self.create_timer(1.0, self.publish_markers)

        def publish_markers(self) -> None:
            markers = MarkerArray()
            markers.markers.append(self._sphere(0, 0.0, 0.0, 0.0, "home", (0.1, 0.8, 0.2, 1.0), 0.45))
            for index, waypoint in enumerate(self.config.waypoints, start=1):
                markers.markers.append(
                    self._sphere(index, waypoint.x, waypoint.y, waypoint.z, f"wp_{index}", (0.1, 0.5, 1.0, 1.0), 0.35)
                )
            markers.markers.append(self._safety_radius(1000))
            self.publisher.publish(markers)

        def _sphere(self, marker_id: int, x: float, y: float, z: float, namespace: str, color, scale: float):
            marker = Marker()
            marker.header.frame_id = "map"
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = namespace
            marker.id = marker_id
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose.position.x = x
            marker.pose.position.y = y
            marker.pose.position.z = z
            marker.scale.x = scale
            marker.scale.y = scale
            marker.scale.z = scale
            marker.color.r, marker.color.g, marker.color.b, marker.color.a = color
            return marker

        def _safety_radius(self, marker_id: int):
            marker = Marker()
            marker.header.frame_id = "map"
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = "safety_radius"
            marker.id = marker_id
            marker.type = Marker.LINE_STRIP
            marker.action = Marker.ADD
            marker.scale.x = 0.08
            marker.color.r = 1.0
            marker.color.g = 0.8
            marker.color.b = 0.1
            marker.color.a = 1.0
            radius = self.config.max_distance_from_home_m
            for i in range(73):
                angle = 2 * math.pi * i / 72
                point = Point()
                point.x = math.cos(angle) * radius
                point.y = math.sin(angle) * radius
                point.z = 0.0
                marker.points.append(point)
            return marker

    rclpy.init()
    node = VisualDebugger()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

