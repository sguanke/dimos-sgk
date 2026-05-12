"""Unit tests for motion_controller module."""

import pytest
import time
from unittest.mock import Mock, patch, mock_open

from src.control.motion_controller import (
    MotionController, PIDState, VelocityCommand,
    TargetPosition, RobotPose
)


@pytest.fixture
def mock_config():
    """Mock configuration data."""
    return {
        'go2': {
            'max_linear_velocity': 0.8,
            'max_angular_velocity': 1.0,
            'max_acceleration': 0.5,
            'control_frequency': 50
        },
        'pid': {
            'linear': {'kp': 0.5, 'ki': 0.01, 'kd': 0.1},
            'angular': {'kp': 1.0, 'ki': 0.02, 'kd': 0.15}
        }
    }


@pytest.fixture
def controller(mock_config):
    """Create MotionController with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                return MotionController()


class TestMotionController:
    """Test MotionController class."""

    def test_initialization(self, controller):
        """Test controller initialization."""
        assert controller.max_linear == 0.8
        assert controller.max_angular == 1.0
        assert controller.max_accel == 0.5
        assert controller.linear_pid.kp == 0.5
        assert controller.angular_pid.kp == 1.0

    def test_compute_velocity_basic(self, controller):
        """Test basic velocity computation."""
        target = TargetPosition(distance=2.0, angle=0.0, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command = controller.compute_velocity(target, robot_pose)

        assert isinstance(command, VelocityCommand)
        assert -controller.max_linear <= command.linear_x <= controller.max_linear
        assert -controller.max_angular <= command.angular_z <= controller.max_angular

    def test_compute_velocity_forward_target(self, controller):
        """Test velocity for target straight ahead."""
        target = TargetPosition(distance=3.0, angle=0.0, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command = controller.compute_velocity(target, robot_pose)

        assert command.linear_x > 0

    def test_compute_velocity_left_target(self, controller):
        """Test velocity for target to the left."""
        target = TargetPosition(distance=2.0, angle=-0.5, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command = controller.compute_velocity(target, robot_pose)

        assert command.angular_z < 0

    def test_compute_velocity_right_target(self, controller):
        """Test velocity for target to the right."""
        target = TargetPosition(distance=2.0, angle=0.5, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command = controller.compute_velocity(target, robot_pose)

        assert command.angular_z > 0

    def test_velocity_limits_respected(self, controller):
        """Test that velocity limits are respected."""
        target = TargetPosition(distance=100.0, angle=3.0, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command = controller.compute_velocity(target, robot_pose)

        assert abs(command.linear_x) <= controller.max_linear
        assert abs(command.angular_z) <= controller.max_angular

    def test_velocity_ramping(self, controller):
        """Test velocity ramping for smooth acceleration."""
        target = TargetPosition(distance=5.0, angle=0.0, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        command1 = controller.compute_velocity(target, robot_pose)
        time.sleep(0.02)
        command2 = controller.compute_velocity(target, robot_pose)

        delta = abs(command2.linear_x - command1.linear_x)
        max_delta = controller.max_accel * 0.02
        assert delta <= max_delta * 1.1

    def test_pid_update(self, controller):
        """Test PID controller update."""
        pid = PIDState(kp=1.0, ki=0.1, kd=0.05)
        error = 2.0
        current_time = time.time()

        output = controller._pid_update(pid, error, current_time)

        assert output != 0
        assert pid.prev_error == error

    def test_pid_integral_anti_windup(self, controller):
        """Test PID integral anti-windup."""
        pid = PIDState(kp=0.5, ki=0.1, kd=0.05)

        for _ in range(100):
            controller._pid_update(pid, 10.0, time.time())

        assert -10.0 <= pid.integral <= 10.0

    def test_clamp(self, controller):
        """Test value clamping."""
        assert controller._clamp(5.0, 0.0, 10.0) == 5.0
        assert controller._clamp(-5.0, 0.0, 10.0) == 0.0
        assert controller._clamp(15.0, 0.0, 10.0) == 10.0

    def test_reset(self, controller):
        """Test controller reset."""
        target = TargetPosition(distance=2.0, angle=0.5, timestamp=time.time())
        robot_pose = RobotPose(x=0.0, y=0.0, theta=0.0, timestamp=time.time())

        controller.compute_velocity(target, robot_pose)

        controller.reset()

        assert controller.linear_pid.integral == 0.0
        assert controller.linear_pid.prev_error == 0.0
        assert controller.angular_pid.integral == 0.0
        assert controller.angular_pid.prev_error == 0.0
        assert controller.prev_command.linear_x == 0.0
        assert controller.prev_command.angular_z == 0.0

    def test_stop(self, controller):
        """Test stop command generation."""
        command = controller.stop()

        assert command.linear_x == 0.0
        assert command.angular_z == 0.0

    def test_ramp_velocity_no_change(self, controller):
        """Test velocity ramping with no change needed."""
        ramped = controller._ramp_velocity(0.5, 0.5, time.time())
        assert ramped == 0.5

    def test_ramp_velocity_increase(self, controller):
        """Test velocity ramping with increase."""
        controller.prev_command = VelocityCommand(0.0, 0.0, time.time() - 0.02)
        ramped = controller._ramp_velocity(0.0, 0.5, time.time())

        assert 0.0 <= ramped <= 0.5

    def test_ramp_velocity_decrease(self, controller):
        """Test velocity ramping with decrease."""
        controller.prev_command = VelocityCommand(0.5, 0.0, time.time() - 0.02)
        ramped = controller._ramp_velocity(0.5, 0.0, time.time())

        assert 0.0 <= ramped <= 0.5

    def test_default_config(self, controller):
        """Test default configuration loading."""
        config = controller._default_config()

        assert 'go2' in config
        assert 'pid' in config
        assert config['go2']['max_linear_velocity'] == 0.8

    def test_dataclasses(self):
        """Test dataclass creation."""
        pid = PIDState(kp=1.0, ki=0.1, kd=0.05)
        assert pid.kp == 1.0
        assert pid.integral == 0.0

        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2)
        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 0.2

        target = TargetPosition(distance=2.0, angle=0.5, timestamp=time.time())
        assert target.distance == 2.0

        pose = RobotPose(x=1.0, y=2.0, theta=0.5, timestamp=time.time())
        assert pose.x == 1.0
