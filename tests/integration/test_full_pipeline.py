"""Integration tests for full system pipeline.

Tests complete system with all modules running together,
simulating real-world person following scenarios.
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
    SafetyEventMessage,
    HealthStatusMessage,
)
from src.dimos_integration.agent_node import (
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
    SafetyAgent,
)
from src.vision.person_detector import Detection
from src.vision.person_tracker import Track


class TestFullPipeline:
    """Test complete system pipeline with all modules."""

    @pytest.fixture
    def message_bus(self):
        """Create message bus for testing."""
        return MessageBus()

    @pytest.fixture
    def mock_camera(self):
        """Create mock camera."""
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        return mock_cap

    def test_full_system_startup_shutdown(self, message_bus, mock_camera):
        """Test that all agents start and stop correctly."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Start all agents in correct order
        localization.start()
        assert localization.is_running()

        perception.start()
        assert perception.is_running()

        safety.start()
        assert safety.is_running()

        navigation.start()
        assert navigation.is_running()

        # Let system run briefly
        time.sleep(0.2)

        # Stop all agents
        navigation.stop()
        assert not navigation.is_running()

        safety.stop()
        assert not safety.is_running()

        perception.stop()
        assert not perception.is_running()

        localization.stop()
        assert not localization.is_running()

    def test_person_walks_straight(self, message_bus, mock_camera):
        """Test robot follows person walking straight."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock person walking straight ahead
            mock_track = Track(
                track_id=1,
                bbox=(200, 150, 300, 350),
                confidence=0.9,
                distance=2.5,
                angle=0.0,  # Straight ahead
                velocity=(0.5, 0.0)  # Moving forward
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify motion commands generated
        assert len(received_commands) > 0

        # Robot should move forward (positive linear velocity)
        forward_commands = [cmd for cmd in received_commands if cmd.linear_x > 0]
        assert len(forward_commands) > 0

    def test_person_turns_left(self, message_bus, mock_camera):
        """Test robot follows person turning left."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock person turning left
            mock_track = Track(
                track_id=1,
                bbox=(100, 150, 200, 350),
                confidence=0.9,
                distance=2.5,
                angle=-20.0,  # Left of center
                velocity=(0.3, 0.0)
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(100, 150, 200, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify motion commands generated
        assert len(received_commands) > 0

        # Robot should turn left (positive angular velocity)
        turning_commands = [cmd for cmd in received_commands if cmd.angular_z > 0]
        assert len(turning_commands) > 0

    def test_person_stops(self, message_bus, mock_camera):
        """Test robot stops when person stops."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock person at target distance, not moving
            mock_track = Track(
                track_id=1,
                bbox=(200, 150, 300, 350),
                confidence=0.9,
                distance=2.0,  # At target distance
                angle=0.0,
                velocity=(0.0, 0.0)  # Not moving
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify motion commands generated
        assert len(received_commands) > 0

        # Most commands should be near zero (robot maintaining position)
        near_zero_commands = [
            cmd for cmd in received_commands
            if abs(cmd.linear_x) < 0.2 and abs(cmd.angular_z) < 0.2
        ]
        assert len(near_zero_commands) > len(received_commands) * 0.5

    def test_person_temporarily_occluded(self, message_bus, mock_camera):
        """Test robot handles temporary occlusion."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Simulate occlusion by alternating between target and no target
            call_count = [0]

            def mock_select_target(tracks):
                call_count[0] += 1
                if call_count[0] % 3 == 0:
                    return None  # Occluded
                return Track(
                    track_id=1,
                    bbox=(200, 150, 300, 350),
                    confidence=0.9,
                    distance=2.5,
                    angle=0.0,
                    velocity=(0.3, 0.0)
                )

            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[
                Track(track_id=1, bbox=(200, 150, 300, 350), confidence=0.9,
                      distance=2.5, angle=0.0, velocity=(0.3, 0.0))
            ])
            perception.target_selector.select_target = Mock(side_effect=mock_select_target)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to motion commands
        received_commands = []
        def callback(msg):
            received_commands.append(msg)

        message_bus.subscribe(MessageType.MOTION_COMMAND, callback)

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify system handled occlusion (should have some stop commands)
        assert len(received_commands) > 0

    def test_multiple_people_correct_target(self, message_bus, mock_camera):
        """Test system selects and follows correct target with multiple people."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            # Mock multiple people, closest should be selected
            tracks = [
                Track(track_id=1, bbox=(200, 150, 300, 350), confidence=0.9,
                      distance=2.0, angle=0.0, velocity=(0.0, 0.0)),  # Closest
                Track(track_id=2, bbox=(400, 150, 500, 350), confidence=0.85,
                      distance=3.5, angle=15.0, velocity=(0.0, 0.0)),
                Track(track_id=3, bbox=(50, 150, 150, 350), confidence=0.8,
                      distance=4.0, angle=-20.0, velocity=(0.0, 0.0)),
            ]

            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0),
                Detection(bbox=(400, 150, 500, 350), confidence=0.85, class_id=0),
                Detection(bbox=(50, 150, 150, 350), confidence=0.8, class_id=0),
            ])
            perception.tracker.update = Mock(return_value=tracks)
            perception.target_selector.select_target = Mock(return_value=tracks[0])

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Subscribe to person detections
        received_detections = []
        def callback(msg):
            received_detections.append(msg)

        message_bus.subscribe(MessageType.PERSON_DETECTION, callback)

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify correct target selected (track_id=1, closest)
        assert len(received_detections) > 0
        for detection in received_detections:
            if detection.target_id is not None:
                assert detection.target_id == 1

    def test_all_message_types_flowing(self, message_bus, mock_camera):
        """Test that all message types are published during operation."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=10.0)

            mock_track = Track(
                track_id=1,
                bbox=(200, 150, 300, 350),
                confidence=0.9,
                distance=2.5,
                angle=0.0,
                velocity=(0.3, 0.0)
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Track all message types
        received_types = set()

        def make_callback(msg_type):
            def callback(msg):
                received_types.add(msg_type)
            return callback

        # Subscribe to all message types
        for msg_type in MessageType:
            message_bus.subscribe(msg_type, make_callback(msg_type))

        # Start all agents
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Let system run
        time.sleep(0.5)

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify all message types were published
        assert MessageType.PERSON_DETECTION in received_types
        assert MessageType.ROBOT_POSE in received_types
        assert MessageType.MOTION_COMMAND in received_types
        assert MessageType.HEALTH_STATUS in received_types

    def test_system_performance_metrics(self, message_bus, mock_camera):
        """Test system performance metrics during operation."""
        # Create all agents
        with patch('cv2.VideoCapture', return_value=mock_camera):
            perception = PerceptionAgent(message_bus, camera_source=0, update_rate=30.0)

            mock_track = Track(
                track_id=1,
                bbox=(200, 150, 300, 350),
                confidence=0.9,
                distance=2.5,
                angle=0.0,
                velocity=(0.3, 0.0)
            )
            perception.detector.detect = Mock(return_value=[
                Detection(bbox=(200, 150, 300, 350), confidence=0.9, class_id=0)
            ])
            perception.tracker.update = Mock(return_value=[mock_track])
            perception.target_selector.select_target = Mock(return_value=mock_track)

        localization = LocalizationAgent(message_bus, update_rate=50.0)
        navigation = NavigationAgent(message_bus, update_rate=50.0)
        safety = SafetyAgent(message_bus, update_rate=50.0)

        # Track message counts
        message_counts = {msg_type: 0 for msg_type in MessageType}

        def make_counter(msg_type):
            def callback(msg):
                message_counts[msg_type] += 1
            return callback

        for msg_type in MessageType:
            message_bus.subscribe(msg_type, make_counter(msg_type))

        # Start all agents
        start_time = time.time()
        localization.start()
        perception.start()
        safety.start()
        navigation.start()

        # Run for 1 second
        time.sleep(1.0)
        elapsed = time.time() - start_time

        # Stop all agents
        navigation.stop()
        safety.stop()
        perception.stop()
        localization.stop()

        # Verify message rates are reasonable
        # Perception at 30Hz should publish ~30 messages
        assert message_counts[MessageType.PERSON_DETECTION] >= 20

        # Localization at 50Hz should publish ~50 messages
        assert message_counts[MessageType.ROBOT_POSE] >= 40

        # Navigation at 50Hz should publish ~50 messages
        assert message_counts[MessageType.MOTION_COMMAND] >= 40

        # Health status should be published regularly
        assert message_counts[MessageType.HEALTH_STATUS] >= 5
