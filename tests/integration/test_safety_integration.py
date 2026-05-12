"""Integration tests for safety monitor integration.

Tests safety monitor validation, emergency stop, watchdog timeouts,
and health checking across the system.
"""

import time
from unittest.mock import Mock, patch
import pytest

from src.dimos_integration.message_handler import (
    MessageBus,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
    SafetyEventMessage,
    HealthStatusMessage,
)
from src.dimos_integration.agent_node import (
    NavigationAgent,
    SafetyAgent,
)
from src.safety.watchdog import ComponentType


class TestSafetyIntegration:
    """Test safety monitor integration with other modules."""

    @pytest.fixture
    def message_bus(self):
        """Create message bus for testing."""
        return MessageBus()

    def test_safety_validates_motion_commands(self, message_bus):
        """Test that safety agent validates motion commands."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to safety events
        received_events = []
        def callback(msg):
            received_events.append(msg)

        message_bus.subscribe(MessageType.SAFETY_EVENT, callback)

        # Start safety agent
        safety.start()

        # Publish a safe motion command
        safe_cmd = MotionCommandMessage(
            source_agent="test",
            linear_x=0.5,
            angular_z=0.3,
            validated=False
        )
        message_bus.publish(MessageType.MOTION_COMMAND, safe_cmd)

        # Publish target detection (safe distance)
        detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=2.5
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection)

        # Let safety process
        time.sleep(0.2)

        # Command should be validated (no safety events for safe command)
        assert safe_cmd.validated

        safety.stop()

    def test_safety_rejects_unsafe_velocity(self, message_bus):
        """Test that safety rejects commands exceeding velocity limits."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to safety events
        received_events = []
        def callback(msg):
            received_events.append(msg)

        message_bus.subscribe(MessageType.SAFETY_EVENT, callback)

        # Start safety agent
        safety.start()

        # Publish unsafe motion command (exceeds max velocity)
        unsafe_cmd = MotionCommandMessage(
            source_agent="test",
            linear_x=2.0,  # Exceeds max 0.8 m/s
            angular_z=0.0,
            validated=False
        )
        message_bus.publish(MessageType.MOTION_COMMAND, unsafe_cmd)

        # Publish target detection
        detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=3.0
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection)

        # Let safety process
        time.sleep(0.2)

        # Should have safety event
        assert len(received_events) > 0
        event = received_events[-1]
        assert event.level in ["critical", "warning"]
        assert "rejected" in event.reason.lower() or "velocity" in event.reason.lower()

        safety.stop()

    def test_emergency_stop_on_close_distance(self, message_bus):
        """Test emergency stop triggers when target too close."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to safety events
        received_events = []
        def callback(msg):
            received_events.append(msg)

        message_bus.subscribe(MessageType.SAFETY_EVENT, callback)

        # Start safety agent
        safety.start()

        # Publish motion command
        cmd = MotionCommandMessage(
            source_agent="test",
            linear_x=0.5,
            angular_z=0.0,
            validated=False
        )
        message_bus.publish(MessageType.MOTION_COMMAND, cmd)

        # Publish target detection with emergency distance
        detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=0.3  # Below emergency threshold (0.5m)
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection)

        # Let safety process
        time.sleep(0.2)

        # Should have emergency stop event
        assert len(received_events) > 0
        emergency_events = [e for e in received_events if e.emergency_stop_active]
        assert len(emergency_events) > 0

        safety.stop()

    def test_watchdog_timeout_no_target(self, message_bus):
        """Test watchdog triggers timeout when no target detected."""
        # Create safety agent with shorter timeout for testing
        with patch('src.safety.watchdog.Watchdog') as MockWatchdog:
            mock_watchdog = Mock()
            MockWatchdog.return_value = mock_watchdog

            safety = SafetyAgent(message_bus, update_rate=50.0)
            safety.watchdog = mock_watchdog

            # Subscribe to safety events
            received_events = []
            def callback(msg):
                received_events.append(msg)

            message_bus.subscribe(MessageType.SAFETY_EVENT, callback)

            # Start safety agent
            safety.start()

            # Don't publish any target detections
            # Simulate watchdog timeout
            time.sleep(0.1)

            # Manually trigger watchdog callback
            safety._on_watchdog_timeout(ComponentType.PERCEPTION, "No target detected")

            # Let safety process
            time.sleep(0.1)

            # Should have emergency stop event
            assert len(received_events) > 0
            event = received_events[-1]
            assert event.emergency_stop_active
            assert "watchdog" in event.reason.lower()

            safety.stop()

    def test_health_status_published(self, message_bus):
        """Test that health status is published regularly."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=10.0)

        # Subscribe to health status
        received_health = []
        def callback(msg):
            received_health.append(msg)

        message_bus.subscribe(MessageType.HEALTH_STATUS, callback)

        # Start safety agent
        safety.start()

        # Let it run
        time.sleep(0.3)

        safety.stop()

        # Should have received health status messages
        assert len(received_health) > 0
        health = received_health[0]
        assert isinstance(health, HealthStatusMessage)
        assert 0.0 <= health.cpu_usage <= 100.0
        assert 0.0 <= health.memory_usage <= 100.0
        assert 0.0 <= health.battery_level <= 100.0

    def test_safety_navigation_integration(self, message_bus):
        """Test safety agent validates navigation commands."""
        # Create navigation and safety agents
        navigation = NavigationAgent(message_bus, update_rate=10.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to safety events
        received_events = []
        def callback(msg):
            received_events.append(msg)

        message_bus.subscribe(MessageType.SAFETY_EVENT, callback)

        # Start agents
        navigation.start()
        safety.start()

        # Publish robot pose
        pose = RobotPoseMessage(
            source_agent="test",
            x=0.0,
            y=0.0,
            theta=0.0
        )
        message_bus.publish(MessageType.ROBOT_POSE, pose)

        # Publish target detection
        detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=2.5,
            angle=10.0
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection)

        # Let system run
        time.sleep(0.3)

        # Stop agents
        safety.stop()
        navigation.stop()

        # Navigation should have generated commands
        # Safety should have validated them (no critical events for safe scenario)
        critical_events = [e for e in received_events if e.level == "critical"]
        assert len(critical_events) == 0

    def test_emergency_stop_overrides_navigation(self, message_bus):
        """Test that emergency stop overrides navigation commands."""
        # Create navigation and safety agents
        navigation = NavigationAgent(message_bus, update_rate=10.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to motion commands to verify stop
        received_commands = []
        def cmd_callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, cmd_callback)

        # Subscribe to safety events
        received_events = []
        def event_callback(msg):
            received_events.append(msg)

        message_bus.subscribe(MessageType.SAFETY_EVENT, event_callback)

        # Start agents
        navigation.start()
        safety.start()

        # Publish robot pose
        pose = RobotPoseMessage(
            source_agent="test",
            x=0.0,
            y=0.0,
            theta=0.0
        )
        message_bus.publish(MessageType.ROBOT_POSE, pose)

        # First publish safe target
        safe_detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=2.5,
            angle=0.0
        )
        message_bus.publish(MessageType.PERSON_DETECTION, safe_detection)

        time.sleep(0.2)

        # Now publish emergency distance
        emergency_detection = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=0.3,  # Emergency distance
            angle=0.0
        )
        message_bus.publish(MessageType.PERSON_DETECTION, emergency_detection)

        time.sleep(0.2)

        # Stop agents
        safety.stop()
        navigation.stop()

        # Should have emergency stop event
        emergency_events = [e for e in received_events if e.emergency_stop_active]
        assert len(emergency_events) > 0

    def test_watchdog_monitors_all_components(self, message_bus):
        """Test that watchdog monitors all system components."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Start safety agent
        safety.start()

        # Publish messages from different components
        detection = PersonDetectionMessage(
            source_agent="PerceptionAgent",
            target_id=1,
            distance=2.5
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection)

        pose = RobotPoseMessage(
            source_agent="LocalizationAgent",
            x=0.0,
            y=0.0,
            theta=0.0
        )
        message_bus.publish(MessageType.ROBOT_POSE, pose)

        cmd = MotionCommandMessage(
            source_agent="NavigationAgent",
            linear_x=0.5,
            angular_z=0.0
        )
        message_bus.publish(MessageType.MOTION_COMMAND, cmd)

        # Let watchdog process
        time.sleep(0.2)

        # Get watchdog status
        status = safety.watchdog.get_status()

        # All components should be healthy
        assert ComponentType.PERCEPTION.value in status
        assert ComponentType.NAVIGATION.value in status
        assert ComponentType.LOCALIZATION.value in status

        safety.stop()

    def test_health_checker_warnings(self, message_bus):
        """Test health checker generates warnings for degraded conditions."""
        # Create safety agent
        safety = SafetyAgent(message_bus, update_rate=10.0)

        # Mock health checker to return warning conditions
        mock_health = Mock()
        mock_health.metrics.cpu_percent = 85.0  # Above warning threshold
        mock_health.metrics.memory_percent = 50.0
        mock_health.metrics.camera_fps = 15.0  # Below warning threshold
        mock_health.metrics.battery_percent = 15.0  # Below warning threshold
        mock_health.is_healthy = False
        mock_health.warnings = ["High CPU usage", "Low camera FPS", "Low battery"]

        safety.health_checker.get_health_report = Mock(return_value=mock_health)

        # Subscribe to health status
        received_health = []
        def callback(msg):
            received_health.append(msg)

        message_bus.subscribe(MessageType.HEALTH_STATUS, callback)

        # Start safety agent
        safety.start()

        # Let it run
        time.sleep(0.2)

        safety.stop()

        # Should have health status with warnings
        assert len(received_health) > 0
        health = received_health[0]
        assert health.cpu_usage >= 80.0
        assert health.camera_fps < 20.0
        assert health.battery_level < 20.0
