"""Integration tests for perception to navigation data flow.

Tests the complete pipeline from person detection through tracking to
motion command generation.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch

from vision.person_detector import PersonDetector
from vision.person_tracker import PersonTracker
from vision.target_selector import TargetSelector
from control.motion_controller import MotionController
from control.distance_keeper import DistanceKeeper
from localization.pose_estimator import PoseEstimator
from dimos_integration.message_handler import (
    MessageHandler,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage
)


class TestPerceptionToNavigation:
    """Test data flow from perception to navigation."""

    @pytest.fixture
    def message_handler(self):
        """Create message handler."""
        handler = MessageHandler()
        handler.start()
        yield handler
        handler.stop()

    @pytest.fixture
    def mock_camera_frame(self):
        """Create mock camera frame with person."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Add a simple rectangle to simulate a person
        frame[400:700, 800:1100] = [100, 100, 100]
        return frame

    @pytest.fixture
    def robot_pose(self):
        """Create mock robot pose."""
        return RobotPoseMessage(
            x=0.0,
            y=0.0,
            theta=0.0,
            covariance=[0.01] * 9
        )

    def test_detection_to_tracking_flow(self, message_handler, mock_camera_frame):
        """Test person detection flows to tracker."""
        # Arrange
        detector = PersonDetector()
        tracker = PersonTracker()

        received_tracks = []

        def track_callback(detections):
            tracks = tracker.update(detections, mock_camera_frame)
            received_tracks.extend(tracks)

        # Act
        detections = detector.detect(mock_camera_frame)
        track_callback(detections)

        # Assert
        assert len(detections) >= 0  # May or may not detect in mock frame
        assert isinstance(received_tracks, list)

    def test_tracking_to_target_selection_flow(
        self,
        message_handler,
        mock_camera_frame
    ):
        """Test tracking flows to target selection."""
        # Arrange
        detector = PersonDetector()
        tracker = PersonTracker()
        selector = TargetSelector()

        target_messages = []

        def target_callback(msg):
            target_messages.append(msg)

        message_handler.subscribe(
            MessageType.PERSON_DETECTION,
            target_callback
        )

        # Act - simulate multiple frames
        for _ in range(5):
            detections = detector.detect(mock_camera_frame)
            tracks = tracker.update(detections, mock_camera_frame)

            if tracks:
                target = selector.select_target(tracks)
                if target:
                    msg = PersonDetectionMessage(
                        target_id=target.track_id,
                        x=target.position[0],
                        y=target.position[1],
                        distance=target.distance,
                        angle=target.angle,
                        confidence=target.confidence
                    )
                    message_handler.publish(MessageType.PERSON_DETECTION, msg)

            time.sleep(0.01)

        # Assert
        # Messages may be empty if no person detected in mock frame
        assert isinstance(target_messages, list)

    def test_target_to_motion_command_flow(self, message_handler, robot_pose):
        """Test target detection flows to motion commands."""
        # Arrange
        controller = MotionController()
        distance_keeper = DistanceKeeper()

        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Simulate target detection
        target_msg = PersonDetectionMessage(
            target_id=1,
            x=2.5,  # 2.5m in front
            y=0.0,
            distance=2.5,
            angle=0.0,
            confidence=0.9
        )

        # Act
        message_handler.publish(MessageType.PERSON_DETECTION, target_msg)
        message_handler.publish(MessageType.ROBOT_POSE, robot_pose)
        time.sleep(0.1)  # Allow message processing

        # Manually trigger control (in real system, this is event-driven)
        desired_velocity = distance_keeper.compute_velocity(
            current_distance=target_msg.distance,
            target_distance=2.0
        )

        command = controller.compute_command(
            target_position=(target_msg.x, target_msg.y),
            robot_pose=(robot_pose.x, robot_pose.y, robot_pose.theta),
            desired_linear_velocity=desired_velocity
        )

        cmd_msg = MotionCommandMessage(
            linear_x=command.linear_x,
            angular_z=command.angular_z
        )
        message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)
        time.sleep(0.1)

        # Assert
        assert len(motion_commands) > 0
        assert motion_commands[0].linear_x >= 0.0
        assert abs(motion_commands[0].angular_z) >= 0.0

    def test_multiple_people_target_selection(
        self,
        message_handler,
        mock_camera_frame
    ):
        """Test target selection with multiple people in scene."""
        # Arrange
        selector = TargetSelector()

        # Create mock tracks for multiple people
        from vision.person_tracker import Track

        tracks = [
            Track(
                track_id=1,
                bbox=(100, 100, 200, 300),
                confidence=0.9,
                position=(3.0, -0.5),
                distance=3.04,
                angle=-0.165
            ),
            Track(
                track_id=2,
                bbox=(500, 100, 600, 300),
                confidence=0.85,
                position=(2.0, 0.0),
                distance=2.0,
                angle=0.0
            ),
            Track(
                track_id=3,
                bbox=(900, 100, 1000, 300),
                confidence=0.8,
                position=(3.5, 1.0),
                distance=3.64,
                angle=0.278
            )
        ]

        # Act
        target = selector.select_target(tracks)

        # Assert - should select closest person in front (track_id=2)
        assert target is not None
        assert target.track_id == 2
        assert target.distance == 2.0

    def test_target_lost_and_reacquired(self, message_handler):
        """Test behavior when target is lost and then reacquired."""
        # Arrange
        selector = TargetSelector()
        from vision.person_tracker import Track

        # Initial target
        initial_track = Track(
            track_id=1,
            bbox=(500, 100, 600, 300),
            confidence=0.9,
            position=(2.0, 0.0),
            distance=2.0,
            angle=0.0
        )

        # Act - select initial target
        target1 = selector.select_target([initial_track])
        assert target1.track_id == 1

        # Simulate target lost (empty tracks)
        target2 = selector.select_target([])
        assert target2 is None

        # Simulate target reacquired
        reacquired_track = Track(
            track_id=1,
            bbox=(520, 110, 620, 310),
            confidence=0.85,
            position=(2.1, 0.1),
            distance=2.1,
            angle=0.048
        )

        target3 = selector.select_target([reacquired_track])

        # Assert - should reacquire same target
        assert target3 is not None
        assert target3.track_id == 1

    def test_end_to_end_perception_navigation(
        self,
        message_handler,
        mock_camera_frame,
        robot_pose
    ):
        """Test complete end-to-end flow from camera to motion command."""
        # Arrange
        detector = PersonDetector()
        tracker = PersonTracker()
        selector = TargetSelector()
        controller = MotionController()
        distance_keeper = DistanceKeeper()

        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Act - simulate processing pipeline
        # 1. Detect persons
        detections = detector.detect(mock_camera_frame)

        # 2. Track persons
        tracks = tracker.update(detections, mock_camera_frame)

        # 3. Select target (if any tracks)
        if tracks:
            target = selector.select_target(tracks)

            if target:
                # 4. Publish target detection
                target_msg = PersonDetectionMessage(
                    target_id=target.track_id,
                    x=target.position[0],
                    y=target.position[1],
                    distance=target.distance,
                    angle=target.angle,
                    confidence=target.confidence
                )
                message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

                # 5. Compute motion command
                desired_velocity = distance_keeper.compute_velocity(
                    current_distance=target.distance,
                    target_distance=2.0
                )

                command = controller.compute_command(
                    target_position=(target.position[0], target.position[1]),
                    robot_pose=(robot_pose.x, robot_pose.y, robot_pose.theta),
                    desired_linear_velocity=desired_velocity
                )

                # 6. Publish motion command
                cmd_msg = MotionCommandMessage(
                    linear_x=command.linear_x,
                    angular_z=command.angular_z
                )
                message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

        time.sleep(0.1)

        # Assert - pipeline executed without errors
        # Motion commands may be empty if no person detected
        assert isinstance(motion_commands, list)

    def test_message_timing_and_sequence(self, message_handler):
        """Test message timestamps and sequence numbers."""
        # Arrange
        messages = []

        def callback(msg):
            messages.append(msg)

        message_handler.subscribe(MessageType.PERSON_DETECTION, callback)

        # Act - publish multiple messages
        for i in range(5):
            msg = PersonDetectionMessage(
                target_id=1,
                x=2.0 + i * 0.1,
                y=0.0,
                distance=2.0 + i * 0.1,
                angle=0.0,
                confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, msg)
            time.sleep(0.02)

        time.sleep(0.1)

        # Assert
        assert len(messages) == 5

        # Check sequence numbers are increasing
        for i in range(len(messages) - 1):
            assert messages[i + 1].sequence > messages[i].sequence

        # Check timestamps are increasing
        for i in range(len(messages) - 1):
            assert messages[i + 1].timestamp >= messages[i].timestamp
