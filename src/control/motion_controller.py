"""PID-based motion controller for Go2 robot.

This module implements a PID controller for linear and angular velocity control,
sending commands to the Go2 robot at 50Hz.
"""

from dataclasses import dataclass, field
from typing import Tuple
import time
import logging
import yaml
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class PIDState:
    """State for a single PID controller."""
    kp: float
    ki: float
    kd: float
    integral: float = 0.0
    prev_error: float = 0.0
    prev_time: float = field(default_factory=time.time)


@dataclass
class VelocityCommand:
    """Robot velocity command."""
    linear_x: float  # m/s
    angular_z: float  # rad/s
    timestamp: float = field(default_factory=time.time)


@dataclass
class TargetPosition:
    """Target person position relative to robot."""
    distance: float  # meters
    angle: float  # radians
    timestamp: float


@dataclass
class RobotPose:
    """Robot pose in world frame."""
    x: float  # meters
    y: float  # meters
    theta: float  # radians
    timestamp: float


class MotionController:
    """PID-based motion controller for Go2 robot."""

    def __init__(self, config_path: str = "config/robot_params.yaml"):
        """Initialize motion controller.

        Args:
            config_path: Path to robot configuration file
        """
        self.config = self._load_config(config_path)

        # Initialize PID controllers
        linear_pid = self.config['pid']['linear']
        angular_pid = self.config['pid']['angular']

        self.linear_pid = PIDState(
            kp=linear_pid['kp'],
            ki=linear_pid['ki'],
            kd=linear_pid['kd']
        )

        self.angular_pid = PIDState(
            kp=angular_pid['kp'],
            ki=angular_pid['ki'],
            kd=angular_pid['kd']
        )

        # Velocity limits
        self.max_linear = self.config['go2']['max_linear_velocity']
        self.max_angular = self.config['go2']['max_angular_velocity']
        self.max_accel = self.config['go2']['max_acceleration']

        # Previous command for velocity ramping
        self.prev_command = VelocityCommand(0.0, 0.0)

        logger.info("Motion controller initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()

        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _default_config(self) -> dict:
        """Return default configuration."""
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

    def compute_velocity(
        self,
        target: TargetPosition,
        robot_pose: RobotPose
    ) -> VelocityCommand:
        """Compute velocity command using PID control.

        Args:
            target: Target person position relative to robot
            robot_pose: Current robot pose

        Returns:
            Velocity command for the robot
        """
        current_time = time.time()

        # Compute errors
        distance_error = target.distance
        angle_error = target.angle

        # Compute linear velocity using PID
        linear_vel = self._pid_update(
            self.linear_pid,
            distance_error,
            current_time
        )

        # Compute angular velocity using PID
        angular_vel = self._pid_update(
            self.angular_pid,
            angle_error,
            current_time
        )

        # Apply velocity limits
        linear_vel = self._clamp(linear_vel, -self.max_linear, self.max_linear)
        angular_vel = self._clamp(angular_vel, -self.max_angular, self.max_angular)

        # Apply velocity ramping for smooth acceleration
        linear_vel = self._ramp_velocity(
            self.prev_command.linear_x,
            linear_vel,
            current_time
        )
        angular_vel = self._ramp_velocity(
            self.prev_command.angular_z,
            angular_vel,
            current_time
        )

        # Create command
        command = VelocityCommand(linear_vel, angular_vel, current_time)
        self.prev_command = command

        logger.debug(
            f"Velocity command: linear={linear_vel:.2f} m/s, "
            f"angular={angular_vel:.2f} rad/s"
        )

        return command

    def _pid_update(
        self,
        pid: PIDState,
        error: float,
        current_time: float
    ) -> float:
        """Update PID controller and return control output.

        Args:
            pid: PID state
            error: Current error value
            current_time: Current timestamp

        Returns:
            Control output
        """
        dt = current_time - pid.prev_time
        if dt <= 0:
            dt = 0.02  # Default 50Hz

        # Proportional term
        p_term = pid.kp * error

        # Integral term with anti-windup
        pid.integral += error * dt
        pid.integral = self._clamp(pid.integral, -10.0, 10.0)
        i_term = pid.ki * pid.integral

        # Derivative term
        d_term = pid.kd * (error - pid.prev_error) / dt

        # Update state
        pid.prev_error = error
        pid.prev_time = current_time

        return p_term + i_term + d_term

    def _ramp_velocity(
        self,
        prev_vel: float,
        target_vel: float,
        current_time: float
    ) -> float:
        """Apply velocity ramping for smooth acceleration.

        Args:
            prev_vel: Previous velocity
            target_vel: Target velocity
            current_time: Current timestamp

        Returns:
            Ramped velocity
        """
        dt = current_time - self.prev_command.timestamp
        if dt <= 0:
            dt = 0.02  # Default 50Hz

        max_delta = self.max_accel * dt
        delta = target_vel - prev_vel

        if abs(delta) > max_delta:
            return prev_vel + max_delta * (1 if delta > 0 else -1)
        return target_vel

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max."""
        return max(min_val, min(max_val, value))

    def reset(self) -> None:
        """Reset PID controllers."""
        self.linear_pid.integral = 0.0
        self.linear_pid.prev_error = 0.0
        self.angular_pid.integral = 0.0
        self.angular_pid.prev_error = 0.0
        self.prev_command = VelocityCommand(0.0, 0.0)
        logger.info("Motion controller reset")

    def stop(self) -> VelocityCommand:
        """Generate stop command.

        Returns:
            Zero velocity command
        """
        command = VelocityCommand(0.0, 0.0)
        self.prev_command = command
        logger.info("Stop command generated")
        return command
