"""Distance keeper for maintaining following distance from target person.

This module ensures the robot maintains a safe following distance with smooth
acceleration and deceleration.
"""

from dataclasses import dataclass, field
from typing import Optional
import time
import logging
import math

from .motion_controller import VelocityCommand, TargetPosition

logger = logging.getLogger(__name__)


@dataclass
class DistanceKeeperConfig:
    """Configuration for distance keeper."""

    target_distance: float = 2.0  # meters
    distance_tolerance: float = 0.3  # meters
    emergency_distance: float = 0.5  # meters
    max_acceleration: float = 0.5  # m/s²
    max_linear_velocity: float = 0.8  # m/s


@dataclass
class DistanceState:
    """State for distance keeping."""

    current_velocity: float = 0.0  # m/s
    last_update_time: float = field(default_factory=time.time)
    emergency_stop_triggered: bool = False


class DistanceKeeper:
    """Maintains safe following distance from target person."""

    def __init__(self, config: Optional[DistanceKeeperConfig] = None):
        """Initialize distance keeper.

        Args:
            config: Distance keeper configuration
        """
        self.config = config or DistanceKeeperConfig()
        self.state = DistanceState()

        logger.info(
            f"DistanceKeeper initialized: "
            f"target={self.config.target_distance}m, "
            f"tolerance={self.config.distance_tolerance}m, "
            f"emergency={self.config.emergency_distance}m"
        )

    def compute_desired_velocity(
        self, target: TargetPosition
    ) -> tuple[float, bool]:
        """Compute desired linear velocity based on distance to target.

        Args:
            target: Target person position

        Returns:
            Tuple of (desired_velocity, emergency_stop_flag)
        """
        distance = target.distance
        current_time = time.time()
        dt = current_time - self.state.last_update_time
        self.state.last_update_time = current_time

        # Check for emergency stop condition
        if distance < self.config.emergency_distance:
            logger.warning(
                f"EMERGENCY STOP: Distance {distance:.2f}m < "
                f"{self.config.emergency_distance}m"
            )
            self.state.emergency_stop_triggered = True
            self.state.current_velocity = 0.0
            return 0.0, True

        self.state.emergency_stop_triggered = False

        # Compute distance error
        distance_error = distance - self.config.target_distance

        # Determine desired velocity based on distance zones
        if distance < self.config.target_distance - self.config.distance_tolerance:
            # Too close (< 1.7m): slow down or stop
            desired_velocity = 0.0
            logger.debug(f"Too close ({distance:.2f}m): stopping")

        elif distance > self.config.target_distance + self.config.distance_tolerance:
            # Too far (> 2.3m): speed up
            # Scale velocity based on distance error
            velocity_scale = min(
                1.0, distance_error / self.config.target_distance
            )
            desired_velocity = self.config.max_linear_velocity * velocity_scale
            logger.debug(
                f"Too far ({distance:.2f}m): speeding up to "
                f"{desired_velocity:.2f} m/s"
            )

        else:
            # Within tolerance (1.7m - 2.3m): maintain moderate speed
            desired_velocity = self.config.max_linear_velocity * 0.5
            logger.debug(
                f"In range ({distance:.2f}m): maintaining "
                f"{desired_velocity:.2f} m/s"
            )

        # Apply smooth acceleration/deceleration
        if dt > 0:
            desired_velocity = self._apply_acceleration_limit(
                desired_velocity, dt
            )

        return desired_velocity, False

    def _apply_acceleration_limit(
        self, desired_velocity: float, dt: float
    ) -> float:
        """Apply acceleration limits for smooth motion.

        Args:
            desired_velocity: Desired velocity (m/s)
            dt: Time step (seconds)

        Returns:
            Velocity with acceleration limit applied
        """
        if dt <= 0:
            return desired_velocity

        # Compute velocity change
        velocity_change = desired_velocity - self.state.current_velocity

        # Limit acceleration
        max_velocity_change = self.config.max_acceleration * dt
        if abs(velocity_change) > max_velocity_change:
            velocity_change = (
                max_velocity_change
                if velocity_change > 0
                else -max_velocity_change
            )

        # Update current velocity
        new_velocity = self.state.current_velocity + velocity_change
        self.state.current_velocity = new_velocity

        return new_velocity

    def adjust_velocity_command(
        self, cmd: VelocityCommand, target: TargetPosition
    ) -> tuple[VelocityCommand, bool]:
        """Adjust velocity command based on distance to target.

        Args:
            cmd: Original velocity command
            target: Target person position

        Returns:
            Tuple of (adjusted_command, emergency_stop_flag)
        """
        desired_velocity, emergency_stop = self.compute_desired_velocity(
            target
        )

        if emergency_stop:
            # Override with emergency stop
            cmd.linear_x = 0.0
            cmd.angular_z = 0.0
            return cmd, True

        # Scale linear velocity based on desired velocity
        if cmd.linear_x > 0:
            # Forward motion: apply distance-based scaling
            velocity_scale = min(
                1.0, desired_velocity / self.config.max_linear_velocity
            )
            cmd.linear_x *= velocity_scale

        # Reduce angular velocity when too close for safety
        if target.distance < self.config.target_distance:
            angular_scale = max(
                0.3,
                (target.distance - self.config.emergency_distance)
                / (
                    self.config.target_distance
                    - self.config.emergency_distance
                ),
            )
            cmd.angular_z *= angular_scale

        logger.debug(
            f"Adjusted command: linear={cmd.linear_x:.3f} m/s, "
            f"angular={cmd.angular_z:.3f} rad/s "
            f"(distance={target.distance:.2f}m)"
        )

        return cmd, False

    def reset(self) -> None:
        """Reset distance keeper state."""
        self.state = DistanceState()
        logger.info("DistanceKeeper reset")

    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is currently active.

        Returns:
            True if emergency stop is triggered
        """
        return self.state.emergency_stop_triggered
