"""IMU data fusion for orientation correction.

This module fuses IMU data (accelerometer, gyroscope) with odometry
using a complementary filter to correct orientation drift.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class IMUData:
    """IMU sensor readings from Go2."""
    accel_x: float  # m/s²
    accel_y: float  # m/s²
    accel_z: float  # m/s²
    gyro_x: float  # rad/s
    gyro_y: float  # rad/s
    gyro_z: float  # rad/s
    timestamp: float = field(default_factory=time.time)


@dataclass
class FusedPose:
    """Fused pose with orientation correction."""
    x: float
    y: float
    theta: float
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    timestamp: float = field(default_factory=time.time)


class IMUFusion:
    """Fuses IMU data with odometry using complementary filter.

    Attributes:
        alpha: Complementary filter weight (0-1, higher trusts gyro more)
        gravity: Expected gravity magnitude (m/s²)
        collision_threshold: Acceleration threshold for collision detection
        publish_rate: Publishing frequency (Hz)
    """

    def __init__(
        self,
        alpha: float = 0.98,
        gravity: float = 9.81,
        collision_threshold: float = 20.0,
        publish_rate: float = 50.0
    ):
        """Initialize IMU fusion.

        Args:
            alpha: Complementary filter weight (higher trusts gyro)
            gravity: Expected gravity magnitude
            collision_threshold: Accel threshold for collision detection
            publish_rate: Update frequency in Hz
        """
        self.alpha = alpha
        self.gravity = gravity
        self.collision_threshold = collision_threshold
        self.publish_rate = publish_rate

        self._fused_theta: float = 0.0
        self._prev_timestamp: Optional[float] = None
        self._logger = logging.getLogger(__name__)

        self._logger.info(
            f"IMUFusion initialized: alpha={alpha}, "
            f"collision_threshold={collision_threshold}m/s²"
        )

    def fuse(
        self, odometry_pose, imu_data: IMUData
    ) -> FusedPose:
        """Fuse odometry pose with IMU data.

        Args:
            odometry_pose: Pose from wheel odometry
            imu_data: Current IMU readings

        Returns:
            Fused pose with corrected orientation
        """
        # Initialize timestamp
        if self._prev_timestamp is None:
            self._prev_timestamp = imu_data.timestamp
            self._fused_theta = odometry_pose.theta

        dt = imu_data.timestamp - self._prev_timestamp

        # Complementary filter for orientation
        theta_gyro = self._fused_theta + imu_data.gyro_z * dt
        theta_accel = self._estimate_theta_from_accel(imu_data)

        # Fuse orientations
        self._fused_theta = self._complementary_filter(
            theta_gyro, theta_accel, odometry_pose.theta
        )

        # Detect sudden movements
        accel_magnitude = self._compute_accel_magnitude(imu_data)
        if accel_magnitude > self.collision_threshold:
            self._logger.warning(
                f"Sudden movement detected: {accel_magnitude:.2f} m/s²"
            )

        # Create fused pose
        fused_pose = FusedPose(
            x=odometry_pose.x,
            y=odometry_pose.y,
            theta=self._fused_theta,
            angular_velocity=imu_data.gyro_z,
            timestamp=imu_data.timestamp
        )

        self._prev_timestamp = imu_data.timestamp

        return fused_pose

    def _estimate_theta_from_accel(self, imu_data: IMUData) -> float:
        """Estimate orientation from accelerometer (tilt).

        Args:
            imu_data: IMU readings

        Returns:
            Estimated theta from accelerometer
        """
        # Use accelerometer to estimate tilt (assumes static or slow motion)
        # This is a simplified 2D case
        theta = np.arctan2(imu_data.accel_y, imu_data.accel_x)
        return theta

    def _complementary_filter(
        self, theta_gyro: float, theta_accel: float, theta_odom: float
    ) -> float:
        """Apply complementary filter to fuse orientation estimates.

        Args:
            theta_gyro: Orientation from gyroscope integration
            theta_accel: Orientation from accelerometer
            theta_odom: Orientation from odometry

        Returns:
            Fused orientation
        """
        # Complementary filter: trust gyro for short-term, accel for long-term
        # Also incorporate odometry for additional correction
        theta_fused = (
            self.alpha * theta_gyro +
            (1 - self.alpha) * 0.7 * theta_accel +
            (1 - self.alpha) * 0.3 * theta_odom
        )

        return self._normalize_angle(theta_fused)

    def _compute_accel_magnitude(self, imu_data: IMUData) -> float:
        """Compute total acceleration magnitude.

        Args:
            imu_data: IMU readings

        Returns:
            Acceleration magnitude in m/s²
        """
        accel_mag = np.sqrt(
            imu_data.accel_x**2 +
            imu_data.accel_y**2 +
            imu_data.accel_z**2
        )
        return accel_mag

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

    def reset(self, theta: float = 0.0) -> None:
        """Reset IMU fusion state.

        Args:
            theta: Initial orientation
        """
        self._fused_theta = theta
        self._prev_timestamp = None
        self._logger.info(f"IMU fusion reset to theta={theta}")

    def detect_collision(self, imu_data: IMUData) -> bool:
        """Detect collision from sudden acceleration.

        Args:
            imu_data: Current IMU readings

        Returns:
            True if collision detected
        """
        accel_magnitude = self._compute_accel_magnitude(imu_data)
        return accel_magnitude > self.collision_threshold
