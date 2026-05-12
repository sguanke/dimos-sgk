"""Integration tests for perception to navigation data flow.

Tests the complete data flow from person detection through tracking
to navigation command generation.
"""

import time
from unittest.mock import Mock, patch
import numpy as np
import pytest

from src.dimos_integration.message_handler import (
    MessageBus,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
)
from src.dimos_integration.agent_node import (
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
)
from src.vision.person_detector import Detection
from src.vision.person_tracker import Track


class TestPerceptionToNavigation:
    """Test data flow from perception to navigation."""

    @pytest.fixture
    def message_bus(self):
        """Create message bus for testing."""
        return MessageBus()

    @pytest.fixture
    def mock_camera(self):
        """Create mock camera that returns test frames."""
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True

        # Create test frame with person
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)

        return mock_cap

    def test_perception_publishes_detection_message(self, message_bus, mock_camera):
        """Test that perception agent publishes person detection messages."""
        # Create perception agent with mocked camera
        with patch('cv2.VideoCapture', return_value=mock_camera):
            agent = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock detector to return a detection
            mock_detection = Detection(
                bbox=(100, 100, 200, 200),
                confidence=0.9,
                class_id=0
            )
            agent.detector.detect = Mock(return_value=[mock_detection])

            # Mock tracker to return a track
            mock_track = Track(
                track_id=1,
                bbox=(100, 100, 200, 200),
                confidence=0.9,
                distance=2.5,
                angle=0.0,
                velocity=(0.0, 0.0)
            )
            agent.tracker.update = Mock(return_value=[mock_track])

            # Mock target selector to return the track
            agent.target_selector.select_target = Mock(return_value=mock_track)

            # Subscribe to messages
            received_messages = []
            def callback(msg):
                received_messages.append(msg)

            message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

            # Start agent and let it run one update
            agent.start()
            time.sleep(0.2)
            agent.stop()

            # Verify message was published
            assert len(received_messages) > 0
            msg = received_messages[0]
            assert isinstance(msg, PersonDetectionMessage)
            assert msg.target_id == 1
            assert msg.distance == 2.5
            assert msg.angle == 0.0

    def test_navigation_receives_and_processes_detection(self, message_bus):
        """Test that navigation agent receives detection and generates command."""
        # Create navigation agent
        agent = NavigationAgent(message_bus, update_rate=10.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Publish robot pose
        pose_msg = RobotPoseMessage(
            source_agent="test",
            x=0.0,
            y=0.0,
            theta=0.0
        )
        message_bus.publish(MessageType.ROBOT_POSE, pose_msg)

        # Publish person detection
        detection_msg = PersonDetectionMessage(
            source_agent="test",
            target_id=1,
            bbox=(100, 100, 200, 200),
            distance=3.0,
            angle=10.0,
            confidence=0.9
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection_msg)

        # Start agent and let it process
        agent.start()
        time.sleep(0.2)
        agent.stop()

        # Verify motion command was generated
        assert len(received_commands) > 0
        cmd = received_commands[0]
        assert isinstance(cmd, MotionCommandMessage)
        assert cmd.linear_x != 0.0 or cmd.angular_z != 0.0

    def test_navigation_stops_when_no_target(self, message_bus):
        """Test that navigation sends stop command when no target detected."""
        # Create navigation agent
        agent = NavigationAgent(message_bus, update_rate=10.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Publish robot pose
        pose_msg = RobotPoseMessage(
            source_agent="test",
            x=0.0,
            y=0.0,
            theta=0.0
        )
        message_bus.publish(MessageType.ROBOT_POSE, pose_msg)

        # Publish detection with no target
        detection_msg = PersonDetectionMessage(
            source_agent="test",
            target_id=None
        )
        message_bus.publish(MessageType.PERSON_DETECTION, detection_msg)

        # Start agent and let it process
        agent.start()
        time.sleep(0.2)
        agent.stop()

        # Verify stop command was sent
        assert len(received_commands) > 0
        cmd = received_commands[-1]
        assert cmd.linear_x == 0.0
        assert cmd.angular_z == 0.0

    def test_multiple_people_target_selection(self, message_bus, mock_camera):
        """Test target selection with multiple people in scene."""
        # Create perception agent
        with patch('cv2.VideoCapture', return_value=mock_camera):
            agent = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock detector to return multiple detections
            detections = [
                Detection(bbox=(100, 100, 200, 200), confidence=0.9, class_id=0),
                Detection(bbox=(300, 100, 400, 200), confidence=0.85, class_id=0),
                Detection(bbox=(500, 100, 600, 200), confidence=0.8, class_id=0),
            ]
            agent.detector.detect = Mock(return_value=detections)

            # Mock tracker to return multiple tracks
            tracks = [
                Track(track_id=1, bbox=(100, 100, 200, 200), confidence=0.9,
                      distance=2.0, angle=-10.0, velocity=(0.0, 0.0)),
                Track(track_id=2, bbox=(300, 100, 400, 200), confidence=0.85,
                      distance=3.0, angle=0.0, velocity=(0.0, 0.0)),
                Track(track_id=3, bbox=(500, 100, 600, 200), confidence=0.8,
                      distance=4.0, angle=15.0, velocity=(0.0, 0.0)),
            ]
            agent.tracker.update = Mock(return_value=tracks)

            # Target selector should pick closest in FOV
            agent.target_selector.select_target = Mock(return_value=tracks[0])

            # Subscribe to messages
            received_messages = []
            def callback(msg):
                received_messages.append(msg)

            message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

            # Start agent
            agent.start()
            time.sleep(0.2)
            agent.stop()

            # Verify correct target was selected
            assert len(received_messages) > 0
            msg = received_messages[0]
            assert msg.target_id == 1
            assert msg.distance == 2.0

    def test_end_to_end_perception_to_navigation(self, message_bus, mock_camera):
        """Test complete flow from perception through navigation."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock perception components
            mock_track = Track(
                track_id=1,
                bbox=(100, 100, 200, 200),
                confidence=0.9,
                distance=2.5,
                angle=5.0,
                velocity=(0.0, 0.0)
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(100, 100, 200, 200), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=10.0)
        navigation = NavigationAgent(message_bus, update_rate=10.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Start all agents
        localization.start()
        perception.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        perception.stop()
        localization.stop()

        # Verify motion commands were generated
        assert len(received_commands) > 0

        # Verify commands are reasonable
        for cmd in received_commands:
            assert isinstance(cmd, MotionCommandMessage)
            assert -1.0 <= cmd.linear_x <= 1.0
            assert -2.0 <= cmd.angular_z <= 2.0

    def test_message_ordering_and_timestamps(self, message_bus):
        """Test that messages have correct ordering and timestamps."""
        received_messages = []

        def callback(msg):
            received_messages.append(msg)

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Publish multiple messages
        for i in range(5):
            msg = PersonDetectionMessage(
                source_agent="test",
                target_id=i
            )
            message_bus.publish(MessageType.PERSON_DETECTION, msg)
            time.sleep(0.01)

        # Verify ordering
        assert len(received_messages) == 5
        for i in range(5):
            assert received_messages[i].target_id == i
            assert received_messages[i].sequence_number == i + 1

        # Verify timestamps are increasing
        for i in range(1, 5):
            assert received_messages[i].timestamp >= received_messages[i-1].timestamp
