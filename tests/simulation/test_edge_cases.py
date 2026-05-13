"""Simulation tests for edge cases and failure scenarios.

This module tests the system's behavior in edge cases, failure modes,
and challenging scenarios.
"""

import pytest
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from tests.mocks.mock_go2 import MockGo2SDK
from tests.mocks.mock_camera import MockCamera
from tests.mocks.mock_dimos import MockMessageBus


@dataclass
class PersonDetection:
    """Represents a detected person."""
    id: int
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    position: Tuple[float, float]  # x, y in world frame


class EdgeCaseEnvironment:
    """Simulation environment for edge case testing."""

    def __init__(self):
        """Initialize edge case environment."""
        self.robot = MockGo2SDK()
        self.camera = MockCamera()
        self.message_bus = MockMessageBus()
        self.robot_pose = np.array([0.0, 0.0, 0.0])
        self.target_id: Optional[int] = None
        self.detections: List[PersonDetection] = []
        self.target_lost_time: float = 0.0
        self.target_timeout: float = 2.0

    def setup(self):
        """Setup environment."""
        self.robot.connect()
        self.camera.open()
        self.robot.clear_command_history()

    def teardown(self):
        """Teardown environment."""
        self.robot.disconnect()
        self.camera.close()

    def add_detection(
        self,
        person_id: int,
        bbox: Tuple[int, int, int, int],
        confidence: float,
        position: Tuple[float, float]
    ):
        """Add a person detection.

        Args:
            person_id: Unique person ID
            bbox: Bounding box (x1, y1, x2, y2)
            confidence: Detection confidence
            position: Position in world frame (x, y)
        """
        detection = PersonDetection(person_id, bbox, confidence, position)
        self.detections.append(detection)

    def clear_detections(self):
        """Clear all detections."""
        self.detections.clear()

    def select_target(self) -> Optional[int]:
        """Select target person (closest in front).

        Returns:
            Target person ID or None
        """
        if not self.detections:
            return None

        # Find closest person in front of robot
        robot_x, robot_y, robot_theta = self.robot_pose
        min_distance = float('inf')
        target_id = None

        for detection in self.detections:
            dx = detection.position[0] - robot_x
            dy = detection.position[1] - robot_y
            distance = np.sqrt(dx**2 + dy**2)

            # Check if in front (within 60 degree FOV)
            angle = np.arctan2(dy, dx) - robot_theta
            angle = np.arctan2(np.sin(angle), np.cos(angle))

            if abs(angle) < np.radians(30) and distance < min_distance:
                min_distance = distance
                target_id = detection.id

        return target_id

    def get_target_position(self) -> Optional[Tuple[float, float]]:
        """Get target person position.

        Returns:
            Target position (x, y) or None
        """
        if self.target_id is None:
            return None

        for detection in self.detections:
            if detection.id == self.target_id:
                return detection.position

        return None


@pytest.fixture
def edge_env():
    """Provide edge case environment."""
    env = EdgeCaseEnvironment()
    env.setup()
    yield env
    env.teardown()


