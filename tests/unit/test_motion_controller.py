"""Unit tests for motion_controller module.

Tests the PID-based motion control functionality.
"""

import pytest
import time
from unittest.mock import Mock
from src.control.motion_controller import (
    MotionController,
    PIDState,
    VelocityCommand,
    RobotPose,
    TargetPosition
)


class TestPIDState:
    """Test PIDState dataclass."""

    def test_pid_state_creation(self):
        """Test creating a PIDState object."""
        pid = PIDState(kp=0.5, ki=0.01, kd=0.1)
        assert pid.kp == 0.5
        assert pid.ki == 0.01
        assert pid.kd == 0.1
        assert pid.integral == 0.0
        assert pid.prev_error == 0.0

    def test_pid_state_reset(self):
        """Test resetting PID state."""
        pid = PIDState(kp=0.5, ki=0.01, kd=0.1)
        pid.integral = 5.0
        pid.prev_error = 2.0

        pid.reset()

        assert pid.integral == 0.0
        assert pid.prev_error == 0.0


class TestVelocityCommand:
    """Test VelocityCommand dataclass."""

    def test_velocity_command_creation(self):
        """Test creating a VelocityCommand object."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2)
        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 0.2
        assert cmd.timestamp > 0

    def test_velocity_command_clamp_within_limits(self):
        """Test clamping velocities within limits."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.3)
        cmd.clamp(max_linear=0.8, max_angular=1.0)

        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 0.3

    def test_velocity_command_clamp_exceeds_linear(self):
        """Test clamping when linear velocity exceeds limit."""
        cmd = VelocityCommand(linear_x=1.5, angular_z=0.3)
        cmd.clamp(max_linear=0.8, max_angular=1.0)

        assert cmd.linear_x == 0.8
        assert cmd.angular_z == 0.3

    def test_velocity_command_clamp_exceeds_angular(self):
        """Test clamping when angular velocity exceeds limit."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=1.5)
        cmd.clamp(max_linear=0.8, max_angular=1.0)

        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 1.0

    def test_velocity_command_clamp_negative_values(self):
        """Test clamping with negative velocities."""
        cmd = VelocityCommand(linear_x=-1.5, angular_z=-1.5)
        cmd.clamp(max_linear=0.8, max_angular=1.0)

        assert cmd.linear_x == -0.8
        assert cmd.angular_z == -1.0


class TestRobotPose:
    """Test RobotPose dataclass."""

    def test_robot_pose_creation(self):
        """Test creating a RobotPose object."""
        pose = RobotPose(x=1.0, y=2.0, theta=0.5)
        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.theta == 0.5
        assert pose.timestamp > 0


class TestTargetPosition:
    """Test TargetPosition dataclass."""

    def test_target_position_creation(self):
        """Test creating a TargetPosition object."""
        target = TargetPosition(x=3.0, y=4.0, distance=5.0, angle=0.6)
        assert target.x == 3.0
        assert target.y == 4.0
        assert target.distance == 5.0
        assert target.angle == 0.6
        assert target.timestamp > 0


class TestMotionController:
    """Test MotionController class."""

    def test_initialization_default_params(self):
        """Test controller initialization with default parameters."""
        controller = MotionController()

        assert controller.linear_pid.kp == 0.5
        assert controller.linear_pid.ki == 0.01
        assert controller.linear_pid.kd == 0.1
        assert controller.angular_pid.kp == 1.0
        assert controller.angular_pid.ki == 0.02
        assert controller.angular_pid.kd == 0.15
        assert controller.max_linear_velocity == 0.8
        assert controller.max_angular_velocity == 1.0

    def test_initialization_custom_params(self):
        """Test controller initialization with custom parameters."""
        controller = MotionController(
            linear_kp=1.0,
            linear_ki=0.05,
            linear_kd=0.2,
            angular_kp=2.0,
            angular_ki=0.1,
            angular_kd=0.3,
            max_linear_velocity=1.0,
            max_angular_velocity=1.5
        )

        assert controller.linear_pid.kp == 1.0
        assert controller.angular_pid.kp == 2.0
        assert controller.max_linear_velocity == 1.0
        assert controller.max_angular_velocity == 1.5

    def test_compute_pid_zero_dt(self):
        """Test PID computation with zero time step."""
        controller = MotionController()
        pid_state = PIDState(kp=1.0, ki=0.1, kd=0.1)

        output = controller.compute_pid(error=1.0, pid_state=pid_state, dt=0.0)

        assert output == 0.0

    def test_compute_pid_negative_dt(self):
        """Test PID computation with negative time step."""
        controller = MotionController()
        pid_state = PIDState(kp=1.0, ki=0.1, kd=0.1)

        output = controller.compute_pid(error=1.0, pid_state=pid_state, dt=-0.1)

        assert output == 0.0

    def test_compute_pid_proportional_term(self):
        """Test PID proportional term."""
        controller = MotionController()
        pid_state = PIDState(kp=2.0, ki=0.0, kd=0.0)

        output = controller.compute_pid(error=1.0, pid_state=pid_state, dt=0.1)

        # Should be purely proportional: kp * error = 2.0 * 1.0 = 2.0
        assert output == 2.0

    def test_compute_pid_integral_term(self):
        """Test PID integral term accumulation."""
        controller = MotionController()
        pid_state = PIDState(kp=0.0, ki=1.0, kd=0.0)

        # First call
        output1 = controller.compute_pid(error=1.0, pid_state=pid_state, dt=0.1)
        # integral = 1.0 * 0.1 = 0.1, output = 1.0 * 0.1 = 0.1
        assert abs(output1 - 0.1) < 0.001

        # Second call
        output2 = controller.compute_pid(error=1.0, pid_state=pid_state, dt=0.1)
        # integral = 0.1 + 1.0 * 0.1 = 0.2, output = 1.0 * 0.2 = 0.2
        assert abs(output2 - 0.2) < 0.001

    def test_compute_pid_derivative_term(self):
        """Test PID derivative term."""
        controller = MotionController()
        pid_state = PIDState(kp=0.0, ki=0.0, kd=1.0)
        pid_state.prev_error = 0.5

        output = controller.compute_pid(error=1.0, pid_state=pid_state, dt=0.1)

        # derivative = (1.0 - 0.5) / 0.1 = 5.0, output = 1.0 * 5.0 = 5.0
        assert abs(output - 5.0) < 0.001

    def test_compute_pid_anti_windup(self):
        """Test PID integral anti-windup."""
        controller = MotionController()
        pid_state = PIDState(kp=0.0, ki=1.0, kd=0.0)

        # Accumulate large integral
        for _ in range(200):
            controller.compute_pid(error=10.0, pid_state=pid_state, dt=0.1)

        # Integral should be clamped to 10.0
        assert pid_state.integral == 10.0

    def test_compute_velocity_command_target_too_far(self):
        """Test velocity command when target is too far."""
        controller = MotionController()
        target = TargetPosition(x=5.0, y=0.0, distance=3.0, angle=0.0)
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0)

        cmd = controller.compute_velocity_command(
            target=target,
            robot_pose=robot_pose,
            desired_distance=2.0
        )

        # Target is 3.0m away, desired is 2.0m, so error is +1.0
        # Should move forward
        assert cmd.linear_x > 0

    def test_compute_velocity_command_target_too_close(self):
        """Test velocity command when target is too close."""
        controller = MotionController()
        target = TargetPosition(x=1.0, y=0.0, distance=1.0, angle=0.0)
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0)

        cmd = controller.compute_velocity_command(
            target=target,
            robot_pose=robot_pose,
            desired_distance=2.0
        )

        # Target is 1.0m away, desired is 2.0m, so error is -1.0
        # Should move backward or stop
        assert cmd.linear_x < 0

    def test_compute_velocity_command_target_at_angle(self):
        """Test velocity command when target is at an angle."""
        controller = MotionController()
        target = TargetPosition(x=2.0, y=1.0, distance=2.0, angle=0.5)
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0)

        cmd = controller.compute_velocity_command(
            target=target,
            robot_pose=robot_pose,
            desired_distance=2.0
        )

        # Target is at angle 0.5 rad, should turn
        assert cmd.angular_z != 0

    def test_compute_velocity_command_clamping(self):
        """Test that velocity commands are clamped to limits."""
        controller = MotionController(
            linear_kp=10.0,  # High gain to exceed limits
            angular_kp=10.0,
            max_linear_velocity=0.8,
            max_angular_velocity=1.0
        )
        target = TargetPosition(x=10.0, y=5.0, distance=10.0, angle=1.5)
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0)

        cmd = controller.compute_velocity_command(
            target=target,
            robot_pose=robot_pose,
            desired_distance=2.0
        )

        # Velocities should be clamped
        assert abs(cmd.linear_x) <= 0.8
        assert abs(cmd.angular_z) <= 1.0

    def test_reset(self):
        """Test controller reset."""
        controller = MotionController()

        # Accumulate some state
        target = TargetPosition(x=5.0, y=0.0, distance=3.0, angle=0.5)
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0)
        controller.compute_velocity_command(target, robot_pose, 2.0)

        # Reset
        controller.reset()

        # State should be cleared
        assert controller.linear_pid.integral == 0.0
        assert controller.linear_pid.prev_error == 0.0
        assert controller.angular_pid.integral == 0.0
        assert controller.angular_pid.prev_error == 0.0

    def test_send_command_to_robot_success(self):
        """Test sending command to robot successfully."""
        controller = MotionController()
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2)

        mock_go2 = Mock()
        mock_go2.set_velocity.return_value = None

        result = controller.send_command_to_robot(cmd, mock_go2)

        assert result is True
        mock_go2.set_velocity.assert_called_once_with(0.5, 0.0, 0.2)

    def test_send_command_to_robot_failure(self):
        """Test handling failure when sending command to robot."""
        controller = MotionController()
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2)

        mock_go2 = Mock()
        mock_go2.set_velocity.side_effect = Exception("Connection lost")

        result = controller.send_command_to_robot(cmd, mock_go2)

        assert result is False

    def test_control_frequency(self):
        """Test that control period is calculated correctly."""
        controller = MotionController(control_frequency=50.0)
        assert abs(controller.control_period - 0.02) < 0.001

        controller = MotionController(control_frequency=100.0)
        assert abs(controller.control_period - 0.01) < 0.001
