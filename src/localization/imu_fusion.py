"""IMU data fusion for orientation correction.

This module reads IMU data (accelerometer, gyroscope) from the Go2 SDK
and fuses it with odometry using a complementary filter to correct
orientation drift.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import logging
import time

from .odometry import Pose2D

logger = logging.getLogger(__name__)


@dataclass
class IMUData:
    """IMU sensor readings."""
    accel_x: float  # m/s²
    accel_y: float  # m/s²
    accel_z: float  # m/s²
    gyro_x: float  # rad/s
    gyro_y: float  # rad/s
    gyro_z: float  # rad/s
    timestamp: float = field(default_factory=time.time)


@dataclass
class FusedPose:
    """Fused pose with uncertainty estimate."""
    pose: Pose2D
    orientation_variance: float = 0.01  # radians²
    sudden_movement_detected: bool = False


class IMUFusion:
    """Fuses IMU data with odometry using complementary filter."""

    def __init__(
        self,
        alpha: float = 0.98,
        sudden_movement_threshold: float = 20.0
    ):
        """Initialize IMU fusion.

        Args:
            alpha: Complementary filter weight (0-1, higher trusts gyro more)
            sudden_movement_threshold: Acceleration threshold for sudden
                movement detection (m/s²)
        """
        self.alpha = alpha
        self.sudden_movement_threshold = sudden_movement_threshold

        self.fused_orientation: float = 0.0
        self.last_imu_data: Optional[IMUData] = None
        self.orientation_variance: float = 0.01

        logger.info(
            f"IMUFusion initialized: alpha={alpha}, "
            f"sudden_threshold={sudden_movement_threshold}m/s²"
        )

    def update(
        self, odometry_pose: Pose2D, imu_data: IMUData
    ) -> FusedPose:
        """Fuse odometry and IMU data.

        Args:
            odometry_pose: Pose estimate from wheel odometry
            imu_data: Current IMU readings

        Returns:
            Fused pose with corrected orientation
        """
        if self.last_imu_data is None:
            self.fused_orientation = odometry_pose.theta
            self.last_imu_data = imu_data
            return FusedPose(pose=odometry_pose)

        dt = imu_data.timestamp - self.last_imu_data.timestamp
        if dt <= 0 or dt > 1.0:
            logger.warning(f"Invalid IMU dt: {dt}s, skipping fusion")
            self.last_imu_data = imu_data
            return FusedPose(pose=odometry_pose)

        gyro_orientation = self._integrate_gyro(imu_data, dt)

        self.fused_orientation = (
            self.alpha * gyro_orientation +
            (1.0 - self.alpha) * odometry_pose.theta
        )
        self.fused_orientation = self._normalize_angle(
            self.fused_orientation
        )

        self._update_orientation_variance(odometry_pose.theta, dt)

        sudden_movement = self._detect_sudden_movement(imu_data)

        fused_pose = Pose2D(
            x=odometry_pose.x,
            y=odometry_pose.y,
            theta=self.fused_orientation,
            timestamp=imu_data.timestamp
        )

        self.last_imu_data = imu_data

        logger.debug(
            f"IMU fusion: theta_odo={np.degrees(odometry_pose.theta):.1f}°, "
            f"theta_fused={np.degrees(self.fused_orientation):.1f}°, "
            f"variance={self.orientation_variance:.4f}"
        )

        return FusedPose(
            pose=fused_pose,
            orientation_variance=self.orientation_variance,
            sudden_movement_detected=sudden_movement
        )

    def _integrate_gyro(self, imu_data: IMUData, dt: float) -> float:
        """Integrate gyroscope to get orientation change.

        Args:
            imu_data: Current IMU data
            dt: Time step (seconds)

        Returns:
            Updated orientation from gyro integration
        """
        gyro_z_avg = (imu_data.gyro_z + self.last_imu_data.gyro_z) / 2.0
        dtheta = gyro_z_avg * dt
        return self._normalize_angle(self.fused_orientation + dtheta)

    def _update_orientation_variance(
        self, odometry_theta: float, dt: float
    ) -> None:
        """Update orientation uncertainty estimate.

        Args:
            odometry_theta: Orientation from odometry
            dt: Time step (seconds)
        """
        angle_diff = abs(
            self._normalize_angle(self.fused_orientation - odometry_theta)
        )

        process_noise = 0.001 * dt
        measurement_noise = 0.01 * angle_diff

        self.orientation_variance = min(
            self.orientation_variance + process_noise + measurement_noise,
            0.1
        )

    def _detect_sudden_movement(self, imu_data: IMUData) -> bool:
        """Detect sudden movements (falls, collisions).

        Args:
            imu_data: Current IMU data

        Returns:
            True if sudden movement detected
        """
        accel_magnitude = np.sqrt(
            imu_data.accel_x**2 +
            imu_data.accel_y**2 +
            imu_data.accel_z**2
        )

        gravity = 9.81
        accel_deviation = abs(accel_magnitude - gravity)

        if accel_deviation > self.sudden_movement_threshold:
            logger.warning(
                f"Sudden movement detected: accel={accel_magnitude:.2f}m/s²"
            )
            return True

        return False

    def reset(self, orientation: float = 0.0) -> None:
        """Reset IMU fusion state.

        Args:
            orientation: Initial orientation (radians)
        """
        self.fused_orientation = orientation
        self.last_imu_data = None
        self.orientation_variance = 0.01
        logger.info(f"IMU fusion reset to {np.degrees(orientation):.1f}°")

    def get_orientation(self) -> float:
        """Get current fused orientation.

        Returns:
            Fused orientation (radians)
        """
        return self.fused_orientation

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