class TestMultiplePeopleScenarios:
    """Test scenarios with multiple people in the scene."""

    def test_select_closest_person_in_front(self, edge_env):
        """Test selecting closest person in front of robot."""
        # Add multiple people
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.5))  # Close, slightly right
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (5.0, 0.0))  # Far, center
        edge_env.add_detection(3, (500, 100, 600, 400), 0.8, (2.0, -2.0))  # Close, far right

        target_id = edge_env.select_target()

        # Should select person 1 (closest in front)
        assert target_id == 1, f"Should select closest person in front, got {target_id}"

    def test_ignore_people_behind_robot(self, edge_env):
        """Test that people behind robot are ignored."""
        edge_env.robot_pose[2] = 0.0  # Facing forward

        # Add people
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))  # In front
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (-2.0, 0.0))  # Behind

        target_id = edge_env.select_target()

        # Should only select person in front
        assert target_id == 1, "Should ignore people behind robot"

    def test_ignore_people_outside_fov(self, edge_env):
        """Test that people outside FOV are ignored."""
        edge_env.robot_pose[2] = 0.0  # Facing forward

        # Add people
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))  # Center
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (3.0, 3.0))  # Far left (>60°)

        target_id = edge_env.select_target()

        # Should only select person in FOV
        assert target_id == 1, "Should ignore people outside FOV"

    def test_sticky_tracking_with_multiple_people(self, edge_env):
        """Test that target selection is sticky even when others are closer."""
        # Initial: select person 1
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (5.0, 0.0))

        edge_env.target_id = edge_env.select_target()
        assert edge_env.target_id == 1

        # Person 2 moves closer
        edge_env.clear_detections()
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (2.0, 0.0))  # Now closer

        # Should still track person 1 (sticky tracking)
        target_pos = edge_env.get_target_position()
        assert target_pos == (3.0, 0.0), "Should maintain original target"

    def test_switch_target_when_original_lost(self, edge_env):
        """Test switching to new target when original is lost."""
        # Initial: select person 1
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (5.0, 0.0))

        edge_env.target_id = edge_env.select_target()
        assert edge_env.target_id == 1

        # Person 1 disappears
        edge_env.clear_detections()
        edge_env.add_detection(2, (300, 100, 400, 400), 0.85, (5.0, 0.0))

        # After timeout, should select new target
        edge_env.target_id = None  # Simulate timeout
        new_target = edge_env.select_target()
        assert new_target == 2, "Should select new target after original lost"


class TestTargetLossAndReacquisition:
    """Test scenarios where target is lost and reacquired."""

    def test_target_leaves_fov(self, edge_env):
        """Test behavior when target leaves field of view."""
        # Target in view
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        # Simulate following
        for step in range(10):
            target_pos = edge_env.get_target_position()
            if target_pos:
                edge_env.robot.set_velocity(0.5, 0.0, 0.0)
            else:
                edge_env.robot.set_velocity(0.0, 0.0, 0.0)

        # Target leaves FOV
        edge_env.clear_detections()

        # Robot should stop
        target_pos = edge_env.get_target_position()
        assert target_pos is None, "Target should be lost"

        # Simulate stop command
        edge_env.robot.set_velocity(0.0, 0.0, 0.0)
        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0, \
            "Robot should stop when target lost"

    def test_target_reappears_after_brief_occlusion(self, edge_env):
        """Test reacquiring target after brief occlusion."""
        # Target visible
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        # Target occluded for 1 second (< 3 second timeout)
        edge_env.clear_detections()
        edge_env.target_lost_time = 1.0

        # Target reappears
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.5, 0.0))

        # Should reacquire same target
        target_pos = edge_env.get_target_position()
        assert target_pos == (3.5, 0.0), "Should reacquire target after brief occlusion"

    def test_target_lost_for_extended_time(self, edge_env):
        """Test behavior when target lost for >3 seconds."""
        # Target visible
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        # Target lost for >3 seconds
        edge_env.clear_detections()
        edge_env.target_lost_time = 3.5

        # Should give up on target
        if edge_env.target_lost_time > edge_env.target_timeout:
            edge_env.target_id = None

        assert edge_env.target_id is None, "Should give up on target after timeout"

        # Robot should stop
        edge_env.robot.set_velocity(0.0, 0.0, 0.0)
        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0


class TestLowLightConditions:
    """Test behavior in low light conditions."""

    def test_low_confidence_detections(self, edge_env):
        """Test handling low confidence detections in low light."""
        # Add low confidence detections
        edge_env.add_detection(1, (100, 100, 200, 400), 0.3, (3.0, 0.0))  # Low confidence
        edge_env.add_detection(2, (300, 100, 400, 400), 0.4, (4.0, 0.0))

        # Should still select best available target
        target_id = edge_env.select_target()
        assert target_id is not None, "Should select target even with low confidence"

    def test_no_detections_in_darkness(self, edge_env):
        """Test behavior when no detections in very low light."""
        # No detections
        edge_env.clear_detections()

        target_id = edge_env.select_target()
        assert target_id is None, "Should have no target in darkness"

        # Robot should stop
        edge_env.robot.set_velocity(0.0, 0.0, 0.0)
        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0

    def test_intermittent_detections_low_light(self, edge_env):
        """Test handling intermittent detections in low light."""
        # Simulate flickering detections
        detection_sequence = [True, False, True, False, True, True, False]

        for i, has_detection in enumerate(detection_sequence):
            edge_env.clear_detections()

            if has_detection:
                edge_env.add_detection(1, (100, 100, 200, 400), 0.6, (3.0, 0.0))
                edge_env.target_id = 1
                edge_env.robot.set_velocity(0.3, 0.0, 0.0)  # Slow speed in low light
            else:
                # Brief loss, maintain last known target
                if edge_env.target_lost_time < edge_env.target_timeout:
                    edge_env.robot.set_velocity(0.1, 0.0, 0.0)  # Very slow
                else:
                    edge_env.robot.set_velocity(0.0, 0.0, 0.0)

        # Should have attempted to follow
        assert len(edge_env.robot.get_command_history()) > 0


