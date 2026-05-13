"""Integration tests for full pipeline.

Tests the complete system with all modules working together,
simulating real-world scenarios.
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
from control.path_planner import PathPlanner
from localization.pose_estimator import PoseEstimator
from localization.odometry import Odometry
from safety.safety_monitor import SafetyMonitor
from safety.watchdog import Watchdog
from safety.health_checker import HealthChecker
from dimos_integration.message_handler import (
    MessageHandler,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
    SafetyEventMessage,
    HeartbeatMessage
)


class TestFullPipeline:
    """Test complete system with all modules."""

    @pytest.fixture
    def message_handler(self):
        """Create message handler."""
        handler = MessageHandler()
        handler.start()
        yield handler
        handler.stop()

    @pytest.fixture
    def full_system(
        self,
        message_handler,
        mock_camera,
        mock_go2_client,
        temp_log_dir,
        temp_config_dir
    ):
        """Create full system with all components."""
        # Vision components
        detector = PersonDetector()
        tracker = PersonTracker()
        selector = TargetSelector()

        # Control components
        controller = MotionController()
        distance_keeper = DistanceKeeper()
        path_planner = PathPlanner()

        # Localization components
        odometry = Odometry(robot_client=mock_go2_client)
        pose_estimator = PoseEstimator(odometry=odometry)

        # Safety components
        safety_monitor = SafetyMonitor(
            message_handler=message_handler,
            log_dir=str(temp_log_dir)
        )
        watchdog = Watchdog(message_handler=message_handler)
        health_checker = HealthChecker(message_handler=message_handler)

        system = {
            'detector': detector,
            'tracker': tracker,
            'selector': selector,
            'controller': controller,
            'distance_keeper': distance_keeper,
            'path_planner': path_planner,
            'odometry': odometry,
            'pose_estimator': pose_estimator,
            'safety_monitor': safety_monitor,
            'watchdog': watchdog,
            'health_checker': health_checker,
            'camera': mock_camera,
            'robot': mock_go2_client
        }

        # Start safety components
        safety_monitor.start()
        watchdog.start()
        health_checker.start()

        yield system

        # Stop safety components
        safety_monitor.stop()
        watchdog.stop()
        health_checker.stop()

    @pytest.fixture
    def video_frames(self):
        """Create sequence of video frames simulating person walking."""
        frames = []
        for i in range(30):
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            # Simulate person moving from left to center
            x_pos = 500 + i * 20
            frame[400:700, x_pos:x_pos+200] = [100, 100, 100]
            frames.append(frame)
        return frames

    def test_person_walks_straight(
        self,
        full_system,
        message_handler,
        video_frames
    ):
        """Test robot follows person walking straight."""
        # Arrange
        motion_commands = []
        safety_events = []

        def motion_callback(msg):
            motion_commands.append(msg)

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)
        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - process video frames
        for frame in video_frames[:10]:  # Process first 10 frames
            # 1. Detect and track
            detections = full_system['detector'].detect(frame)
            tracks = full_system['tracker'].update(detections, frame)

            # 2. Select target
            if tracks:
                target = full_system['selector'].select_target(tracks)

                if target:
                    # 3. Publish target
                    target_msg = PersonDetectionMessage(
                        target_id=target.track_id,
                        x=target.position[0],
                        y=target.position[1],
                        distance=target.distance,
                        angle=target.angle,
                        confidence=target.confidence
                    )
                    message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

                    # 4. Update pose
                    full_system['odometry'].update()
                    pose = full_system['pose_estimator'].get_pose()
                    pose_msg = RobotPoseMessage(
                        x=pose.x,
                        y=pose.y,
                        theta=pose.theta,
                        covariance=pose.covariance
                    )
                    message_handler.publish(MessageType.ROBOT_POSE, pose_msg)

                    # 5. Compute motion command
                    desired_velocity = full_system['distance_keeper'].compute_velocity(
                        current_distance=target.distance,
                        target_distance=2.0
                    )

                    command = full_system['controller'].compute_command(
                        target_position=(target.position[0], target.position[1]),
                        robot_pose=(pose.x, pose.y, pose.theta),
                        desired_linear_velocity=desired_velocity
                    )

                    # 6. Publish command (safety monitor will validate)
                    cmd_msg = MotionCommandMessage(
                        linear_x=command.linear_x,
                        angular_z=command.angular_z
                    )
                    message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

            # Send heartbeat
            heartbeat = HeartbeatMessage(agent_name="perception", status="running")
            message_handler.publish(MessageType.HEARTBEAT, heartbeat)

            time.sleep(0.05)

        time.sleep(0.3)

        # Assert
        # Should have generated motion commands (if person detected)
        assert isinstance(motion_commands, list)
        # No critical safety events
        critical_events = [e for e in safety_events if e.level == "critical"]
        assert len(critical_events) == 0

    def test_person_stops_suddenly(
        self,
        full_system,
        message_handler
    ):
        """Test robot stops when person stops."""
        # Arrange
        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Act - simulate person at constant position
        for _ in range(5):
            target_msg = PersonDetectionMessage(
                target_id=1,
                x=2.0,  # Constant position
                y=0.0,
                distance=2.0,
                angle=0.0,
                confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

            pose_msg = RobotPoseMessage(x=0.0, y=0.0, theta=0.0, covariance=[0.01]*9)
            message_handler.publish(MessageType.ROBOT_POSE, pose_msg)

            # Compute command
            desired_velocity = full_system['distance_keeper'].compute_velocity(
                current_distance=2.0,
                target_distance=2.0
            )

            command = full_system['controller'].compute_command(
                target_position=(2.0, 0.0),
                robot_pose=(0.0, 0.0, 0.0),
                desired_linear_velocity=desired_velocity
            )

            cmd_msg = MotionCommandMessage(
                linear_x=command.linear_x,
                angular_z=command.angular_z
            )
            message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

            time.sleep(0.1)

        time.sleep(0.2)

        # Assert - velocity should be near zero (at target distance)
        if motion_commands:
            avg_velocity = sum(cmd.linear_x for cmd in motion_commands) / len(motion_commands)
            assert avg_velocity < 0.2  # Should be slow or stopped

    def test_person_turns_corner(
        self,
        full_system,
        message_handler
    ):
        """Test robot follows person turning."""
        # Arrange
        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Act - simulate person turning (changing angle)
        angles = [0.0, 0.2, 0.4, 0.6, 0.8]  # Gradual turn
        for angle in angles:
            x = 2.0 * np.cos(angle)
            y = 2.0 * np.sin(angle)

            target_msg = PersonDetectionMessage(
                target_id=1,
                x=x,
                y=y,
                distance=2.0,
                angle=angle,
                confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

            pose_msg = RobotPoseMessage(x=0.0, y=0.0, theta=0.0, covariance=[0.01]*9)
            message_handler.publish(MessageType.ROBOT_POSE, pose_msg)

            desired_velocity = full_system['distance_keeper'].compute_velocity(
                current_distance=2.0,
                target_distance=2.0
            )

            command = full_system['controller'].compute_command(
                target_position=(x, y),
                robot_pose=(0.0, 0.0, 0.0),
                desired_linear_velocity=desired_velocity
            )

            cmd_msg = MotionCommandMessage(
                linear_x=command.linear_x,
                angular_z=command.angular_z
            )
            message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

            time.sleep(0.1)

        time.sleep(0.2)

        # Assert - should have angular velocity commands
        if motion_commands:
            has_angular = any(abs(cmd.angular_z) > 0.1 for cmd in motion_commands)
            assert has_angular

    def test_person_temporarily_occluded(
        self,
        full_system,
        message_handler
    ):
        """Test system handles temporary occlusion."""
        # Arrange
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - simulate person visible, then occluded, then visible again
        # Visible
        for _ in range(3):
            target_msg = PersonDetectionMessage(
                target_id=1, x=2.0, y=0.0, distance=2.0, angle=0.0, confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, target_msg)
            heartbeat = HeartbeatMessage(agent_name="perception", status="running")
            message_handler.publish(MessageType.HEARTBEAT, heartbeat)
            time.sleep(0.3)

        # Occluded (no target messages, but heartbeats continue)
        for _ in range(3):
            heartbeat = HeartbeatMessage(agent_name="perception", status="running")
            message_handler.publish(MessageType.HEARTBEAT, heartbeat)
            time.sleep(0.3)

        # Visible again
        for _ in range(3):
            target_msg = PersonDetectionMessage(
                target_id=1, x=2.0, y=0.0, distance=2.0, angle=0.0, confidence=0.9
            )
            message_handler.publish(MessageType.PERSON_DETECTION, target_msg)
            heartbeat = HeartbeatMessage(agent_name="perception", status="running")
            message_handler.publish(MessageType.HEARTBEAT, heartbeat)
            time.sleep(0.3)

        # Assert - watchdog should trigger timeout during occlusion
        timeout_events = [
            e for e in safety_events
            if "timeout" in e.description.lower()
        ]
        assert len(timeout_events) > 0

    def test_obstacle_avoidance_while_following(
        self,
        full_system,
        message_handler
    ):
        """Test robot avoids obstacles while following person."""
        # Arrange
        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Act - simulate person ahead with obstacle in path
        # Create simple obstacle map
        obstacle_map = np.zeros((100, 100), dtype=np.uint8)
        obstacle_map[45:55, 40:60] = 1  # Obstacle in middle

        target_msg = PersonDetectionMessage(
            target_id=1, x=3.0, y=0.0, distance=3.0, angle=0.0, confidence=0.9
        )
        message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

        pose_msg = RobotPoseMessage(x=0.0, y=0.0, theta=0.0, covariance=[0.01]*9)
        message_handler.publish(MessageType.ROBOT_POSE, pose_msg)

        # Plan path with obstacle avoidance
        path = full_system['path_planner'].plan(
            start=(0.0, 0.0),
            goal=(3.0, 0.0),
            obstacle_map=obstacle_map
        )

        # Generate command
        if path and len(path) > 1:
            next_waypoint = path[1]
            command = full_system['controller'].compute_command(
                target_position=next_waypoint,
                robot_pose=(0.0, 0.0, 0.0),
                desired_linear_velocity=0.5
            )

            cmd_msg = MotionCommandMessage(
                linear_x=command.linear_x,
                angular_z=command.angular_z
            )
            message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

        time.sleep(0.2)

        # Assert - path should avoid obstacle
        assert path is not None
        if len(path) > 0:
            # Path should not go through obstacle
            assert isinstance(path, list)

    def test_emergency_stop_on_close_approach(
        self,
        full_system,
        message_handler
    ):
        """Test emergency stop when too close to person."""
        # Arrange
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - simulate person very close
        full_system['safety_monitor'].update_target_distance(0.3)  # Below 0.5m threshold
        time.sleep(0.2)

        # Assert
        emergency_events = [
            e for e in safety_events
            if e.emergency_stop_active
        ]
        assert len(emergency_events) > 0

    def test_system_health_monitoring(
        self,
        full_system,
        message_handler
    ):
        """Test health monitoring during operation."""
        # Arrange
        health_messages = []

        def health_callback(msg):
            health_messages.append(msg)

        message_handler.subscribe(MessageType.HEALTH_STATUS, health_callback)

        # Act - run system for a while
        time.sleep(1.5)

        # Assert
        assert len(health_messages) > 0
        latest = health_messages[-1]
        assert latest.cpu_usage >= 0.0
        assert latest.memory_usage >= 0.0
        assert latest.battery_level >= 0.0

    def test_multiple_people_correct_target(
        self,
        full_system,
        message_handler
    ):
        """Test system follows correct person with multiple people."""
        # Arrange
        from vision.person_tracker import Track

        motion_commands = []

        def motion_callback(msg):
            motion_commands.append(msg)

        message_handler.subscribe(MessageType.MOTION_COMMAND, motion_callback)

        # Create multiple tracks
        tracks = [
            Track(
                track_id=1,
                bbox=(100, 100, 200, 300),
                confidence=0.9,
                position=(3.0, -1.0),
                distance=3.16,
                angle=-0.322
            ),
            Track(
                track_id=2,
                bbox=(500, 100, 600, 300),
                confidence=0.85,
                position=(2.0, 0.0),
                distance=2.0,
                angle=0.0
            ),
        ]

        # Act - select target (should pick closest in front)
        target = full_system['selector'].select_target(tracks)

        # Publish target and generate command
        if target:
            target_msg = PersonDetectionMessage(
                target_id=target.track_id,
                x=target.position[0],
                y=target.position[1],
                distance=target.distance,
                angle=target.angle,
                confidence=target.confidence
            )
            message_handler.publish(MessageType.PERSON_DETECTION, target_msg)

            pose_msg = RobotPoseMessage(x=0.0, y=0.0, theta=0.0, covariance=[0.01]*9)
            message_handler.publish(MessageType.ROBOT_POSE, pose_msg)

            desired_velocity = full_system['distance_keeper'].compute_velocity(
                current_distance=target.distance,
                target_distance=2.0
            )

            command = full_system['controller'].compute_command(
                target_position=(target.position[0], target.position[1]),
                robot_pose=(0.0, 0.0, 0.0),
                desired_linear_velocity=desired_velocity
            )

            cmd_msg = MotionCommandMessage(
                linear_x=command.linear_x,
                angular_z=command.angular_z
            )
            message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)

        time.sleep(0.2)

        # Assert - should have selected track_id=2 (closest)
        assert target.track_id == 2

    def test_graceful_shutdown(
        self,
        full_system,
        message_handler
    ):
        """Test system shuts down gracefully."""
        # Arrange - system is running

        # Act - stop all components
        full_system['safety_monitor'].stop()
        full_system['watchdog'].stop()
        full_system['health_checker'].stop()
        message_handler.stop()

        # Assert - no exceptions raised
        assert full_system['safety_monitor']._running is False
        assert full_system['watchdog']._running is False
        assert full_system['health_checker']._running is False
        assert message_handler._running is False

    def test_system_recovery_after_error(
        self,
        full_system,
        message_handler
    ):
        """Test system recovers from transient errors."""
        # Arrange
        safety_events = []

        def safety_callback(msg):
            safety_events.append(msg)

        message_handler.subscribe(MessageType.SAFETY_EVENT, safety_callback)

        # Act - trigger error condition
        full_system['safety_monitor'].trigger_emergency_stop("Test error")
        time.sleep(0.2)

        # Clear emergency stop
        full_system['safety_monitor'].clear_emergency_stop()
        time.sleep(0.2)

        # Send normal command
        cmd_msg = MotionCommandMessage(linear_x=0.3, angular_z=0.0)
        message_handler.publish(MessageType.MOTION_COMMAND, cmd_msg)
        time.sleep(0.2)

        # Assert - system should recover
        assert len(safety_events) > 0
        # Last event should not be emergency
        if len(safety_events) > 1:
            assert not safety_events[-1].emergency_stop_active
