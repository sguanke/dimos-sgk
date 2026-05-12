"""Unit tests for pose_estimator module."""

import pytest
import time
import numpy as np

from src.localization.pose_estimator import PoseEstimator, PoseWithCovariance
from src.localization.odometry import WheelEncoderData, Pose2D
from src.localization.imu_fusion import IMUData


@pytest.fixture
def pose_estimator():
    """Create PoseEstimator instance."""
    return PoseEstimator(
        wheel_base=0.3,
        ticks_per_meter=1000.0,
        imu_alpha=0.98,
        publish_rate=50.0
    )


@pytest.fixture
def sample_encoder_data():
    """Create sample encoder data."""
    return WheelEncoderData(
        left_ticks=1000,
        right_ticks=1000,
        timestamp=time.time()
    )


@pytest.fixture
def sample_imu_data():
    """Create sample IMU data."""
    return IMUData(
        accel_x=0.0,
        accel_y=0.0,
        accel_z=9.81,
        gyro_x=0.0,
        gyro_y=0.0,
        gyro_z=0.1,
        timestamp=time.time()
    )


class TestPoseEstimator:
    """Test PoseEstimator class."""

    def test_initialization(self, pose_estimator):
        """Test pose estimator initialization."""
        assert pose_estimator.publish_rate == 50.0
        assert pose_estimator.pose.x == 0.0
        assert pose_estimator.pose.y == 0.0
        assert pose_estimator.pose.theta == 0.0
        assert pose_estimator.pose.covariance.shape == (3, 3)

    def test_update(self, pose_estimator, sample_encoder_data, sample_imu_data):
        """Test pose update from sensor data."""
        pose = pose_estimator.update(sample_encoder_data, sample_imu_data)

        assert isinstance(pose, PoseWithCovariance)
        assert pose.covariance.shape == (3, 3)

    def test_update_multiple_times(self, pose_estimator):
        """Test multiple sequential updates."""
        for i in range(10):
            encoder_data = WheelEncoderData(
                left_ticks=i * 100,
                right_ticks=i * 100,
                timestamp=time.time() + i * 0.02
            )
            imu_data = IMUData(
                accel_x=0.0,
                accel_y=0.0,
                accel_z=9.81,
                gyro_x=0.0,
                gyro_y=0.0,
                gyro_z=0.1,
                timestamp=time.time() + i * 0.02
            )
            pose = pose_estimator.update(encoder_data, imu_data)

        assert isinstance(pose, PoseWithCovariance)

    def test_covariance_grows(self, pose_estimator, sample_encoder_data, sample_imu_data):
        """Test that covariance grows with updates."""
        initial_cov = pose_estimator.pose.covariance.copy()

        for _ in range(10):
            pose_estimator.update(sample_encoder_data, sample_imu_data)

        final_cov = pose_estimator.pose.covariance

        assert np.any(final_cov > initial_cov)

    def test_covariance_bounded(self, pose_estimator, sample_encoder_data, sample_imu_data):
        """Test that covariance is bounded."""
        for _ in range(100):
            pose_estimator.update(sample_encoder_data, sample_imu_data)

        cov = pose_estimator.pose.covariance
        assert cov[0, 0] <= 1.0 ** 2
        assert cov[1, 1] <= 1.0 ** 2
        assert cov[2, 2] <= 0.5 ** 2

    def test_reset_to_origin(self, pose_estimator, sample_encoder_data, sample_imu_data):
        """Test reset to origin."""
        pose_estimator.update(sample_encoder_data, sample_imu_data)

        pose_estimator.reset()

        assert pose_estimator.pose.x == 0.0
        assert pose_estimator.pose.y == 0.0
        assert pose_estimator.pose.theta == 0.0

    def test_reset_to_custom_pose(self, pose_estimator):
        """Test reset to custom pose."""
        custom_cov = np.eye(3) * 0.5
        pose_estimator.reset(x=5.0, y=3.0, theta=np.pi/2, covariance=custom_cov)

        assert pose_estimator.pose.x == 5.0
        assert pose_estimator.pose.y == 3.0
        assert pose_estimator.pose.theta == np.pi/2
        assert np.allclose(pose_estimator.pose.covariance, custom_cov)

    def test_reset_with_default_covariance(self, pose_estimator):
        """Test reset with default covariance."""
        pose_estimator.reset(x=1.0, y=2.0, theta=0.5)

        assert pose_estimator.pose.covariance.shape == (3, 3)
        assert pose_estimator.pose.covariance[0, 0] == 0.01

    def test_get_pose(self, pose_estimator):
        """Test getting current pose."""
        pose = pose_estimator.get_pose()

        assert isinstance(pose, PoseWithCovariance)
        assert pose.x == 0.0
        assert pose.y == 0.0

    def test_get_uncertainty(self, pose_estimator):
        """Test getting pose uncertainty."""
        sigma_x, sigma_y, sigma_theta = pose_estimator.get_uncertainty()

        assert sigma_x > 0
        assert sigma_y > 0
        assert sigma_theta > 0

    def test_uncertainty_increases(self, pose_estimator, sample_encoder_data, sample_imu_data):
        """Test that uncertainty increases with motion."""
        sigma_x1, sigma_y1, sigma_theta1 = pose_estimator.get_uncertainty()

        for _ in range(10):
            pose_estimator.update(sample_encoder_data, sample_imu_data)

        sigma_x2, sigma_y2, sigma_theta2 = pose_estimator.get_uncertainty()

        assert sigma_x2 >= sigma_x1
        assert sigma_y2 >= sigma_y1

    def test_create_pose_with_covariance(self, pose_estimator):
        """Test creating pose with covariance from fused pose."""
        from src.localization.imu_fusion import FusedPose

        fused_pose = FusedPose(
            x=1.0,
            y=2.0,
            theta=0.5,
            timestamp=time.time()
        )

        pose = pose_estimator._create_pose_with_covariance(fused_pose)

        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.theta == 0.5
        assert pose.covariance.shape == (3, 3)

    def test_update_covariance(self, pose_estimator):
        """Test covariance update."""
        initial_cov = pose_estimator.pose.covariance.copy()

        pose_estimator._update_covariance()

        assert np.any(pose_estimator.pose.covariance != initial_cov)

    def test_dataclass(self):
        """Test PoseWithCovariance dataclass."""
        cov = np.eye(3) * 0.1
        pose = PoseWithCovariance(
            x=1.0,
            y=2.0,
            theta=0.5,
            covariance=cov,
            timestamp=123.456
        )

        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.theta == 0.5
        assert pose.covariance.shape == (3, 3)
        assert pose.timestamp == 123.456

    def test_odometry_and_imu_integration(self, pose_estimator):
        """Test that odometry and IMU are properly integrated."""
        encoder_data = WheelEncoderData(
            left_ticks=0,
            right_ticks=0,
            timestamp=time.time()
        )
        imu_data = IMUData(
            accel_x=0.0,
            accel_y=0.0,
            accel_z=9.81,
            gyro_x=0.0,
            gyro_y=0.0,
            gyro_z=0.0,
            timestamp=time.time()
        )

        pose1 = pose_estimator.update(encoder_data, imu_data)

        encoder_data.left_ticks = 1000
        encoder_data.right_ticks = 1000
        encoder_data.timestamp = time.time()
        imu_data.timestamp = time.time()

        pose2 = pose_estimator.update(encoder_data, imu_data)

        assert pose2.x > pose1.x or pose2.y != pose1.y
