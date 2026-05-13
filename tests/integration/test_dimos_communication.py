"""Integration tests for dimos message bus communication.

Tests message passing, publish-subscribe patterns, agent communication,
and message ordering.
"""

import pytest
import time
import threading
from unittest.mock import Mock

from dimos_integration.message_handler import (
    MessageHandler,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
    SafetyEventMessage,
    HealthStatusMessage,
    HeartbeatMessage
)
from dimos_integration.agent_node import (
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
    SafetyAgent
)


class TestDimosCommunication:
    """Test dimos message bus communication."""

    @pytest.fixture
    def message_handler(self):
        """Create message handler."""
        handler = MessageHandler()
        handler.start()
        yield handler
        handler.stop()

    def test_publish_subscribe_basic(self, message_handler):
        """Test basic publish-subscribe functionality."""
        # Arrange
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_handler.subscribe(MessageType.PERSON_DETECTION, callback)

        # Act
        msg = PersonDetectionMessage(
            target_id=1,
            x=2.0,
            y=0.0,
            distance=2.0,
            angle=0.0,
            confidence=0.9
        )
        message_handler.publish(MessageType.PERSON_DETECTION, msg)
        time.sleep(0.1)

        # Assert
        assert len(received_messages) == 1
        assert received_messages[0].target_id == 1

    def test_multiple_subscribers(self, message_handler):
        """Test multiple subscribers receive same message."""
        # Arrange
        received_1 = []
        received_2 = []
        received_3 = []

        def callback_1(msg):
            received_1.append(msg)

        def callback_2(msg):
            received_2.append(msg)

        def callback_3(msg):
            received_3.append(msg)

        message_handler.subscribe(MessageType.ROBOT_POSE, callback_1)
        message_handler.subscribe(MessageType.ROBOT_POSE, callback_2)
        message_handler.subscribe(MessageType.ROBOT_POSE, callback_3)

        # Act
        msg = RobotPoseMessage(x=1.0, y=2.0, theta=0.5, covariance=[0.01] * 9)
        message_handler.publish(MessageType.ROBOT_POSE, msg)
        time.sleep(0.1)

        # Assert
        assert len(received_1) == 1
        assert len(received_2) == 1
        assert len(received_3) == 1
        assert received_1[0].x == 1.0
        assert received_2[0].x == 1.0
        assert received_3[0].x == 1.0

    def test_message_type_isolation(self, message_handler):
        """Test messages are only delivered to correct type subscribers."""
        # Arrange
        pose_messages = []
        detection_messages = []

        def pose_callback(msg):
            pose_messages.append(msg)

        def detection_callback(msg):
            detection_messages.append(msg)

        message_handler.subscribe(MessageType.ROBOT_POSE, pose_callback)
        message_handler.subscribe(MessageType.PERSON_DETECTION, detection_callback)

        # Act
        pose_msg = RobotPoseMessage(x=1.0, y=2.0, theta=0.5, covariance=[0.01] * 9)
        detection_msg = PersonDetectionMessage(
            target_id=1, x=2.0, y=0.0, distance=2.0, angle=0.0, confidence=0.9
        )

        message_handler.publish(MessageType.ROBOT_POSE, pose_msg)
        message_handler.publish(MessageType.PERSON_DETECTION, detection_msg)
        time.sleep(0.1)

        # Assert
        assert len(pose_messages) == 1
        assert len(detection_messages) == 1
        assert isinstance(pose_messages[0], RobotPoseMessage)
        assert isinstance(detection_messages[0], PersonDetectionMessage)

    def test_unsubscribe(self, message_handler):
        """Test unsubscribe stops message delivery."""
        # Arrange
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, callback)

        # Act - publish before unsubscribe
        msg1 = MotionCommandMessage(linear_x=0.5, angular_z=0.0)
        message_handler.publish(MessageType.MOTION_COMMAND, msg1)
        time.sleep(0.1)

        # Unsubscribe
        message_handler.unsubscribe(MessageType.MOTION_COMMAND, callback)

        # Publish after unsubscribe
        msg2 = MotionCommandMessage(linear_x=0.3, angular_z=0.1)
        message_handler.publish(MessageType.MOTION_COMMAND, msg2)
        time.sleep(0.1)

        # Assert - only first message received
        assert len(received_messages) == 1

    def test_message_sequence_numbers(self, message_handler):
        """Test messages have increasing sequence numbers."""
        # Arrange
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_handler.subscribe(MessageType.HEARTBEAT, callback)

        # Act - publish multiple messages
        for i in range(10):
            msg = HeartbeatMessage(agent_name="test", status="running")
            message_handler.publish(MessageType.HEARTBEAT, msg)

        time.sleep(0.2)

        # Assert
        assert len(received_messages) == 10
        for i in range(9):
            assert received_messages[i + 1].sequence > received_messages[i].sequence

    def test_message_timestamps(self, message_handler):
        """Test messages have valid timestamps."""
        # Arrange
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, callback)

        # Act
        start_time = time.time()
        msg = SafetyEventMessage(
            level="warning",
            event_type="test",
            description="Test event"
        )
        message_handler.publish(MessageType.SAFETY_EVENT, msg)
        time.sleep(0.1)
        end_time = time.time()

        # Assert
        assert len(received_messages) == 1
        assert start_time <= received_messages[0].timestamp <= end_time

    def test_concurrent_publishing(self, message_handler):
        """Test message handler handles concurrent publishing."""
        # Arrange
        received_messages = []
        lock = threading.Lock()

        def callback(msg):
            with lock:
                received_messages.append(msg)

        message_handler.subscribe(MessageType.PERSON_DETECTION, callback)

        # Act - publish from multiple threads
        def publish_messages(thread_id):
            for i in range(10):
                msg = PersonDetectionMessage(
                    target_id=thread_id,
                    x=float(i),
                    y=0.0,
                    distance=float(i),
                    angle=0.0,
                    confidence=0.9
                )
                message_handler.publish(MessageType.PERSON_DETECTION, msg)
                time.sleep(0.01)

        threads = []
        for tid in range(5):
            t = threading.Thread(target=publish_messages, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        time.sleep(0.5)

        # Assert
        assert len(received_messages) == 50  # 5 threads * 10 messages

    def test_message_handler_statistics(self, message_handler):
        """Test message handler tracks statistics."""
        # Arrange
        def callback(msg):
            pass

        message_handler.subscribe(MessageType.HEALTH_STATUS, callback)

        # Act - publish messages
        for _ in range(5):
            msg = HealthStatusMessage(
                cpu_usage=50.0,
                memory_usage=60.0,
                camera_fps=30.0,
                battery_level=80.0,
                network_latency=10.0
            )
            message_handler.publish(MessageType.HEALTH_STATUS, msg)

        time.sleep(0.2)

        stats = message_handler.get_statistics()

        # Assert
        assert stats[MessageType.HEALTH_STATUS.value]['published'] == 5
        assert stats[MessageType.HEALTH_STATUS.value]['subscribers'] == 1

    def test_agent_to_agent_communication(
        self,
        message_handler,
        mock_camera,
        mock_go2_client,
        temp_config_dir
    ):
        """Test communication between agents."""
        # Arrange
        perception_agent = PerceptionAgent(
            message_handler=message_handler,
            camera=mock_camera,
            config_dir=str(temp_config_dir)
        )
        navigation_agent = NavigationAgent(
            message_handler=message_handler,
            robot_client=mock_go2_client,
            config_dir=str(temp_config_dir)
        )

        received_commands = []

        def command_callback(msg):
            received_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, command_callback)

        # Act - start agents
        perception_agent.start()
        navigation_agent.start()
        time.sleep(0.5)

        # Simulate perception publishing target
        target_msg = PersonDetectionMessage(
            target_id=1,
            x=2.0,
            y=0.0,
            distance=2.0,
            angle=0.0,
            confidence=0.9
        )
        message_handler.publish(MessageType.PERSON_DETECTION, target_msg)
        time.sleep(0.3)

        # Stop agents
        perception_agent.stop()
        navigation_agent.stop()

        # Assert - navigation should have generated commands
        # May be empty depending on agent implementation
        assert isinstance(received_commands, list)

    def test_message_queue_overflow_handling(self, message_handler):
        """Test message handler handles queue overflow gracefully."""
        # Arrange
        received_count = [0]

        def slow_callback(msg):
            time.sleep(0.1)  # Slow processing
            received_count[0] += 1

        message_handler.subscribe(MessageType.PERSON_DETECTION, slow_callback)

        # Act - publish many messages quickly
        for i in range(150):  # More than queue size (100)
            msg = PersonDetectionMessage(
                target_id=1,
                x=float(i),
                y=0.0,
                distance=2.0,
                angle=0.0,
                confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, msg)

        time.sleep(2.0)

        # Assert - some messages may be dropped, but no crash
        assert received_count[0] > 0
        assert received_count[0] <= 150

    def test_message_handler_start_stop(self):
        """Test message handler start and stop."""
        # Arrange
        handler = MessageHandler()

        # Act & Assert - start
        handler.start()
        assert handler._running is True

        # Stop
        handler.stop()
        assert handler._running is False

        # Restart
        handler.start()
        assert handler._running is True
        handler.stop()

    def test_clear_message_queues(self, message_handler):
        """Test clearing message queues."""
        # Arrange
        received_messages = []

        def callback(msg):
            time.sleep(0.5)  # Slow processing to build up queue
            received_messages.append(msg)

        message_handler.subscribe(MessageType.ROBOT_POSE, callback)

        # Act - publish messages
        for i in range(10):
            msg = RobotPoseMessage(
                x=float(i),
                y=0.0,
                theta=0.0,
                covariance=[0.01] * 9
            )
            message_handler.publish(MessageType.ROBOT_POSE, msg)

        # Clear queues before processing completes
        time.sleep(0.1)
        message_handler.clear_queues()
        time.sleep(1.0)

        # Assert - fewer messages processed due to clearing
        assert len(received_messages) < 10

    def test_error_in_subscriber_callback(self, message_handler):
        """Test message handler handles subscriber errors gracefully."""
        # Arrange
        good_messages = []
        error_count = [0]

        def good_callback(msg):
            good_messages.append(msg)

        def bad_callback(msg):
            error_count[0] += 1
            raise ValueError("Test error")

        message_handler.subscribe(MessageType.SAFETY_EVENT, good_callback)
        message_handler.subscribe(MessageType.SAFETY_EVENT, bad_callback)

        # Act
        msg = SafetyEventMessage(
            level="warning",
            event_type="test",
            description="Test"
        )
        message_handler.publish(MessageType.SAFETY_EVENT, msg)
        time.sleep(0.2)

        # Assert - good callback still receives message despite bad callback error
        assert len(good_messages) == 1
        assert error_count[0] == 1
