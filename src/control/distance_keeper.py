"""Distance keeper for maintaining following distance.

This module ensures the robot maintains a safe following distance from the target person,
with smooth acceleration/deceleration and emergency stop capability.
"""

from dataclasses import dataclass
from typing import Optional
import logging
import yaml
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class DistanceCommand:
    """Distance-based velocity command."""
    target_linear_velocity: float  # m/s
    should_stop: bool
    emergency_stop: bool
    reason: str


class DistanceKeeper:
    """Maintains safe following distance from target person."""

    def __init__(self, config_path: str = "config/robot_params.yaml"):
        """Initialize distance keeper.

        Args:
            config_path: Path to robot configuration file
        """
        self.config = self._load_config(config_path)

        # Following parameters
        self.target_distance = self.config['following']['target_distance']
        self.distance_tolerance = self.config['following']['distance_tolerance']
        self.emergency_distance = self.config['following']['emergency_distance']

        # Velocity limits
        self.max_linear = self.config['go2']['max_linear_velocity']
        self.max_accel = self.config['go2']['max_acceleration']

        # Distance thresholds
        self.min_distance = self.target_distance - self.distance_tolerance
        self.max_distance = self.target_distance + self.distance_tolerance

        logger.info(
            f"Distance keeper initialized: target={self.target_distance}m, "
            f"tolerance={self.distance_tolerance}m, "
            f"emergency={self.emergency_distance}m"
        )

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
                'max_acceleration': 0.5
            },
            'following': {
                'target_distance': 2.0,
                'distance_tolerance': 0.3,
                'emergency_distance': 0.5
            }
        }

    def compute_distance_command(
        self,
        current_distance: float
    ) -> DistanceCommand:
        """Compute velocity command based on distance to target.

        Args:
            current_distance: Current distance to target person (meters)

        Returns:
            Distance-based velocity command
        """
        # Emergency stop if too close
        if current_distance < self.emergency_distance:
            logger.warning(
                f"Emergency stop triggered: distance={current_distance:.2f}m "
                f"< {self.emergency_distance}m"
            )
            return DistanceCommand(
                target_linear_velocity=0.0,
                should_stop=True,
                emergency_stop=True,
                reason=f"Too close: {current_distance:.2f}m"
            )

        # Compute distance error
        distance_error = current_distance - self.target_distance

        # Within tolerance - maintain current speed
        if abs(distance_error) <= self.distance_tolerance:
            velocity = self._compute_maintain_velocity(distance_error)
            return DistanceCommand(
                target_linear_velocity=velocity,
                should_stop=False,
                emergency_stop=False,
                reason=f"Maintaining distance: {current_distance:.2f}m"
            )

        # Too close - slow down or stop
        if distance_error < 0:
            velocity = self._compute_slowdown_velocity(current_distance)
            should_stop = current_distance < self.min_distance
            return DistanceCommand(
                target_linear_velocity=velocity,
                should_stop=should_stop,
                emergency_stop=False,
                reason=f"Too close, slowing down: {current_distance:.2f}m"
            )

        # Too far - speed up
        velocity = self._compute_speedup_velocity(distance_error)
        return DistanceCommand(
            target_linear_velocity=velocity,
            should_stop=False,
            emergency_stop=False,
            reason=f"Too far, speeding up: {current_distance:.2f}m"
        )

    def _compute_maintain_velocity(self, distance_error: float) -> float:
        """Compute velocity to maintain current distance.

        Args:
            distance_error: Error from target distance (meters)

        Returns:
            Target linear velocity (m/s)
        """
        # Proportional control within tolerance band
        gain = 0.3
        velocity = gain * distance_error
        return self._clamp(velocity, 0.0, self.max_linear * 0.5)

    def _compute_slowdown_velocity(self, current_distance: float) -> float:
        """Compute velocity when too close to target.

        Args:
            current_distance: Current distance to target (meters)

        Returns:
            Target linear velocity (m/s)
        """
        # Linear interpolation from emergency distance to min distance
        if current_distance <= self.emergency_distance:
            return 0.0

        # Slow down proportionally
        distance_range = self.min_distance - self.emergency_distance
        distance_from_emergency = current_distance - self.emergency_distance

        velocity_ratio = distance_from_emergency / distance_range
        velocity = velocity_ratio * self.max_linear * 0.3

        return self._clamp(velocity, 0.0, self.max_linear * 0.3)

    def _compute_speedup_velocity(self, distance_error: float) -> float:
        """Compute velocity when too far from target.

        Args:
            distance_error: Positive error from target distance (meters)

        Returns:
            Target linear velocity (m/s)
        """
        # Proportional control with saturation
        gain = 0.4
        velocity = gain * distance_error
        return self._clamp(velocity, 0.0, self.max_linear)

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max."""
        return max(min_val, min(max_val, value))

    def is_safe_distance(self, distance: float) -> bool:
        """Check if distance is safe.

        Args:
            distance: Distance to target (meters)

        Returns:
            True if distance is safe, False otherwise
        """
        return distance >= self.emergency_distance

    def is_within_tolerance(self, distance: float) -> bool:
        """Check if distance is within tolerance.

        Args:
            distance: Distance to target (meters)

        Returns:
            True if within tolerance, False otherwise
        """
        return abs(distance - self.target_distance) <= self.distance_tolerance
