"""Unit tests for safety_monitor module.

Tests the critical safety monitoring functionality.
CRITICAL: This module requires 100% test coverage.
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.safety.safety_monitor import (
    SafetyMonitor,
    SafetyLevel,
    SafetyEvent,
    VelocityCommand
)


@pytest.fixture
def temp_config():
    """Create a temporary config file."""
    config_content = """
safety_monitor:
  max_linear_velocity: 0.8
  max_angular_velocity: 1.0
  min_obstacle_distance: 0.3
  emergency_stop_distance: 0.5
  emergency_stop_timeout: 0.1
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        return f.name


@pytest.fixture
def safety_monitor(temp_config):
    """Create a SafetyMonitor instance."""
    return SafetyMonitor(config_path=temp_config)


@pytest.fixture
def safety_monitor_no_config():
    """Create a SafetyMonitor with default config (no file)."""
    return SafetyMonitor(config_path="nonexistent.yaml")


class TestSafetyLevel:
    """Test SafetyLevel enum."""

    def test_safety_levels(self):
        """Test all safety level values."""
        assert SafetyLevel.NORMAL.value == "normal"
        assert SafetyLevel.WARNING.value == "warning"
        assert SafetyLevel.CRITICAL.value == "critical"
        assert SafetyLevel.EMERGENCY.value == "emergency"


class TestVelocityCommand:
    """Test VelocityCommand dataclass."""

    def test_velocity_command_creation(self):
        """Test creating a VelocityCommand."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2, timestamp=time.time())
        assert cmd.linear_x == 0.5
        assert cmd.angular_z == 0.2
        assert cmd.timestamp > 0


class TestSafetyEvent:
    """Test SafetyEvent dataclass."""

    def test_safety_event_creation(self):
        """Test creating a SafetyEvent."""
        event = SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.WARNING,
            event_type="TEST",
            description="Test event"
        )
        assert event.level == SafetyLevel.WARNING
        assert event.event_type == "TEST"
        assert event.description == "Test event"
        assert event.command is None

    def test_safety_event_with_command(self):
        """Test SafetyEvent with command."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2, timestamp=time.time())
        event = SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.CRITICAL,
            event_type="VETO",
            description="Command vetoed",
            command=cmd
        )
        assert event.command == cmd


