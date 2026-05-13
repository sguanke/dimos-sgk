"""Unit tests for distance_keeper module.

Tests the distance keeping functionality for safe following.
"""

import pytest
import time
from src.control.distance_keeper import (
    DistanceKeeper,
    DistanceKeeperConfig,
    DistanceState
)
from src.control.motion_controller import VelocityCommand, TargetPosition


class TestDistanceKeeperConfig:
    """Test DistanceKeeperConfig dataclass."""

    def test_config_creation_defaults(self):
        """Test creating config with default values."""
        config = DistanceKeeperConfig()

        assert config.target_distance == 2.0
        assert config.distance_tolerance == 0.3
        assert config.emergency_distance == 0.5
        assert config.max_acceleration == 0.5
        assert config.max_linear_velocity == 0.8

    def test_config_creation_custom(self):
        """Test creating config with custom values."""
        config = DistanceKeeperConfig(
            target_distance=3.0,
            distance_tolerance=0.5,
            emergency_distance=1.0,
            max_acceleration=0.3,
            max_linear_velocity=1.0
        )

        assert config.target_distance == 3.0
        assert config.distance_tolerance == 0.5
        assert config.emergency_distance == 1.0


class TestDistanceState:
    """Test DistanceState dataclass."""

    def test_state_creation(self):
        """Test creating distance state."""
        state = DistanceState()

        assert state.current_velocity == 0.0
        assert state.last_update_time > 0
        assert not state.emergency_stop_triggered


