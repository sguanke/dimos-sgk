"""PID-based motion controller for Go2 robot.

This module implements a PID controller for linear and angular velocity control,
sending commands to the Go2 robot at 50Hz.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
import time
import logging
import math

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

    def reset(self) -> None:
        """Reset PID state."""
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = time.time()


@dataclass
class VelocityCommand:
    """Robot velocity command."""

    linear_x: float  # m/s
    angular_z: float  # rad/s
    timestamp: float = field(default_factory=time.time)

    def clamp(self, max_linear: float, max_angular: float) -> None:
        """Clamp velocities to maximum values."""
        self.linear_x = max(-max_linear, min(max_linear, self.linear_x))
        self.angular_z = max(-max_angular, min(max_angular, self.angular_z))


@dataclass
class RobotPose:
    """Robot pose in world frame."""

    x: float  # meters
    y: float  # meters
    theta: float  # radians
    timestamp: float = field(default_factory=time.time)


@dataclass
class TargetPosition:
    """Target person position."""

    x: float  # meters
    y: float  # meters
    distance: float  # meters from robot
    angle: float  # radians relative to robot heading
    timestamp: float = field(default_factory=time.time)


class MotionController:
    """PID-based motion controller for Go2 robot."""

    def __init__(
        self,
        linear_kp: float = 0.5,
        linear_ki: float = 0.01,
        linear_kd: float = 0.1,
        angular_kp: float = 1.0,
        angular_ki: float = 0.02,
        angular_kd: float = 0.15,
        max_linear_velocity: float = 0.8,
        max_angular_velocity: float = 1.0,
        control_frequency: float = 50.0,
    ):
        """Initialize motion controller.

        Args:
            linear_kp: Linear velocity proportional gain
            linear_ki: Linear velocity integral gain
            linear_kd: Linear velocity derivative gain
            angular_kp: Angular velocity proportional gain
            angular_ki: Angular velocity integral gain
            angular_kd: Angular velocity derivative gain
            max_linear_velocity: Maximum linear velocity (m/s)
            max_angular_velocity: Maximum angular velocity (rad/s)
            control_frequency: Control loop frequency (Hz)
        """
        self.linear_pid = PIDState(kp=linear_kp, ki=linear_ki, kd=linear_kd)
        self.angular_pid = PIDState(kp=angular_kp, ki=angular_ki, kd=angular_kd)
        self.max_linear_velocity = max_linear_velocity
        self.max_angular_velocity = max_angular_velocity
        self.control_period = 1.0 / control_frequency

        logger.info(
            f"MotionController initialized: "
            f"linear PID=({linear_kp}, {linear_ki}, {linear_kd}), "
            f"angular PID=({angular_kp}, {angular_ki}, {angular_kd})"
        )

    def compute_pid(
        self, error: float, pid_state: PIDState, dt: float
    ) -> float:
        """Compute PID control output.

        Args:
            error: Current error value
            pid_state: PID controller state
            dt: Time step (seconds)

        Returns:
            Control output
        """
        if dt <= 0:
            return 0.0

        # Proportional term
        p_term = pid_state.kp * error

        # Integral term with anti-windup
        pid_state.integral += error * dt
        pid_state.integral = max(-10.0, min(10.0, pid_state.integral))
        i_term = pid_state.ki * pid_state.integral

        # Derivative term
        d_term = pid_state.kd * (error - pid_state.prev_error) / dt

        # Update state
        pid_state.prev_error = error

        return p_term + i_term + d_term

    def compute_velocity_command(
        self,
        target: TargetPosition,
        robot_pose: RobotPose,
        desired_distance: float,
    ) -> VelocityCommand:
        """Compute velocity command to reach target.

        Args:
            target: Target person position
            robot_pose: Current robot pose
            desired_distance: Desired following distance (meters)

        Returns:
            Velocity command
        """
        current_time = time.time()

        # Compute time step
        dt_linear = current_time - self.linear_pid.prev_time
        dt_angular = current_time - self.angular_pid.prev_time

        # Update time
        self.linear_pid.prev_time = current_time
        self.angular_pid.prev_time = current_time

        # Distance error (positive = too far, negative = too close)
        distance_error = target.distance - desired_distance

        # Angular error (angle to target)
        angular_error = target.angle

        # Compute PID outputs
        linear_velocity = self.compute_pid(
            distance_error, self.linear_pid, dt_linear
        )
        angular_velocity = self.compute_pid(
            angular_error, self.angular_pid, dt_angular
        )

        # Create command and clamp
        cmd = VelocityCommand(
            linear_x=linear_velocity,
            angular_z=angular_velocity,
        )
        cmd.clamp(self.max_linear_velocity, self.max_angular_velocity)

        logger.debug(
            f"Motion command: linear={cmd.linear_x:.3f} m/s, "
            f"angular={cmd.angular_z:.3f} rad/s "
            f"(distance_error={distance_error:.3f}m, "
            f"angular_error={math.degrees(angular_error):.1f}°)"
        )

        return cmd

    def reset(self) -> None:
        """Reset controller state."""
        self.linear_pid.reset()
        self.angular_pid.reset()
        logger.info("MotionController reset")

    def send_command_to_robot(
        self, cmd: VelocityCommand, go2_sdk_client
    ) -> bool:
        """Send velocity command to Go2 robot.

        Args:
            cmd: Velocity command
            go2_sdk_client: Go2 SDK client instance

        Returns:
            True if command sent successfully
        """
        try:
            # Send command via Go2 SDK
            go2_sdk_client.set_velocity(cmd.linear_x, 0.0, cmd.angular_z)
            return True
        except Exception as e:
            logger.error(f"Failed to send command to robot: {e}")
            return False
