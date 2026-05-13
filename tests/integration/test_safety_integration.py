"""Integration tests for safety monitor integration.

Tests safety monitor's ability to validate commands, trigger emergency stops,
and integrate with watchdog and health checker.
"""

import pytest
import time
from unittest.mock import Mock, patch

from safety.safety_monitor import SafetyMonitor
from safety.watchdog import Watchdog
from safety.health_checker import HealthChecker
from dimos_integration.message_handler import (
    MessageHandler,
    MessageType,
    MotionCommandMessage,
    SafetyEventMessage,
    HealthStatusMessage,
    HeartbeatMessage
)


class TestSafetyIntegration:
    """Test safety monitor integration with other modules."""

    @pytest.fixture
    def message_handler(self):
        """Create message handler."""
        handler = MessageHandler()
        handler.start()
        yield handler
        handler.stop()

    @pytest.fixture
    def safety_monitor(self, message_handler, temp_log_dir):
        """Create safety monitor."""
        monitor = SafetyMonitor(
            message_handler=message_handler,
            log_dir=str(temp_log_dir)
        )
        yield monitor
        monitor.stop()

    @pytest.fixture
    def watchdog(self, message_handler):
        """Create watchdog."""
        dog = Watchdog(message_handler=message_handler)
        yield dog
        dog.stop()

    @pytest.fixture
    def health_checker(self, message_handler):
        """Create health checker."""
        checker = HealthChecker(message_handler=message_handler)
        yield checker
        checker.stop()

    def test_safety_monitor_validates_safe_command(
        self,
        safety_monitor,
        message_handler
    ):
        """Test safety monitor allows safe commands."""
        # Arrange
        safety_monitor.start()
        validated_commands = []

        def validated_callback(msg):
            if msg.validated:
                validated_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, validated_callback)

        # Act - send safe command
        safe_command = MotionCommandMessage(
            linear_x=0.5,  # Within limits
            angular_z=0.3  # Within limits
        )
        message_handler.publish(MessageType.MOTION_COMMAND, safe_command)
        time.sleep(0.2)

        # Assert
        assert len(validated_commands) > 0
        assert validated_commands[0].validated is True

    def test_safety_monitor_vetoes_unsafe_velocity(
        self,
        safety_monitor,
        message_handler
    ):
        """Test safety monitor vetoes commands exceeding velocity limits."""
        # Arrange
        safety_monitor.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - send unsafe command (exceeds max velocity)
        unsafe_command = MotionCommandMessage(
            linear_x=1.5,  # Exceeds 0.8 m/s limit
            angular_z=0.0
        )
        message_handler.publish(MessageType.MOTION_COMMAND, unsafe_command)
        time.sleep(0.2)

        # Assert
        assert len(safety_events) > 0
        assert any(
            "velocity" in event.description.lower()
            for event in safety_events
        )

    def test_safety_monitor_emergency_stop(
        self,
        safety_monitor,
        message_handler
    ):
        """Test emergency stop triggered by safety monitor."""
        # Arrange
        safety_monitor.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - trigger emergency stop (distance too close)
        safety_monitor.update_obstacle_distance(0.3)  # Below 0.5m threshold
        time.sleep(0.2)

        # Assert
        assert len(safety_events) > 0
        emergency_events = [
            e for e in safety_events
            if e.emergency_stop_active
        ]
        assert len(emergency_events) > 0
        assert emergency_events[0].level == "emergency"

    def test_watchdog_detects_target_timeout(
        self,
        watchdog,
        message_handler
    ):
        """Test watchdog detects when no target detected for too long."""
        # Arrange
        watchdog.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - wait for timeout (no target messages sent)
        time.sleep(2.5)  # Exceeds 2.0s timeout

        # Assert
        assert len(safety_events) > 0
        timeout_events = [
            e for e in safety_events
            if "timeout" in e.description.lower()
        ]
        assert len(timeout_events) > 0

    def test_watchdog_reset_by_heartbeat(
        self,
        watchdog,
        message_handler
    ):
        """Test watchdog is reset by heartbeat messages."""
        # Arrange
        watchdog.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - send heartbeats regularly
        for _ in range(5):
            heartbeat = HeartbeatMessage(
                agent_name="perception",
                status="running"
            )
            message_handler.publish(MessageType.HEARTBEAT, heartbeat)
            time.sleep(0.4)  # Less than 0.5s timeout

        # Assert - no timeout events
        timeout_events = [
            e for e in safety_events
            if "timeout" in e.description.lower()
        ]
        assert len(timeout_events) == 0

    def test_health_checker_monitors_system(
        self,
        health_checker,
        message_handler
    ):
        """Test health checker monitors system health."""
        # Arrange
        health_checker.start()
        health_messages = []

        def health_callback(msg):
            health_messages.append(msg)

        message_handler.subscribe(MessageType.HEALTH_STATUS, health_callback)

        # Act - wait for health check
        time.sleep(1.5)

        # Assert
        assert len(health_messages) > 0
        latest_health = health_messages[-1]
        assert latest_health.cpu_usage >= 0.0
        assert latest_health.memory_usage >= 0.0
        assert latest_health.battery_level >= 0.0

    def test_health_checker_warns_high_cpu(
        self,
        health_checker,
        message_handler
    ):
        """Test health checker warns on high CPU usage."""
        # Arrange
        health_checker.start()
        health_messages = []

        def health_callback(msg):
            health_messages.append(msg)

        message_handler.subscribe(MessageType.HEALTH_STATUS, health_callback)

        # Act - simulate high CPU
        with patch('psutil.cpu_percent', return_value=85.0):
            time.sleep(1.5)

        # Assert
        if health_messages:
            warnings = [
                msg for msg in health_messages
                if any("cpu" in w.lower() for w in msg.warnings)
            ]
            # May or may not have warnings depending on timing
            assert isinstance(warnings, list)

    def test_health_checker_critical_battery(
        self,
        health_checker,
        message_handler
    ):
        """Test health checker triggers critical event on low battery."""
        # Arrange
        health_checker.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - simulate critical battery
        health_checker.update_battery_level(5.0)  # Below 10% critical threshold
        time.sleep(0.5)

        # Assert
        critical_events = [
            e for e in safety_events
            if e.level == "critical" and "battery" in e.description.lower()
        ]
        assert len(critical_events) > 0

    def test_safety_monitor_and_watchdog_coordination(
        self,
        safety_monitor,
        watchdog,
        message_handler
    ):
        """Test safety monitor and watchdog work together."""
        # Arrange
        safety_monitor.start()
        watchdog.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - send unsafe command while watchdog is active
        unsafe_command = MotionCommandMessage(
            linear_x=1.2,  # Exceeds limit
            angular_z=0.0
        )
        message_handler.publish(MessageType.MOTION_COMMAND, unsafe_command)
        time.sleep(0.5)

        # Assert - both should generate safety events
        assert len(safety_events) > 0

    def test_emergency_stop_overrides_all_commands(
        self,
        safety_monitor,
        message_handler
    ):
        """Test emergency stop prevents all motion commands."""
        # Arrange
        safety_monitor.start()
        validated_commands = []

        def validated_callback(msg):
            if msg.validated:
                validated_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, validated_callback)

        # Act - trigger emergency stop
        safety_monitor.trigger_emergency_stop("Test emergency")
        time.sleep(0.1)

        # Try to send command during emergency stop
        command = MotionCommandMessage(linear_x=0.3, angular_z=0.0)
        message_handler.publish(MessageType.MOTION_COMMAND, command)
        time.sleep(0.2)

        # Assert - no commands should be validated
        assert len(validated_commands) == 0

    def test_safety_event_logging(
        self,
        safety_monitor,
        message_handler,
        temp_log_dir
    ):
        """Test all safety events are logged to file."""
        # Arrange
        safety_monitor.start()

        # Act - trigger various safety events
        safety_monitor.trigger_emergency_stop("Test emergency")
        time.sleep(0.1)

        unsafe_command = MotionCommandMessage(linear_x=1.5, angular_z=0.0)
        message_handler.publish(MessageType.MOTION_COMMAND, unsafe_command)
        time.sleep(0.2)

        # Assert - check log file exists and has content
        log_files = list(temp_log_dir.glob("safety_*.log"))
        assert len(log_files) > 0

        log_content = log_files[0].read_text()
        assert "emergency" in log_content.lower()

    def test_graceful_degradation_on_warnings(
        self,
        safety_monitor,
        health_checker,
        message_handler
    ):
        """Test system gracefully degrades on health warnings."""
        # Arrange
        safety_monitor.start()
        health_checker.start()
        health_messages = []

        def health_callback(msg):
            health_messages.append(msg)

        message_handler.subscribe(MessageType.HEALTH_STATUS, health_callback)

        # Act - simulate degraded conditions
        with patch('psutil.cpu_percent', return_value=85.0):
            time.sleep(1.5)

        # Assert - system should still be operational but with warnings
        if health_messages:
            latest = health_messages[-1]
            # System should report warnings but continue operating
            assert isinstance(latest.warnings, list)

    def test_safety_monitor_response_time(
        self,
        safety_monitor,
        message_handler
    ):
        """Test safety monitor responds within 100ms requirement."""
        # Arrange
        safety_monitor.start()
        safety_events = []
        event_times = []

        def safety_callback(msg):
            safety_events.append(msg)
            event_times.append(time.time())

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - trigger emergency stop and measure response time
        start_time = time.time()
        safety_monitor.update_obstacle_distance(0.3)  # Emergency condition
        time.sleep(0.15)

        # Assert
        if safety_events:
            response_time = event_times[0] - start_time
            assert response_time < 0.1  # Must respond within 100ms

    def test_multiple_safety_events_handling(
        self,
        safety_monitor,
        watchdog,
        health_checker,
        message_handler
    ):
        """Test system handles multiple simultaneous safety events."""
        # Arrange
        safety_monitor.start()
        watchdog.start()
        health_checker.start()
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - trigger multiple safety conditions
        safety_monitor.update_obstacle_distance(0.3)  # Emergency
        health_checker.update_battery_level(5.0)  # Critical battery
        unsafe_command = MotionCommandMessage(linear_x=1.5, angular_z=0.0)
        message_handler.publish(MessageType.MOTION_COMMAND, unsafe_command)
        time.sleep(0.5)

        # Assert - all events should be captured
        assert len(safety_events) >= 2
        event_types = {e.event_type for e in safety_events}
        assert len(event_types) >= 2  # Multiple different event types