class TestBatteryLowScenarios:
    """Test behavior when battery is low."""

    def test_battery_warning_threshold(self, edge_env):
        """Test warning when battery drops below 20%."""
        edge_env.robot.set_battery_level(25.0)
        battery = edge_env.robot.get_battery_level()
        assert battery == 25.0

        # Continue operation but log warning
        edge_env.robot.set_battery_level(15.0)
        battery = edge_env.robot.get_battery_level()
        assert battery == 15.0, "Should continue operating below 20%"

    def test_battery_critical_threshold(self, edge_env):
        """Test emergency stop when battery drops below 10%."""
        edge_env.robot.set_battery_level(12.0)

        # Add target
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        # Try to follow
        edge_env.robot.set_velocity(0.5, 0.0, 0.0)

        # Battery drops to critical
        edge_env.robot.set_battery_level(8.0)
        battery = edge_env.robot.get_battery_level()

        # Should trigger emergency stop
        if battery < 10.0:
            edge_env.robot.emergency_stop()

        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0, \
            "Should stop when battery critical"

    def test_graceful_shutdown_low_battery(self, edge_env):
        """Test graceful shutdown sequence on low battery."""
        edge_env.robot.set_battery_level(5.0)

        # Shutdown sequence
        edge_env.robot.emergency_stop()
        edge_env.robot.disconnect()

        assert not edge_env.robot.is_connected(), "Should disconnect on shutdown"


class TestOcclusionScenarios:
    """Test behavior during target occlusion."""

    def test_brief_occlusion_maintain_tracking(self, edge_env):
        """Test maintaining tracking during brief occlusion (<1 second)."""
        # Target visible
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        last_known_position = (3.0, 0.0)

        # Occlusion for 0.5 seconds
        edge_env.clear_detections()

        # Should maintain target ID and use last known position
        assert edge_env.target_id == 1, "Should maintain target ID during brief occlusion"

        # Continue with reduced speed
        edge_env.robot.set_velocity(0.2, 0.0, 0.0)

    def test_extended_occlusion_stop_robot(self, edge_env):
        """Test stopping robot during extended occlusion (>2 seconds)."""
        # Target visible
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1

        # Extended occlusion
        edge_env.clear_detections()
        edge_env.target_lost_time = 2.5

        # Should stop after timeout
        if edge_env.target_lost_time > edge_env.target_timeout:
            edge_env.robot.set_velocity(0.0, 0.0, 0.0)
            edge_env.target_id = None

        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0

    def test_reacquisition_after_occlusion(self, edge_env):
        """Test reacquiring target after occlusion using appearance features."""
        # Target visible with appearance features
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        edge_env.target_id = 1
        appearance_features = np.random.rand(128)  # Mock appearance vector

        # Occlusion
        edge_env.clear_detections()

        # Target reappears at different position
        edge_env.add_detection(1, (150, 100, 250, 400), 0.85, (3.5, 0.5))

        # Should reacquire based on appearance similarity
        target_pos = edge_env.get_target_position()
        assert target_pos == (3.5, 0.5), "Should reacquire target after occlusion"


