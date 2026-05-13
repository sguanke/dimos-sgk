"""Wheel odometry for robot pose estimation.

This module reads wheel encoder data from the Go2 SDK and computes
incremental pose changes to estimate the robot's position.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class Pose2D:
    """2D pose representation (x, y, theta)."""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    timestamp: float = field(default_factory=time.time)


@dataclass
class WheelEncoderData:
    """Wheel encoder readings."""
    left_ticks: int
    right_ticks: int
    timestamp: float


class WheelOdometry:
    """Computes odometry from wheel encoder data."""

    def __init__(
        self,
        wheel_base: float = 0.3,
        wheel_radius: float = 0.08,
        ticks_per_revolution: int = 1024
    ):
        """Initialize wheel odometry.

        Args:
            wheel_base: Distance between left and right wheels (meters)
            wheel_radius: Radius of the wheels (meters)
            ticks_per_revolution: Encoder ticks per wheel revolution
        """
        self.wheel_base = wheel_base
        self.wheel_radius = wheel_radius
        self.ticks_per_revolution = ticks_per_revolution

        self.pose = Pose2D()
        self.last_encoder_data: Optional[WheelEncoderData] = None

        self._meters_per_tick = (
            2.0 * np.pi * wheel_radius / ticks_per_revolution
        )

        logger.info(
            f"WheelOdometry initialized: wheel_base={wheel_base}m, "
            f"wheel_radius={wheel_radius}m, "
            f"meters_per_tick={self._meters_per_tick:.6f}m"
        )

    def update(self, encoder_data: WheelEncoderData) -> Pose2D:
        """Update odometry with new encoder data.

        Args:
            encoder_data: Current wheel encoder readings

        Returns:
            Updated pose estimate
        """
        if self.last_encoder_data is None:
            self.last_encoder_data = encoder_data
            return self.pose

        delta_left = (
            encoder_data.left_ticks - self.last_encoder_data.left_ticks
        )
        delta_right = (
            encoder_data.right_ticks - self.last_encoder_data.right_ticks
        )

        distance_left = delta_left * self._meters_per_tick
        distance_right = delta_right * self._meters_per_tick

        dx, dy, dtheta = self._compute_pose_delta(
            distance_left, distance_right
        )

        self.pose.x += dx
        self.pose.y += dy
        self.pose.theta += dtheta
        self.pose.theta = self._normalize_angle(self.pose.theta)
        self.pose.timestamp = encoder_data.timestamp

        self.last_encoder_data = encoder_data

        logger.debug(
            f"Odometry update: pose=({self.pose.x:.3f}, {self.pose.y:.3f}, "
            f"{np.degrees(self.pose.theta):.1f}°)"
        )

        return self.pose

    def _compute_pose_delta(
        self, distance_left: float, distance_right: float
    ) -> tuple[float, float, float]:
        """Compute incremental pose change from wheel distances.

        Args:
            distance_left: Distance traveled by left wheel
            distance_right: Distance traveled by right wheel

        Returns:
            Tuple of (dx, dy, dtheta) in robot frame
        """
        distance_center = (distance_left + distance_right) / 2.0
        dtheta = (distance_right - distance_left) / self.wheel_base

        if abs(dtheta) < 1e-6:
            dx = distance_center * np.cos(self.pose.theta)
            dy = distance_center * np.sin(self.pose.theta)
        else:
            radius = distance_center / dtheta
            dx = radius * (
                np.sin(self.pose.theta + dtheta) - np.sin(self.pose.theta)
            )
            dy = -radius * (
                np.cos(self.pose.theta + dtheta) - np.cos(self.pose.theta)
            )

        return dx, dy, dtheta

    def reset(self, pose: Optional[Pose2D] = None) -> None:
        """Reset odometry to given pose or origin.

        Args:
            pose: New pose to set, or None for origin
        """
        if pose is None:
            self.pose = Pose2D()
        else:
            self.pose = pose

        self.last_encoder_data = None
        logger.info(f"Odometry reset to ({self.pose.x}, {self.pose.y})")

    def get_pose(self) -> Pose2D:
        """Get current odometry pose estimate.

        Returns:
            Current pose
        """
        return self.pose

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi].

        Args:
            angle: Angle in radians

        Returns:
            Normalized angle
        """
        while angle > np.pi:
            angle -= 2.0 * np.pi
        while angle < -np.pi:
            angle += 2.0 * np.pi
        return angle