class TestSafetyMonitor:
    """Test SafetyMonitor class."""

    def test_initialization_with_config(self, safety_monitor):
        """Test initialization with config file."""
        assert safety_monitor.config['max_linear_velocity'] == 0.8
        assert safety_monitor.config['max_angular_velocity'] == 1.0
        assert safety_monitor.config['min_obstacle_distance'] == 0.3
        assert safety_monitor.config['emergency_stop_distance'] == 0.5
        assert not safety_monitor._emergency_stop_active

    def test_initialization_without_config(self, safety_monitor_no_config):
        """Test initialization with default config."""
        assert safety_monitor_no_config.config['max_linear_velocity'] == 0.8
        assert safety_monitor_no_config.config['max_angular_velocity'] == 1.0

    def test_validate_command_within_limits(self, safety_monitor):
        """Test validating command within all limits."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(
            cmd,
            target_distance=2.0,
            min_obstacle_distance=1.0
        )

        assert is_valid is True
        assert reason is None

    def test_validate_command_exceeds_linear_velocity(self, safety_monitor):
        """Test validating command that exceeds linear velocity limit."""
        cmd = VelocityCommand(linear_x=1.5, angular_z=0.5, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(cmd)

        assert is_valid is False
        assert "Linear velocity exceeds limit" in reason

    def test_validate_command_exceeds_angular_velocity(self, safety_monitor):
        """Test validating command that exceeds angular velocity limit."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=2.0, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(cmd)

        assert is_valid is False
        assert "Angular velocity exceeds limit" in reason

    def test_validate_command_negative_velocities(self, safety_monitor):
        """Test validating command with negative velocities."""
        cmd = VelocityCommand(linear_x=-0.9, angular_z=-0.5, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(cmd)

        # Should fail because |-0.9| > 0.8
        assert is_valid is False

    def test_validate_command_target_too_close_emergency(self, safety_monitor):
        """Test emergency stop when target is too close."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.0, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(
            cmd,
            target_distance=0.3  # Below emergency threshold of 0.5
        )

        assert is_valid is False
        assert "Emergency stop" in reason
        assert safety_monitor.is_emergency_stop_active()

    def test_validate_command_obstacle_too_close(self, safety_monitor):
        """Test vetoing command when obstacle is too close."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.0, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(
            cmd,
            min_obstacle_distance=0.2  # Below threshold of 0.3
        )

        assert is_valid is False
        assert "Obstacle too close" in reason

    def test_validate_command_during_emergency_stop(self, safety_monitor):
        """Test that all commands are vetoed during emergency stop."""
        # Trigger emergency stop
        safety_monitor.trigger_emergency_stop("Test emergency")

        cmd = VelocityCommand(linear_x=0.1, angular_z=0.0, timestamp=time.time())
        is_valid, reason = safety_monitor.validate_command(cmd)

        assert is_valid is False
        assert "Emergency stop active" in reason

    def test_trigger_emergency_stop(self, safety_monitor):
        """Test triggering emergency stop."""
        assert not safety_monitor.is_emergency_stop_active()

        safety_monitor.trigger_emergency_stop("Manual trigger")

        assert safety_monitor.is_emergency_stop_active()
        stats = safety_monitor.get_statistics()
        assert stats['emergency_stops'] == 1

    def test_reset_emergency_stop(self, safety_monitor):
        """Test resetting emergency stop."""
        safety_monitor.trigger_emergency_stop("Test")
        assert safety_monitor.is_emergency_stop_active()

        result = safety_monitor.reset_emergency_stop()

        assert result is True
        assert not safety_monitor.is_emergency_stop_active()

    def test_reset_emergency_stop_when_not_active(self, safety_monitor):
        """Test resetting emergency stop when not active."""
        assert not safety_monitor.is_emergency_stop_active()

        result = safety_monitor.reset_emergency_stop()

        assert result is False

    def test_is_emergency_stop_active(self, safety_monitor):
        """Test checking emergency stop status."""
        assert not safety_monitor.is_emergency_stop_active()

        safety_monitor.trigger_emergency_stop("Test")
        assert safety_monitor.is_emergency_stop_active()

        safety_monitor.reset_emergency_stop()
        assert not safety_monitor.is_emergency_stop_active()

    def test_get_statistics_initial(self, safety_monitor):
        """Test getting statistics initially."""
        stats = safety_monitor.get_statistics()

        assert stats['total_commands'] == 0
        assert stats['vetoed_commands'] == 0
        assert stats['emergency_stops'] == 0
        assert stats['veto_rate'] == 0.0

    def test_get_statistics_after_commands(self, safety_monitor):
        """Test statistics after processing commands."""
        # Valid command
        cmd1 = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())
        safety_monitor.validate_command(cmd1)

        # Invalid command
        cmd2 = VelocityCommand(linear_x=1.5, angular_z=0.5, timestamp=time.time())
        safety_monitor.validate_command(cmd2)

        stats = safety_monitor.get_statistics()

        assert stats['total_commands'] == 2
        assert stats['vetoed_commands'] == 1
        assert stats['veto_rate'] == 0.5

    def test_get_statistics_veto_rate_calculation(self, safety_monitor):
        """Test veto rate calculation."""
        # Process 10 commands, veto 3
        for i in range(10):
            if i < 7:
                cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())
            else:
                cmd = VelocityCommand(linear_x=1.5, angular_z=0.5, timestamp=time.time())
            safety_monitor.validate_command(cmd)

        stats = safety_monitor.get_statistics()
        assert stats['total_commands'] == 10
        assert stats['vetoed_commands'] == 3
        assert abs(stats['veto_rate'] - 0.3) < 0.001

    def test_thread_safety_concurrent_validation(self, safety_monitor):
        """Test thread safety with concurrent command validation."""
        import threading

        results = []

        def validate_commands():
            for _ in range(10):
                cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())
                is_valid, _ = safety_monitor.validate_command(cmd)
                results.append(is_valid)

        threads = [threading.Thread(target=validate_commands) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All commands should be valid
        assert all(results)

        # Total commands should be 50
        stats = safety_monitor.get_statistics()
        assert stats['total_commands'] == 50

    def test_thread_safety_emergency_stop(self, safety_monitor):
        """Test thread safety of emergency stop."""
        import threading

        def trigger_stop():
            safety_monitor.trigger_emergency_stop("Concurrent test")

        def check_stop():
            time.sleep(0.01)
            return safety_monitor.is_emergency_stop_active()

        threads = [threading.Thread(target=trigger_stop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Emergency stop should be active
        assert safety_monitor.is_emergency_stop_active()

        # Should have multiple emergency stops recorded
        stats = safety_monitor.get_statistics()
        assert stats['emergency_stops'] >= 1

    def test_log_safety_event(self, safety_monitor):
        """Test logging safety events to file."""
        event = SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.WARNING,
            event_type="TEST",
            description="Test event"
        )

        safety_monitor._log_safety_event(event)

        # Check that log file exists
        assert safety_monitor.safety_log_path.exists()

    def test_log_safety_event_with_command(self, safety_monitor):
        """Test logging safety event with command."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.2, timestamp=time.time())
        event = SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.CRITICAL,
            event_type="VETO",
            description="Command vetoed",
            command=cmd
        )

        safety_monitor._log_safety_event(event)

        # Read log file and verify content
        with open(safety_monitor.safety_log_path, 'r') as f:
            lines = f.readlines()
            last_line = lines[-1]
            assert "VETO" in last_line
            assert "linear_x=0.500" in last_line
            assert "angular_z=0.200" in last_line

    def test_shutdown(self, safety_monitor):
        """Test shutdown logs final statistics."""
        # Process some commands
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())
        safety_monitor.validate_command(cmd)

        safety_monitor.shutdown()

        # Verify shutdown was logged
        with open(safety_monitor.safety_log_path, 'r') as f:
            lines = f.readlines()
            last_line = lines[-1]
            assert "SHUTDOWN" in last_line

    def test_validate_command_updates_last_command_time(self, safety_monitor):
        """Test that valid commands update last command time."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())

        before = safety_monitor._last_command_time
        safety_monitor.validate_command(cmd)
        after = safety_monitor._last_command_time

        assert after > before

    def test_validate_command_does_not_update_time_on_veto(self, safety_monitor):
        """Test that vetoed commands don't update last command time."""
        cmd = VelocityCommand(linear_x=1.5, angular_z=0.5, timestamp=time.time())

        before = safety_monitor._last_command_time
        safety_monitor.validate_command(cmd)
        after = safety_monitor._last_command_time

        assert after == before

    def test_emergency_stop_timeout_value(self, safety_monitor):
        """Test that emergency stop timeout is configured correctly."""
        assert safety_monitor.config['emergency_stop_timeout'] == 0.1

    def test_multiple_emergency_stops(self, safety_monitor):
        """Test multiple emergency stop triggers."""
        safety_monitor.trigger_emergency_stop("First")
        safety_monitor.trigger_emergency_stop("Second")
        safety_monitor.trigger_emergency_stop("Third")

        stats = safety_monitor.get_statistics()
        assert stats['emergency_stops'] == 3

    def test_validate_command_at_exact_limits(self, safety_monitor):
        """Test validation at exact velocity limits."""
        # At exact linear limit
        cmd1 = VelocityCommand(linear_x=0.8, angular_z=0.0, timestamp=time.time())
        is_valid1, _ = safety_monitor.validate_command(cmd1)
        assert is_valid1 is True

        # At exact angular limit
        cmd2 = VelocityCommand(linear_x=0.0, angular_z=1.0, timestamp=time.time())
        is_valid2, _ = safety_monitor.validate_command(cmd2)
        assert is_valid2 is True

    def test_validate_command_at_exact_distance_thresholds(self, safety_monitor):
        """Test validation at exact distance thresholds."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.0, timestamp=time.time())

        # At exact emergency distance (should trigger)
        is_valid1, _ = safety_monitor.validate_command(
            cmd,
            target_distance=0.5
        )
        assert is_valid1 is False

        # Reset emergency stop
        safety_monitor.reset_emergency_stop()

        # At exact obstacle distance (should veto)
        is_valid2, _ = safety_monitor.validate_command(
            cmd,
            min_obstacle_distance=0.3
        )
        assert is_valid2 is False

    def test_validate_command_none_distances(self, safety_monitor):
        """Test validation with None distance values."""
        cmd = VelocityCommand(linear_x=0.5, angular_z=0.5, timestamp=time.time())

        is_valid, reason = safety_monitor.validate_command(
            cmd,
            target_distance=None,
            min_obstacle_distance=None
        )

        assert is_valid is True
        assert reason is None