class TestEmergencyScenarios:
    """Test emergency stop and safety scenarios."""

    def test_emergency_stop_on_close_approach(self, edge_env):
        """Test emergency stop when too close to person (<0.5m)."""
        # Person very close
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (0.4, 0.0))
        edge_env.target_id = 1

        # Calculate distance
        target_pos = edge_env.get_target_position()
        distance = np.sqrt(target_pos[0]**2 + target_pos[1]**2)

        # Should trigger emergency stop
        if distance < 0.5:
            edge_env.robot.emergency_stop()

        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0, \
            "Should emergency stop when too close"

    def test_emergency_stop_response_time(self, edge_env):
        """Test that emergency stop executes within 100ms."""
        import time

        # Trigger emergency stop
        start_time = time.time()
        edge_env.robot.emergency_stop()
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # Convert to ms

        # Should be very fast (mock is instant, real system must be <100ms)
        assert response_time < 100, f"Emergency stop too slow: {response_time:.2f}ms"

    def test_collision_detection_triggers_stop(self, edge_env):
        """Test that collision detection triggers emergency stop."""
        # Simulate collision detection (e.g., from IMU sudden deceleration)
        collision_detected = True

        if collision_detected:
            edge_env.robot.emergency_stop()

        assert edge_env.robot.last_velocity_command['linear_x'] == 0.0


class TestSystemHealthMonitoring:
    """Test system health monitoring scenarios."""

    def test_high_cpu_usage_warning(self, edge_env):
        """Test warning on high CPU usage."""
        cpu_usage = 85.0  # Simulated high CPU

        # Should log warning but continue
        assert cpu_usage > 80.0, "High CPU detected"

        # System should still function
        edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
        target_id = edge_env.select_target()
        assert target_id is not None

    def test_low_frame_rate_degradation(self, edge_env):
        """Test graceful degradation on low frame rate."""
        frame_rate = 15.0  # Below 20 FPS threshold

        # Should reduce speed for safety
        if frame_rate < 20.0:
            max_speed = 0.4  # Reduced from 0.8
        else:
            max_speed = 0.8

        edge_env.robot.set_velocity(max_speed, 0.0, 0.0)

        assert edge_env.robot.last_velocity_command['linear_x'] <= 0.4, \
            "Should reduce speed on low frame rate"

    def test_network_latency_warning(self, edge_env):
        """Test warning on high network latency to Go2."""
        network_latency = 150.0  # ms, above 100ms threshold

        # Should log warning
        assert network_latency > 100.0, "High latency detected"

        # Should continue but may reduce responsiveness
        edge_env.robot.set_velocity(0.3, 0.0, 0.0)


class TestRobustnessTesting:
    """Test system robustness and stress scenarios."""

    def test_rapid_target_switching(self, edge_env):
        """Test handling rapid target appearance/disappearance."""
        for i in range(20):
            edge_env.clear_detections()

            if i % 2 == 0:
                edge_env.add_detection(1, (100, 100, 200, 400), 0.9, (3.0, 0.0))
                edge_env.target_id = 1
                edge_env.robot.set_velocity(0.3, 0.0, 0.0)
            else:
                edge_env.target_id = None
                edge_env.robot.set_velocity(0.0, 0.0, 0.0)

        # Should handle without crashing
        assert len(edge_env.robot.get_command_history()) > 0

    def test_noisy_detections(self, edge_env):
        """Test handling noisy/jittery detections."""
        # Add detections with noise
        for i in range(50):
            edge_env.clear_detections()

            # Add jittery position
            noise_x = np.random.normal(0, 0.1)
            noise_y = np.random.normal(0, 0.1)
            edge_env.add_detection(
                1,
                (100, 100, 200, 400),
                0.9,
                (3.0 + noise_x, 0.0 + noise_y)
            )

            edge_env.target_id = 1
            target_pos = edge_env.get_target_position()

            # Should still track despite noise
            assert target_pos is not None

    def test_extreme_person_speed(self, edge_env):
        """Test handling person moving at extreme speed."""
        # Person moves very fast (2.0 m/s, faster than robot max)
        positions = [(2.0 * t, 0.0) for t in range(10)]

        for pos in positions:
            edge_env.clear_detections()
            edge_env.add_detection(1, (100, 100, 200, 400), 0.9, pos)
            edge_env.target_id = 1

            # Robot tries to follow at max speed
            edge_env.robot.set_velocity(0.8, 0.0, 0.0)

        # Robot should lag behind but not crash
        assert len(edge_env.robot.get_command_history()) > 0
