"""Robot pose estimator combining odometry and IMU data.

This module maintains the robot's pose estimate by combining wheel odometry
and IMU data, providing pose with uncertainty estimates.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import logging
import time

from .odometry import Pose2D, WheelOdometry, WheelEncoderData
from .imu_fusion import IMUFusion, IMUData, FusedPose

logger = logging.getLogger(__name__)


@dataclass
class PoseEstimate:
    """Robot pose estimate with covariance."""
    pose: Pose2D
    covariance: np.ndarray  # 3x3 covariance matrix (x, y, theta)
    timestamp: float = 0.0


class PoseEstimator:
    """Estimates robot pose by fusing odometry and IMU data."""

    def __init__(
        self,
        wheel_base: float = 0.3,
        wheel_radius: float = 0.08,
        ticks_per_revolution: int = 1024,
        imu_alpha: float = 0.98
    ):
        """Initialize pose estimator.

        Args:
            wheel_base: Distance between wheels (meters)
            wheel_radius: Wheel radius (meters)
            ticks_per_revolution: Encoder ticks per revolution
            imu_alpha: IMU complementary filter weight
        """
        self.odometry = WheelOdometry(
            wheel_base=wheel_base,
            wheel_radius=wheel_radius,
            ticks_per_revolution=ticks_per_revolution
        )
        self.imu_fusion = IMUFusion(alpha=imu_alpha)

        self.pose_estimate = PoseEstimate(
            pose=Pose2D(),
            covariance=np.eye(3) * 0.01,
            timestamp=time.time()
        )

        self._odometry_noise = np.array([0.01, 0.01, 0.001])
        self._imu_noise = 0.01

        logger.info("PoseEstimator initialized")

    def update(
        self,
        encoder_data: WheelEncoderData,
        imu_data: IMUData
    ) -> PoseEstimate:
        """Update pose estimate with new sensor data.

        Args:
            encoder_data: Wheel encoder readings
            imu_data: IMU sensor readings

        Returns:
            Updated pose estimate with covariance
        """
        odometry_pose = self.odometry.update(encoder_data)

        fused_result = self.imu_fusion.update(odometry_pose, imu_data)

        self._update_covariance(fused_result)

        self.pose_estimate = PoseEstimate(
            pose=fused_result.pose,
            covariance=self.pose_estimate.covariance.copy(),
            timestamp=imu_data.timestamp
        )

        if fused_result.sudden_movement_detected:
            logger.warning("Sudden movement detected, increasing uncertainty")
            self.pose_estimate.covariance *= 2.0

        logger.debug(
            f"Pose estimate: ({self.pose_estimate.pose.x:.3f}, "
            f"{self.pose_estimate.pose.y:.3f}, "
            f"{np.degrees(self.pose_estimate.pose.theta):.1f}°)"
        )

        return self.pose_estimate

    def _update_covariance(self, fused_result: FusedPose) -> None:
        """Update pose covariance matrix.

        Args:
            fused_result: Fused pose with orientation variance
        """
        dt = 0.02

        process_noise = np.diag([
            self._odometry_noise[0] * dt,
            self._odometry_noise[1] * dt,
            self._odometry_noise[2] * dt
        ])

        self.pose_estimate.covariance += process_noise

        self.pose_estimate.covariance[2, 2] = min(
            self.pose_estimate.covariance[2, 2],
            fused_result.orientation_variance
        )

        max_variance = np.array([1.0, 1.0, 0.1])
        for i in range(3):
            self.pose_estimate.covariance[i, i] = min(
                self.pose_estimate.covariance[i, i],
                max_variance[i]
            )

    def reset(self, pose: Optional[Pose2D] = None) -> None:
        """Reset pose estimate to given pose or origin.

        Args:
            pose: New pose to set, or None for origin
        """
        if pose is None:
            pose = Pose2D()

        self.odometry.reset(pose)
        self.imu_fusion.reset(pose.theta)

        self.pose_estimate = PoseEstimate(
            pose=pose,
            covariance=np.eye(3) * 0.01,
            timestamp=time.time()
        )

        logger.info(
            f"Pose estimator reset to ({pose.x:.3f}, {pose.y:.3f}, "
            f"{np.degrees(pose.theta):.1f}°)"
        )

    def get_pose(self) -> Pose2D:
        """Get current pose estimate.

        Returns:
            Current pose
        """
        return self.pose_estimate.pose

    def get_pose_with_covariance(self) -> PoseEstimate:
        """Get current pose estimate with covariance.

        Returns:
            Pose estimate with uncertainty
        """
        return self.pose_estimate

    def get_uncertainty(self) -> tuple[float, float, float]:
        """Get pose uncertainty (standard deviations).

        Returns:
            Tuple of (sigma_x, sigma_y, sigma_theta)
        """
        return (
            np.sqrt(self.pose_estimate.covariance[0, 0]),
            np.sqrt(self.pose_estimate.covariance[1, 1]),
            np.sqrt(self.pose_estimate.covariance[2, 2])
        )
