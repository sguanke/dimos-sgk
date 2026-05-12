"""Unit tests for imu_fusion module."""

import pytest
import time
import numpy as np

from src.localization.imu_fusion import IMUFusion, IMUData, FusedPose
from src.localization.odometry import Pose2D


@pytest.fixture
def imu_fusion():
    """Create IMUFusion instance."""
    return IMUFusion(
        alpha=0.98,
        gravity=9.81,
        collision_threshold=20.0,
        publish_rate=50.0
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


@pytest.fixture
def sample_odom_pose():
    """Create sample odometry pose."""
    return Pose2D(x=1.0, y=2.0, theta=0.5, timestamp=time.time())


class TestIMUFusion:
    """Test IMUFusion class."""

    def test_initialization(self, imu_fusion):
        """Test IMU fusion initialization."""
        assert imu_fusion.alpha == 0.98
        assert imu_fusion.gravity == 9.81
        assert imu_fusion.collision_threshold == 20.0
        assert imu_fusion._fused_theta == 0.0

    def test_fuse_first_call(self, imu_fusion, sample_odom_pose, sample_imu_data):
        """Test first fusion call initializes state."""
        fused_pose = imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        assert isinstance(fused_pose, FusedPose)
        assert fused_pose.x == sample_odom_pose.x
        assert fused_pose.y == sample_odom_pose.y

    def test_fuse_updates_orientation(self, imu_fusion, sample_odom_pose, sample_imu_data):
        """Test fusion updates orientation."""
        fused_pose1 = imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        time.sleep(0.01)
        sample_imu_data.timestamp = time.time()
        fused_pose2 = imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        assert isinstance(fused_pose2, FusedPose)

    def test_fuse_preserves_position(self, imu_fusion, sample_odom_pose, sample_imu_data):
        """Test fusion preserves x, y from odometry."""
        fused_pose = imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        assert fused_pose.x == sample_odom_pose.x
        assert fused_pose.y == sample_odom_pose.y

    def test_estimate_theta_from_accel(self, imu_fusion, sample_imu_data):
        """Test theta estimation from accelerometer."""
        theta = imu_fusion._estimate_theta_from_accel(sample_imu_data)

        assert isinstance(theta, float)
        assert -np.pi <= theta <= np.pi

    def test_complementary_filter(self, imu_fusion):
        """Test complementary filter."""
        theta_gyro = 0.5
        theta_accel = 0.4
        theta_odom = 0.45

        theta_fused = imu_fusion._complementary_filter(
            theta_gyro, theta_accel, theta_odom
        )

        assert isinstance(theta_fused, float)
        assert -np.pi <= theta_fused <= np.pi

    def test_compute_accel_magnitude(self, imu_fusion, sample_imu_data):
        """Test acceleration magnitude computation."""
        mag = imu_fusion._compute_accel_magnitude(sample_imu_data)

        assert mag > 0
        assert abs(mag - 9.81) < 0.1

    def test_compute_accel_magnitude_high(self, imu_fusion):
        """Test high acceleration magnitude."""
        imu_data = IMUData(
            accel_x=10.0,
            accel_y=10.0,
            accel_z=10.0,
            gyro_x=0.0,
            gyro_y=0.0,
            gyro_z=0.0,
            timestamp=time.time()
        )

        mag = imu_fusion._compute_accel_magnitude(imu_data)

        assert mag > 15.0

    def test_normalize_angle(self, imu_fusion):
        """Test angle normalization."""
        assert abs(imu_fusion._normalize_angle(0.0)) < 0.01
        assert abs(imu_fusion._normalize_angle(np.pi)) - np.pi < 0.01

        normalized = imu_fusion._normalize_angle(3 * np.pi)
        assert -np.pi <= normalized <= np.pi

        normalized = imu_fusion._normalize_angle(-3 * np.pi)
        assert -np.pi <= normalized <= np.pi

    def test_reset(self, imu_fusion, sample_odom_pose, sample_imu_data):
        """Test reset functionality."""
        imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        imu_fusion.reset(theta=1.0)

        assert imu_fusion._fused_theta == 1.0
        assert imu_fusion._prev_timestamp is None

    def test_detect_collision_no_collision(self, imu_fusion, sample_imu_data):
        """Test collision detection with normal acceleration."""
        collision = imu_fusion.detect_collision(sample_imu_data)

        assert collision is False

    def test_detect_collision_with_collision(self, imu_fusion):
        """Test collision detection with high acceleration."""
        imu_data = IMUData(
            accel_x=15.0,
            accel_y=15.0,
            accel_z=15.0,
            gyro_x=0.0,
            gyro_y=0.0,
            gyro_z=0.0,
            timestamp=time.time()
        )

        collision = imu_fusion.detect_collision(imu_data)

        assert collision is True

    def test_detect_collision_at_threshold(self, imu_fusion):
        """Test collision detection at exact threshold."""
        accel = imu_fusion.collision_threshold / np.sqrt(3)
        imu_data = IMUData(
            accel_x=accel,
            accel_y=accel,
            accel_z=accel,
            gyro_x=0.0,
            gyro_y=0.0,
            gyro_z=0.0,
            timestamp=time.time()
        )

        collision = imu_fusion.detect_collision(imu_data)

        assert isinstance(collision, bool)

    def test_angular_velocity_captured(self, imu_fusion, sample_odom_pose, sample_imu_data):
        """Test that angular velocity is captured in fused pose."""
        fused_pose = imu_fusion.fuse(sample_odom_pose, sample_imu_data)

        assert fused_pose.angular_velocity == sample_imu_data.gyro_z

    def test_dataclasses(self):
        """Test dataclass creation."""
        imu_data = IMUData(
            accel_x=1.0,
            accel_y=2.0,
            accel_z=9.81,
            gyro_x=0.1,
            gyro_y=0.2,
            gyro_z=0.3,
            timestamp=123.456
        )
        assert imu_data.accel_x == 1.0
        assert imu_data.gyro_z == 0.3

        fused_pose = FusedPose(
            x=1.0,
            y=2.0,
            theta=0.5,
            linear_velocity=0.8,
            angular_velocity=0.2
        )
        assert fused_pose.x == 1.0
        assert fused_pose.theta == 0.5
        assert fused_pose.linear_velocity == 0.8

    def test_multiple_fusions(self, imu_fusion, sample_odom_pose):
        """Test multiple sequential fusions."""
        for i in range(10):
            imu_data = IMUData(
                accel_x=0.0,
                accel_y=0.0,
                accel_z=9.81,
                gyro_x=0.0,
                gyro_y=0.0,
                gyro_z=0.1,
                timestamp=time.time() + i * 0.02
            )
            fused_pose = imu_fusion.fuse(sample_odom_pose, imu_data)

        assert isinstance(fused_pose, FusedPose)
