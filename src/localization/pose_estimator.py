"""Robot pose estimation combining odometry and IMU.

This module maintains the robot's pose in the world frame by combining
odometry and IMU data, and provides uncertainty estimates.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .odometry import WheelOdometry, WheelEncoderData, Pose2D
from .imu_fusion import IMUFusion, IMUData, FusedPose


@dataclass
class PoseWithCovariance:
    """Robot pose with uncertainty estimate."""
    x: float
    y: float
    theta: float
    covariance: np.ndarray  # 3x3 covariance matrix
    timestamp: float = field(default_factory=time.time)


class PoseEstimator:
    """Estimates robot pose by fusing odometry and IMU data.

    Attributes:
        odometry: Wheel odometry module
        imu_fusion: IMU fusion module
        pose: Current pose estimate with covariance
        publish_rate: Publishing frequency (Hz)
    """

    def __init__(
        self,
        wheel_base: float = 0.3,
        ticks_per_meter: float = 1000.0,
        imu_alpha: float = 0.98,
        publish_rate: float = 50.0
    ):
        """Initialize pose estimator.

        Args:
            wheel_base: Distance between wheels in meters
            ticks_per_meter: Encoder resolution
            imu_alpha: IMU complementary filter weight
            publish_rate: Update frequency in Hz
        """
        self.odometry = WheelOdometry(
            wheel_base=wheel_base,
            ticks_per_meter=ticks_per_meter,
            publish_rate=publish_rate
        )
        self.imu_fusion = IMUFusion(
            alpha=imu_alpha,
            publish_rate=publish_rate
        )
        self.publish_rate = publish_rate

        # Initialize pose with covariance
        self.pose = PoseWithCovariance(
            x=0.0,
            y=0.0,
            theta=0.0,
            covariance=np.eye(3) * 0.01  # Initial uncertainty
        )

        self._odom_noise = np.array([0.01, 0.01, 0.02])  # x, y, theta
        self._imu_noise = 0.01  # theta correction noise
        self._logger = logging.getLogger(__name__)

        self._logger.info(
            f"PoseEstimator initialized: rate={publish_rate}Hz"
        )

    def update(
        self,
        encoder_data: WheelEncoderData,
        imu_data: IMUData
    ) -> PoseWithCovariance:
        """Update pose estimate from sensor data.

        Args:
            encoder_data: Wheel encoder readings
            imu_data: IMU sensor readings

        Returns:
            Updated pose with covariance
        """
        # Update odometry
        odom_pose = self.odometry.update(encoder_data)

        # Fuse with IMU
        fused_pose = self.imu_fusion.fuse(odom_pose, imu_data)

        # Update pose estimate
        self.pose = self._create_pose_with_covariance(fused_pose)

        # Update covariance (simplified model)
        self._update_covariance()

        return self.pose

    def _create_pose_with_covariance(
        self, fused_pose: FusedPose
    ) -> PoseWithCovariance:
        """Create pose with covariance from fused pose.

        Args:
            fused_pose: Fused pose from IMU fusion

        Returns:
            Pose with covariance matrix
        """
        return PoseWithCovariance(
            x=fused_pose.x,
            y=fused_pose.y,
            theta=fused_pose.theta,
            covariance=self.pose.covariance.copy(),
            timestamp=fused_pose.timestamp
        )

    def _update_covariance(self) -> None:
        """Update pose covariance (uncertainty growth).

        Uses a simplified motion model where uncertainty grows
        with each update based on odometry and IMU noise.
        """
        # Process noise (uncertainty growth per update)
        Q = np.diag([
            self._odom_noise[0]**2,
            self._odom_noise[1]**2,
            (self._odom_noise[2]**2 + self._imu_noise**2)
        ])

        # Simple covariance update (no Jacobian, simplified model)
        self.pose.covariance = self.pose.covariance + Q

        # Limit maximum uncertainty
        max_variance = np.array([1.0, 1.0, 0.5])  # x, y, theta
        for i in range(3):
            if self.pose.covariance[i, i] > max_variance[i]**2:
                self.pose.covariance[i, i] = max_variance[i]**2

    def reset(
        self,
        x: float = 0.0,
        y: float = 0.0,
        theta: float = 0.0,
        covariance: Optional[np.ndarray] = None
    ) -> None:
        """Reset pose estimate to given values.

        Args:
            x: X position in meters
            y: Y position in meters
            theta: Orientation in radians
            covariance: Initial covariance, or None for default
        """
        # Reset odometry
        self.odometry.reset(Pose2D(x=x, y=y, theta=theta))

        # Reset IMU fusion
        self.imu_fusion.reset(theta=theta)

        # Reset pose with covariance
        if covariance is None:
            covariance = np.eye(3) * 0.01

        self.pose = PoseWithCovariance(
            x=x,
            y=y,
            theta=theta,
            covariance=covariance
        )

        self._logger.info(f"Pose reset to: x={x}, y={y}, theta={theta}")

    def get_pose(self) -> PoseWithCovariance:
        """Get current pose estimate with covariance.

        Returns:
            Current pose with uncertainty
        """
        return self.pose

    def get_uncertainty(self) -> tuple[float, float, float]:
        """Get current pose uncertainty (standard deviations).

        Returns:
            Tuple of (sigma_x, sigma_y, sigma_theta)
        """
        return (
            np.sqrt(self.pose.covariance[0, 0]),
            np.sqrt(self.pose.covariance[1, 1]),
            np.sqrt(self.pose.covariance[2, 2])
        )
