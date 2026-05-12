"""Unit tests for odometry module."""

import pytest
import time
import numpy as np

from src.localization.odometry import WheelOdometry, Pose2D, WheelEncoderData


@pytest.fixture
def odometry():
    """Create WheelOdometry instance."""
    return WheelOdometry(
        wheel_base=0.3,
        ticks_per_meter=1000.0,
        publish_rate=50.0
    )


class TestWheelOdometry:
    """Test WheelOdometry class."""

    def test_initialization(self, odometry):
        """Test odometry initialization."""
        assert odometry.wheel_base == 0.3
        assert odometry.ticks_per_meter == 1000.0
        assert odometry.publish_rate == 50.0
        assert odometry.pose.x == 0.0
        assert odometry.pose.y == 0.0
        assert odometry.pose.theta == 0.0

    def test_update_first_call(self, odometry):
        """Test first update initializes previous ticks."""
        encoder_data = WheelEncoderData(
            left_ticks=1000,
            right_ticks=1000,
            timestamp=time.time()
        )

        pose = odometry.update(encoder_data)

        assert pose.x == 0.0
        assert pose.y == 0.0
        assert pose.theta == 0.0

    def test_update_straight_motion(self, odometry):
        """Test odometry update for straight motion."""
        encoder_data1 = WheelEncoderData(0, 0, time.time())
        odometry.update(encoder_data1)

        encoder_data2 = WheelEncoderData(1000, 1000, time.time())
        pose = odometry.update(encoder_data2)

        assert pose.x > 0
        assert abs(pose.y) < 0.01
        assert abs(pose.theta) < 0.01

    def test_update_turn_left(self, odometry):
        """Test odometry update for left turn."""
        encoder_data1 = WheelEncoderData(0, 0, time.time())
        odometry.update(encoder_data1)

        encoder_data2 = WheelEncoderData(500, 1500, time.time())
        pose = odometry.update(encoder_data2)

        assert pose.theta > 0

    def test_update_turn_right(self, odometry):
        """Test odometry update for right turn."""
        encoder_data1 = WheelEncoderData(0, 0, time.time())
        odometry.update(encoder_data1)

        encoder_data2 = WheelEncoderData(1500, 500, time.time())
        pose = odometry.update(encoder_data2)

        assert pose.theta < 0

    def test_compute_pose_change_straight(self, odometry):
        """Test pose change computation for straight motion."""
        dx, dy, dtheta = odometry._compute_pose_change(1.0, 1.0)

        assert dx == 1.0
        assert dy == 0.0
        assert dtheta == 0.0

    def test_compute_pose_change_arc(self, odometry):
        """Test pose change computation for arc motion."""
        dx, dy, dtheta = odometry._compute_pose_change(0.5, 1.5)

        assert dx > 0
        assert dtheta != 0.0

    def test_integrate_pose_change(self, odometry):
        """Test pose integration into world frame."""
        odometry.pose = Pose2D(x=1.0, y=1.0, theta=np.pi/4)

        new_pose = odometry._integrate_pose_change(1.0, 0.0, 0.0)

        assert new_pose.x > 1.0
        assert new_pose.y > 1.0

    def test_normalize_angle(self, odometry):
        """Test angle normalization."""
        assert abs(odometry._normalize_angle(0.0)) < 0.01
        assert abs(odometry._normalize_angle(np.pi)) - np.pi < 0.01
        assert abs(odometry._normalize_angle(-np.pi)) - np.pi < 0.01

        normalized = odometry._normalize_angle(3 * np.pi)
        assert -np.pi <= normalized <= np.pi

        normalized = odometry._normalize_angle(-3 * np.pi)
        assert -np.pi <= normalized <= np.pi

    def test_reset_to_origin(self, odometry):
        """Test reset to origin."""
        encoder_data1 = WheelEncoderData(0, 0, time.time())
        odometry.update(encoder_data1)
        encoder_data2 = WheelEncoderData(1000, 1000, time.time())
        odometry.update(encoder_data2)

        odometry.reset()

        assert odometry.pose.x == 0.0
        assert odometry.pose.y == 0.0
        assert odometry.pose.theta == 0.0
        assert odometry._prev_left_ticks is None
        assert odometry._prev_right_ticks is None

    def test_reset_to_custom_pose(self, odometry):
        """Test reset to custom pose."""
        custom_pose = Pose2D(x=5.0, y=3.0, theta=np.pi/2)
        odometry.reset(custom_pose)

        assert odometry.pose.x == 5.0
        assert odometry.pose.y == 3.0
        assert odometry.pose.theta == np.pi/2

    def test_get_pose(self, odometry):
        """Test getting current pose."""
        pose = odometry.get_pose()

        assert isinstance(pose, Pose2D)
        assert pose.x == 0.0
        assert pose.y == 0.0

    def test_multiple_updates(self, odometry):
        """Test multiple sequential updates."""
        for i in range(10):
            encoder_data = WheelEncoderData(
                left_ticks=i * 100,
                right_ticks=i * 100,
                timestamp=time.time()
            )
            pose = odometry.update(encoder_data)

        assert pose.x > 0

    def test_backward_motion(self, odometry):
        """Test backward motion."""
        encoder_data1 = WheelEncoderData(1000, 1000, time.time())
        odometry.update(encoder_data1)

        encoder_data2 = WheelEncoderData(0, 0, time.time())
        pose = odometry.update(encoder_data2)

        assert pose.x < 0

    def test_dataclasses(self):
        """Test dataclass creation."""
        pose = Pose2D(x=1.0, y=2.0, theta=0.5)
        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.theta == 0.5

        encoder_data = WheelEncoderData(
            left_ticks=100,
            right_ticks=200,
            timestamp=123.456
        )
        assert encoder_data.left_ticks == 100
        assert encoder_data.right_ticks == 200
        assert encoder_data.timestamp == 123.456
