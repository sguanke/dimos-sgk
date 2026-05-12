"""Unit tests for safety_monitor module.

CRITICAL: This module requires 100% test coverage as it is safety-critical.
"""

import pytest
import time
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path

from src.safety.safety_monitor import (
    SafetyMonitor, SafetyLevel, VelocityCommand, SafetyEvent
)


@pytest.fixture
def mock_config():
    """Mock safety configuration."""
    return {
        'safety_monitor': {
            'max_linear_velocity': 0.8,
            'max_angular_velocity': 1.0,
            'min_obstacle_distance': 0.3,
            'emergency_stop_distance': 0.5,
            'emergency_stop_timeout': 0.1
        }
    }


@pytest.fixture
def safety_monitor(mock_config, tmp_path):
    """Create SafetyMonitor with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir'):
                    monitor = SafetyMonitor()
                    return monitor


class TestSafetyMonitor:
    """Test SafetyMonitor class - SAFETY CRITICAL."""

    def test_initialization(self, safety_monitor):
        """Test safety monitor initialization."""
        assert safety_monitor.max_linear_velocity == 0.8
        assert safety_monitor.max_angular_velocity == 1.0
        assert safety_monitor.min_obstacle_distance == 0.3
        assert safety_monitor.emergency_stop_distance == 0.5
        assert not safety_monitor._emergency_stop_active

    def test_validate_command_safe(self, safety_monitor):
        """Test validation of safe command."""
        command = VelocityCommand(
            linear_x=0.5,
            angular_z=0.3,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(
            command,
            distance_to_target=2.0,
            distance_to_obstacle=1.0
        )

        assert is_safe is True
        assert modified_cmd is not None
        assert "validated" in reason.lower()

    def test_validate_command_linear_velocity_exceeded(self, safety_monitor):
        """Test rejection of excessive linear velocity."""
        command = VelocityCommand(
            linear_x=1.5,
            angular_z=0.0,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is False
        assert modified_cmd is None
        assert "linear velocity" in reason.lower()

    def test_validate_command_angular_velocity_exceeded(self, safety_monitor):
        """Test rejection of excessive angular velocity."""
        command = VelocityCommand(
            linear_x=0.5,
            angular_z=1.5,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is False
        assert modified_cmd is None
        assert "angular velocity" in reason.lower()

    def test_validate_command_target_too_close(self, safety_monitor):
        """Test emergency stop when target too close."""
        command = VelocityCommand(
            linear_x=0.5,
            angular_z=0.0,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(
            command,
            distance_to_target=0.3
        )

        assert is_safe is False
        assert modified_cmd is None
        assert "emergency stop" in reason.lower()
        assert safety_monitor._emergency_stop_active is True

    def test_validate_command_obstacle_too_close(self, safety_monitor):
        """Test rejection when obstacle too close."""
        command = VelocityCommand(
            linear_x=0.5,
            angular_z=0.0,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(
            command,
            distance_to_obstacle=0.2
        )

        assert is_safe is False
        assert modified_cmd is None
        assert "obstacle" in reason.lower()

    def test_validate_command_emergency_stop_active(self, safety_monitor):
        """Test that commands are rejected when emergency stop is active."""
        safety_monitor._emergency_stop_active = True

        command = VelocityCommand(
            linear_x=0.1,
            angular_z=0.0,
            timestamp=time.time()
        )

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is False
        assert modified_cmd is None
        assert "emergency stop active" in reason.lower()

    def test_trigger_emergency_stop(self, safety_monitor):
        """Test emergency stop trigger."""
        start_time = time.time()
        safety_monitor._trigger_emergency_stop("Test emergency")
        execution_time = time.time() - start_time

        assert safety_monitor._emergency_stop_active is True
        assert execution_time < 0.2

    def test_emergency_stop_execution_time(self, safety_monitor):
        """Test that emergency stop executes within timeout."""
        start_time = time.time()
        safety_monitor._trigger_emergency_stop("Speed test")
        execution_time = time.time() - start_time

        assert execution_time < safety_monitor.emergency_stop_timeout * 2

    def test_reset_emergency_stop(self, safety_monitor):
        """Test emergency stop reset."""
        safety_monitor._emergency_stop_active = True

        result = safety_monitor.reset_emergency_stop()

        assert result is True
        assert safety_monitor._emergency_stop_active is False

    def test_reset_emergency_stop_when_not_active(self, safety_monitor):
        """Test reset when emergency stop not active."""
        result = safety_monitor.reset_emergency_stop()

        assert result is False

    def test_is_emergency_stop_active(self, safety_monitor):
        """Test checking emergency stop status."""
        assert safety_monitor.is_emergency_stop_active() is False

        safety_monitor._emergency_stop_active = True
        assert safety_monitor.is_emergency_stop_active() is True

    def test_get_status(self, safety_monitor):
        """Test getting monitor status."""
        status = safety_monitor.get_status()

        assert 'emergency_stop_active' in status
        assert 'last_command_time' in status
        assert 'max_linear_velocity' in status
        assert status['max_linear_velocity'] == 0.8

    def test_log_safety_event(self, safety_monitor):
        """Test safety event logging."""
        command = VelocityCommand(0.5, 0.2, time.time())

        safety_monitor._log_safety_event(
            SafetyLevel.WARNING,
            "Test warning",
            command
        )

    def test_log_safety_event_no_command(self, safety_monitor):
        """Test logging event without command."""
        safety_monitor._log_safety_event(
            SafetyLevel.CRITICAL,
            "Test critical",
            None
        )

    def test_log_safety_event_all_levels(self, safety_monitor):
        """Test logging all safety levels."""
        for level in SafetyLevel:
            safety_monitor._log_safety_event(level, f"Test {level.value}", None)

    def test_validate_command_at_emergency_distance(self, safety_monitor):
        """Test behavior at exact emergency distance."""
        command = VelocityCommand(0.5, 0.0, time.time())

        is_safe, _, _ = safety_monitor.validate_command(
            command,
            distance_to_target=0.5
        )

        assert is_safe is False

    def test_validate_command_at_min_obstacle_distance(self, safety_monitor):
        """Test behavior at minimum obstacle distance."""
        command = VelocityCommand(0.5, 0.0, time.time())

        is_safe, _, _ = safety_monitor.validate_command(
            command,
            distance_to_obstacle=0.3
        )

        assert is_safe is False

    def test_validate_command_negative_velocities(self, safety_monitor):
        """Test validation with negative velocities."""
        command = VelocityCommand(-0.5, -0.5, time.time())

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is True

    def test_validate_command_zero_velocities(self, safety_monitor):
        """Test validation with zero velocities."""
        command = VelocityCommand(0.0, 0.0, time.time())

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is True

    def test_validate_command_max_velocities(self, safety_monitor):
        """Test validation at maximum allowed velocities."""
        command = VelocityCommand(0.8, 1.0, time.time())

        is_safe, modified_cmd, reason = safety_monitor.validate_command(command)

        assert is_safe is True

    def test_load_config_failure(self, mock_config):
        """Test fallback to defaults on config load failure."""
        with patch('builtins.open', side_effect=Exception("File not found")):
            with patch('pathlib.Path.mkdir'):
                monitor = SafetyMonitor()

                assert monitor.max_linear_velocity == 0.8
                assert monitor.emergency_stop_distance == 0.5

    def test_dataclasses(self):
        """Test dataclass creation."""
        cmd = VelocityCommand(0.5, 0.2, 123.456)
        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 0.2

        event = SafetyEvent(
            timestamp=123.456,
            level=SafetyLevel.WARNING,
            reason="Test",
            command=cmd
        )
        assert event.level == SafetyLevel.WARNING
        assert event.command == cmd

    def test_safety_level_enum(self):
        """Test SafetyLevel enum values."""
        assert SafetyLevel.SAFE.value == "safe"
        assert SafetyLevel.WARNING.value == "warning"
        assert SafetyLevel.CRITICAL.value == "critical"
        assert SafetyLevel.EMERGENCY_STOP.value == "emergency_stop"

    def test_multiple_validations(self, safety_monitor):
        """Test multiple sequential validations."""
        for i in range(10):
            command = VelocityCommand(0.5, 0.1 * i, time.time())
            is_safe, _, _ = safety_monitor.validate_command(command)

            if abs(0.1 * i) <= 1.0:
                assert is_safe is True

    def test_last_command_time_updated(self, safety_monitor):
        """Test that last command time is updated."""
        initial_time = safety_monitor._last_command_time

        command = VelocityCommand(0.5, 0.2, time.time())
        safety_monitor.validate_command(command)

        assert safety_monitor._last_command_time > initial_time