class TestDistanceKeeper:
    """Test DistanceKeeper class."""

    def test_initialization_default_config(self):
        """Test initialization with default config."""
        keeper = DistanceKeeper()

        assert keeper.config.target_distance == 2.0
        assert keeper.state.current_velocity == 0.0

    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        config = DistanceKeeperConfig(target_distance=3.0)
        keeper = DistanceKeeper(config=config)

        assert keeper.config.target_distance == 3.0

    def test_compute_desired_velocity_emergency_stop(self):
        """Test emergency stop when target too close."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=0.3, y=0.0, distance=0.3, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        assert velocity == 0.0
        assert emergency is True
        assert keeper.state.emergency_stop_triggered

    def test_compute_desired_velocity_too_close(self):
        """Test velocity when target is too close (but not emergency)."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=1.5, y=0.0, distance=1.5, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        assert velocity == 0.0
        assert emergency is False

    def test_compute_desired_velocity_too_far(self):
        """Test velocity when target is too far."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        assert velocity > 0
        assert emergency is False

    def test_compute_desired_velocity_in_range(self):
        """Test velocity when target is in acceptable range."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=2.0, y=0.0, distance=2.0, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        assert velocity > 0
        assert emergency is False

    def test_compute_desired_velocity_at_emergency_threshold(self):
        """Test velocity at exact emergency threshold."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=0.5, y=0.0, distance=0.5, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        # At threshold, should not trigger emergency
        assert emergency is False

    def test_compute_desired_velocity_below_emergency_threshold(self):
        """Test velocity just below emergency threshold."""
        keeper = DistanceKeeper()
        target = TargetPosition(x=0.49, y=0.0, distance=0.49, angle=0.0)

        velocity, emergency = keeper.compute_desired_velocity(target)

        assert emergency is True

    def test_apply_acceleration_limit_zero_dt(self):
        """Test acceleration limiting with zero time step."""
        keeper = DistanceKeeper()

        velocity = keeper._apply_acceleration_limit(1.0, 0.0)

        assert velocity == 1.0

    def test_apply_acceleration_limit_negative_dt(self):
        """Test acceleration limiting with negative time step."""
        keeper = DistanceKeeper()

        velocity = keeper._apply_acceleration_limit(1.0, -0.1)

        assert velocity == 1.0

    def test_apply_acceleration_limit_smooth_acceleration(self):
        """Test smooth acceleration."""
        keeper = DistanceKeeper()
        keeper.state.current_velocity = 0.0

        # Try to accelerate to 0.8 m/s in 0.1s
        # Max change = 0.5 * 0.1 = 0.05 m/s
        velocity = keeper._apply_acceleration_limit(0.8, 0.1)

        assert velocity == 0.05
        assert keeper.state.current_velocity == 0.05

    def test_apply_acceleration_limit_smooth_deceleration(self):
        """Test smooth deceleration."""
        keeper = DistanceKeeper()
        keeper.state.current_velocity = 0.8

        # Try to decelerate to 0.0 m/s in 0.1s
        # Max change = 0.5 * 0.1 = 0.05 m/s
        velocity = keeper._apply_acceleration_limit(0.0, 0.1)

        assert velocity == 0.75
        assert keeper.state.current_velocity == 0.75

    def test_apply_acceleration_limit_within_limit(self):
        """Test acceleration within limit."""
        keeper = DistanceKeeper()
        keeper.state.current_velocity = 0.5

        # Small change within limit
        velocity = keeper._apply_acceleration_limit(0.52, 0.1)

        assert velocity == 0.52

    def test_adjust_velocity_command_emergency(self):
        """Test adjusting command during emergency."""
        keeper = DistanceKeeper()
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.3)
        target = TargetPosition(x=0.3, y=0.0, distance=0.3, angle=0.0)

        adjusted_cmd, emergency = keeper.adjust_velocity_command(cmd, target)

        assert adjusted_cmd.linear_x == 0.0
        assert adjusted_cmd.angular_z == 0.0
        assert emergency is True

    def test_adjust_velocity_command_forward_motion(self):
        """Test adjusting forward motion command."""
        keeper = DistanceKeeper()
        cmd = VelocityCommand(linear_x=0.8, angular_z=0.0)
        target = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.0)

        adjusted_cmd, emergency = keeper.adjust_velocity_command(cmd, target)

        # Command should be scaled based on distance
        assert adjusted_cmd.linear_x <= 0.8
        assert emergency is False

    def test_adjust_velocity_command_backward_motion(self):
        """Test that backward motion is not scaled."""
        keeper = DistanceKeeper()
        cmd = VelocityCommand(linear_x=-0.5, angular_z=0.0)
        target = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.0)

        adjusted_cmd, emergency = keeper.adjust_velocity_command(cmd, target)

        # Backward motion should not be scaled
        assert adjusted_cmd.linear_x == -0.5

    def test_adjust_velocity_command_angular_scaling_close(self):
        """Test angular velocity scaling when close to target."""
        keeper = DistanceKeeper()
        cmd = VelocityCommand(linear_x=0.5, angular_z=1.0)
        target = TargetPosition(x=1.0, y=0.0, distance=1.0, angle=0.5)

        adjusted_cmd, emergency = keeper.adjust_velocity_command(cmd, target)

        # Angular velocity should be reduced when close
        assert adjusted_cmd.angular_z < 1.0

    def test_adjust_velocity_command_angular_scaling_far(self):
        """Test angular velocity not scaled when far from target."""
        keeper = DistanceKeeper()
        cmd = VelocityCommand(linear_x=0.5, angular_z=1.0)
        target = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.5)

        adjusted_cmd, emergency = keeper.adjust_velocity_command(cmd, target)

        # Angular velocity should not be reduced when far
        assert adjusted_cmd.angular_z == 1.0

    def test_reset(self):
        """Test resetting distance keeper state."""
        keeper = DistanceKeeper()

        # Modify state
        keeper.state.current_velocity = 0.5
        keeper.state.emergency_stop_triggered = True

        keeper.reset()

        assert keeper.state.current_velocity == 0.0
        assert not keeper.state.emergency_stop_triggered

    def test_is_emergency_stop_active(self):
        """Test checking emergency stop status."""
        keeper = DistanceKeeper()

        assert not keeper.is_emergency_stop_active()

        # Trigger emergency
        target = TargetPosition(x=0.3, y=0.0, distance=0.3, angle=0.0)
        keeper.compute_desired_velocity(target)

        assert keeper.is_emergency_stop_active()

    def test_velocity_scaling_proportional_to_distance(self):
        """Test that velocity scales proportionally with distance error."""
        keeper = DistanceKeeper()

        # Far target
        target_far = TargetPosition(x=5.0, y=0.0, distance=5.0, angle=0.0)
        velocity_far, _ = keeper.compute_desired_velocity(target_far)

        keeper.reset()

        # Medium distance target
        target_medium = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.0)
        velocity_medium, _ = keeper.compute_desired_velocity(target_medium)

        # Farther target should have higher velocity
        assert velocity_far >= velocity_medium

    def test_multiple_updates_smooth_velocity(self):
        """Test that multiple updates produce smooth velocity changes."""
        keeper = DistanceKeeper()

        velocities = []
        for i in range(10):
            target = TargetPosition(x=3.0, y=0.0, distance=3.0, angle=0.0)
            velocity, _ = keeper.compute_desired_velocity(target)
            velocities.append(velocity)
            time.sleep(0.01)

        # Velocity should increase smoothly
        for i in range(1, len(velocities)):
            # Each step should not exceed max acceleration
            velocity_change = abs(velocities[i] - velocities[i-1])
            assert velocity_change <= keeper.config.max_acceleration * 0.02  # 0.01s * 2 for margin
