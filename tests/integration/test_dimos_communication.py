"""Integration tests for dimos message bus communication.

Tests message passing, publish-subscribe pattern, message ordering,
agent startup/shutdown, and message bus functionality.
"""

import time
from threading import Event
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


class TestDimosCommunication:
    """Test dimos message bus communication."""

    @pytest.fixture
    def message_bus(self):
        """Create message bus for testing."""
        return MessageBus()

    def test_publish_subscribe_pattern(self, message_bus):
        """Test basic publish-subscribe functionality."""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        # Subscribe to message type
        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Publish message
        msg = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            distance=2.5
        )
        message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Verify message received
        assert len(received_messages) == 1
        assert received_messages[0].target_id == 1
        assert received_messages[0].distance == 2.5

    def test_multiple_subscribers(self, message_bus):
        """Test multiple subscribers receive same message."""
        received_1 = []
        received_2 = []
        received_3 = []

        def callback1(msg):
            received_1.append(msg)

        def callback2(msg):
            received_2.append(msg)

        def callback3(msg):
            received_3.append(msg)

        # Subscribe multiple callbacks
        message_bus.subscribe(MessageType.ROBOT_POSE, callback1)
        message_bus.subscribe(MessageType.ROBOT_POSE, callback2)
        message_bus.subscribe(MessageType.ROBOT_POSE, callback3)

        # Publish message
        msg = RobotPoseMessage(
            source_agent="test",
            x=1.0,
            y=2.0,
            theta=0.5
        )
        message_bus.publish(MessageType.ROBOT_POSE, msg)

        # All subscribers should receive
        assert len(received_1) == 1
        assert len(received_2) == 1
        assert len(received_3) == 1

        # All should have same message
        assert received_1[0].x == 1.0
        assert received_2[0].x == 1.0
        assert received_3[0].x == 1.0

    def test_unsubscribe(self, message_bus):
        """Test unsubscribing from message type."""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        # Subscribe
        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Publish first message
        msg1 = MotionCommandMessage(
            source_agent="test",
            linear_x=0.5,
            angular_z=0.0
        )
        message_bus.publish(MessageType.MOTION_COMMAND, msg1)

        assert len(received_messages) == 1

        # Unsubscribe
        message_bus.unsubscribe(MessageType.MOTION_COMMAND, callback)

        # Publish second message
        msg2 = MotionCommandMessage(
            source_agent="test",
            linear_x=0.3,
            angular_z=0.2
        )
        message_bus.publish(MessageType.MOTION_COMMAND, msg2)

        # Should still have only one message
        assert len(received_messages) == 1

    def test_message_sequence_numbers(self, message_bus):
        """Test that messages have correct sequence numbers."""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Publish multiple messages from same source
        for i in range(5):
            msg = PersonDetectionMessage(
                source_agent="perception",
                target_id=i
            )
            message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Verify sequence numbers
        assert len(received_messages) == 5
        for i in range(5):
            assert received_messages[i].sequence_number == i + 1

    def test_message_timestamps(self, message_bus):
        """Test that messages have valid timestamps."""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_bus.subscribe(MessageType.ROBOT_POSE, callback)

        # Publish messages with delays
        for i in range(3):
            msg = RobotPoseMessage(
                source_agent="localization",
                x=float(i),
                y=0.0,
                theta=0.0
            )
            message_bus.publish(MessageType.ROBOT_POSE, msg)
            time.sleep(0.01)

        # Verify timestamps are increasing
        assert len(received_messages) == 3
        for i in range(1, 3):
            assert received_messages[i].timestamp >= received_messages[i-1].timestamp

    def test_message_history(self, message_bus):
        """Test message history retrieval."""
        # Publish multiple messages
        for i in range(10):
            msg = PersonDetectionMessage(
                source_agent="test",
                target_id=i
            )
            message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Get latest message
        latest = message_bus.get_latest_message(MessageType.PERSON_DETECTION)
        assert latest is not None
        assert latest.target_id == 9

        # Get message history
        history = message_bus.get_message_history(MessageType.PERSON_DETECTION, count=5)
        assert len(history) == 5
        assert history[-1].target_id == 9
        assert history[0].target_id == 5

    def test_clear_history(self, message_bus):
        """Test clearing message history."""
        # Publish messages
        for i in range(5):
            msg = PersonDetectionMessage(
                source_agent="test",
                target_id=i
            )
            message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Verify history exists
        history = message_bus.get_message_history(MessageType.PERSON_DETECTION)
        assert len(history) == 5

        # Clear history
        message_bus.clear_history(MessageType.PERSON_DETECTION)

        # Verify history cleared
        history = message_bus.get_message_history(MessageType.PERSON_DETECTION)
        assert len(history) == 0

    def test_message_bus_stats(self, message_bus):
        """Test message bus statistics."""
        # Subscribe to multiple message types
        def callback(msg):
            pass

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)
        message_bus.subscribe(MessageType.ROBOT_POSE, callback)
        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Publish messages
        msg1 = PersonDetectionMessage(source_agent="perception")
        message_bus.publish(MessageType.PERSON_DETECTION, msg1)

        msg2 = RobotPoseMessage(source_agent="localization")
        message_bus.publish(MessageType.ROBOT_POSE, msg2)

        # Get stats
        stats = message_bus.get_stats()

        # Verify stats
        assert "subscriber_counts" in stats
        assert "message_counts" in stats
        assert "sequence_counters" in stats

        assert stats["subscriber_counts"]["person_detection"] == 1
        assert stats["subscriber_counts"]["robot_pose"] == 1
        assert stats["message_counts"]["person_detection"] == 1
        assert stats["message_counts"]["robot_pose"] == 1

    def test_concurrent_publishing(self, message_bus):
        """Test concurrent message publishing from multiple sources."""
        received_messages = []
        lock = Event()

        def callback(msg):
            received_messages.append(msg)

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Publish from multiple sources concurrently
        import threading

        def publish_messages(source_name, count):
            for i in range(count):
                msg = PersonDetectionMessage(
                    source_agent=source_name,
                    target_id=i
                )
                message_bus.publish(MessageType.PERSON_DETECTION, msg)

        threads = []
        for i in range(3):
            t = threading.Thread(target=publish_messages, args=(f"source_{i}", 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have received all messages
        assert len(received_messages) == 30

    def test_message_isolation_between_types(self, message_bus):
        """Test that different message types are isolated."""
        detection_messages = []
        pose_messages = []
        command_messages = []

        def detection_callback(msg):
            detection_messages.append(msg)

        def pose_callback(msg):
            pose_messages.append(msg)

        def command_callback(msg):
            command_messages.append(msg)

        # Subscribe to different types
        message_bus.subscribe(MessageType.PERSON_DETECTION, detection_callback)
        message_bus.subscribe(MessageType.ROBOT_POSE, pose_callback)
        message_bus.subscribe(MessageType.MOTION_COMMAND, command_callback)

        # Publish to each type
        msg1 = PersonDetectionMessage(source_agent="test")
        message_bus.publish(MessageType.PERSON_DETECTION, msg1)

        msg2 = RobotPoseMessage(source_agent="test")
        message_bus.publish(MessageType.ROBOT_POSE, msg2)

        msg3 = MotionCommandMessage(source_agent="test")
        message_bus.publish(MessageType.MOTION_COMMAND, msg3)

        # Each callback should only receive its type
        assert len(detection_messages) == 1
        assert len(pose_messages) == 1
        assert len(command_messages) == 1

    def test_all_message_types(self, message_bus):
        """Test all defined message types can be published and received."""
        received = {msg_type: [] for msg_type in MessageType}

        # Subscribe to all types
        for msg_type in MessageType:
            def make_callback(mt):
                def callback(msg):
                    received[mt].append(msg)
                return callback

            message_bus.subscribe(msg_type, make_callback(msg_type))

        # Publish each message type
        message_bus.publish(
            MessageType.PERSON_DETECTION,
            PersonDetectionMessage(source_agent="test")
        )
        message_bus.publish(
            MessageType.ROBOT_POSE,
            RobotPoseMessage(source_agent="test")
        )
        message_bus.publish(
            MessageType.MOTION_COMMAND,
            MotionCommandMessage(source_agent="test")
        )
        message_bus.publish(
            MessageType.SAFETY_EVENT,
            SafetyEventMessage(source_agent="test")
        )
        message_bus.publish(
            MessageType.HEALTH_STATUS,
            HealthStatusMessage(source_agent="test")
        )

        # Verify all received
        for msg_type in MessageType:
            assert len(received[msg_type]) == 1

    def test_subscriber_error_handling(self, message_bus):
        """Test that subscriber errors don't affect other subscribers."""
        received_good = []

        def bad_callback(msg):
            raise ValueError("Intentional error")

        def good_callback(msg):
            received_good.append(msg)

        # Subscribe both callbacks
        message_bus.subscribe(MessageType.PERSON_DETECTION, bad_callback)
        message_bus.subscribe(MessageType.PERSON_DETECTION, good_callback)

        # Publish message
        msg = PersonDetectionMessage(source_agent="test", target_id=1)
        message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Good callback should still receive message
        assert len(received_good) == 1
        assert received_good[0].target_id == 1

    def test_message_bus_thread_safety(self, message_bus):
        """Test message bus thread safety with concurrent operations."""
        import threading

        received_messages = []
        lock = threading.Lock()

        def callback(msg):
            with lock:
                received_messages.append(msg)

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Concurrent publishers
        def publisher(agent_id, count):
            for i in range(count):
                msg = PersonDetectionMessage(
                    source_agent=f"agent_{agent_id}",
                    target_id=i
                )
                message_bus.publish(MessageType.PERSON_DETECTION, msg)

        # Concurrent subscribers
        def subscriber():
            def local_callback(msg):
                pass
            message_bus.subscribe(MessageType.ROBOT_POSE, local_callback)
            time.sleep(0.01)
            message_bus.unsubscribe(MessageType.ROBOT_POSE, local_callback)

        threads = []

        # Start publishers
        for i in range(5):
            t = threading.Thread(target=publisher, args=(i, 20))
            threads.append(t)
            t.start()

        # Start subscribers
        for i in range(3):
            t = threading.Thread(target=subscriber)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have received all published messages
        assert len(received_messages) == 100
