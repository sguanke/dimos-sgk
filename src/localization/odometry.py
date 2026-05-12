"""Wheel odometry for robot pose estimation.

This module reads wheel encoder data from the Go2 SDK and computes
incremental pose changes to estimate the robot's position.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class Pose2D:
    """2D pose representation (x, y, theta)."""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    timestamp: float = field(default_factory=time.time)


@dataclass
class WheelEncoderData:
    """Wheel encoder readings from Go2."""
    left_ticks: int
    right_ticks: int
    timestamp: float


class WheelOdometry:
    """Computes robot pose from wheel encoder data.

    Attributes:
        wheel_base: Distance between left and right wheels (meters)
        ticks_per_meter: Encoder ticks per meter of wheel travel
        pose: Current estimated pose
        publish_rate: Publishing frequency (Hz)
    """

    def __init__(
        self,
        wheel_base: float = 0.3,
        ticks_per_meter: float = 1000.0,
        publish_rate: float = 50.0
    ):
        """Initialize wheel odometry.

        Args:
            wheel_base: Distance between wheels in meters
            ticks_per_meter: Encoder resolution
            publish_rate: Update frequency in Hz
        """
        self.wheel_base = wheel_base
        self.ticks_per_meter = ticks_per_meter
        self.publish_rate = publish_rate
        self.pose = Pose2D()

        self._prev_left_ticks: Optional[int] = None
        self._prev_right_ticks: Optional[int] = None
        self._logger = logging.getLogger(__name__)

        self._logger.info(
            f"WheelOdometry initialized: wheel_base={wheel_base}m, "
            f"rate={publish_rate}Hz"
        )

    def update(self, encoder_data: WheelEncoderData) -> Pose2D:
        """Update pose estimate from encoder data.

        Args:
            encoder_data: Current wheel encoder readings

        Returns:
            Updated pose estimate
        """
        if self._prev_left_ticks is None:
            self._prev_left_ticks = encoder_data.left_ticks
            self._prev_right_ticks = encoder_data.right_ticks
            return self.pose

        # Compute incremental changes
        delta_left = encoder_data.left_ticks - self._prev_left_ticks
        delta_right = encoder_data.right_ticks - self._prev_right_ticks

        # Convert ticks to distance
        dist_left = delta_left / self.ticks_per_meter
        dist_right = delta_right / self.ticks_per_meter

        # Compute pose change
        dx, dy, dtheta = self._compute_pose_change(dist_left, dist_right)

        # Update pose
        self.pose = self._integrate_pose_change(dx, dy, dtheta)
        self.pose.timestamp = encoder_data.timestamp

        # Update previous values
        self._prev_left_ticks = encoder_data.left_ticks
        self._prev_right_ticks = encoder_data.right_ticks

        return self.pose

    def _compute_pose_change(
        self, dist_left: float, dist_right: float
    ) -> tuple[float, float, float]:
        """Compute incremental pose change from wheel distances.

        Args:
            dist_left: Left wheel distance traveled
            dist_right: Right wheel distance traveled

        Returns:
            Tuple of (dx, dy, dtheta) in robot frame
        """
        # Average distance traveled
        dist_center = (dist_left + dist_right) / 2.0

        # Change in orientation
        dtheta = (dist_right - dist_left) / self.wheel_base

        # Position change in robot frame
        if abs(dtheta) < 1e-6:
            # Straight line motion
            dx = dist_center
            dy = 0.0
        else:
            # Arc motion
            radius = dist_center / dtheta
            dx = radius * np.sin(dtheta)
            dy = radius * (1 - np.cos(dtheta))

        return dx, dy, dtheta

    def _integrate_pose_change(
        self, dx: float, dy: float, dtheta: float
    ) -> Pose2D:
        """Integrate pose change into world frame.

        Args:
            dx: Forward displacement in robot frame
            dy: Lateral displacement in robot frame
            dtheta: Change in orientation

        Returns:
            Updated pose in world frame
        """
        # Rotate displacement to world frame
        cos_theta = np.cos(self.pose.theta)
        sin_theta = np.sin(self.pose.theta)

        dx_world = dx * cos_theta - dy * sin_theta
        dy_world = dx * sin_theta + dy * cos_theta

        # Update pose
        new_pose = Pose2D(
            x=self.pose.x + dx_world,
            y=self.pose.y + dy_world,
            theta=self._normalize_angle(self.pose.theta + dtheta)
        )

        return new_pose

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-pi, pi].

        Args:
            angle: Angle in radians

        Returns:
            Normalized angle
        """
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle

    def reset(self, pose: Optional[Pose2D] = None) -> None:
        """Reset odometry to given pose or origin.

        Args:
            pose: New pose, or None to reset to origin
        """
        self.pose = pose if pose is not None else Pose2D()
        self._prev_left_ticks = None
        self._prev_right_ticks = None
        self._logger.info(f"Odometry reset to: {self.pose}")

    def get_pose(self) -> Pose2D:
        """Get current pose estimate.

        Returns:
            Current pose
        """
        return self.pose
