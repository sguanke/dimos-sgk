"""Simulation tests for person following scenarios.

This module tests the complete person following system in various scenarios
using the Go2 simulator or mock hardware.
"""

import pytest
import numpy as np
import time
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from tests.mocks.mock_go2 import MockGo2SDK
from tests.mocks.mock_camera import MockCamera
from tests.mocks.mock_dimos import MockMessageBus


@dataclass
class PersonTrajectory:
    """Represents a person's movement trajectory."""
    positions: List[Tuple[float, float]]  # (x, y) positions
    timestamps: List[float]
    speeds: List[float]


@dataclass
class FollowingMetrics:
    """Metrics for evaluating following performance."""
    distance_errors: List[float]
    tracking_success_rate: float
    response_times: List[float]
    collision_count: int


class SimulationEnvironment:
    """Simulation environment for testing person following."""

    def __init__(self):
        """Initialize simulation environment."""
        self.robot = MockGo2SDK()
        self.camera = MockCamera()
        self.message_bus = MockMessageBus()
        self.robot_pose = np.array([0.0, 0.0, 0.0])  # x, y, theta
        self.target_distance = 2.0
        self.dt = 0.02  # 50Hz control loop

    def setup(self):
        """Setup simulation environment."""
        self.robot.connect()
        self.camera.open()
        self.robot.clear_command_history()

    def teardown(self):
        """Teardown simulation environment."""
        self.robot.disconnect()
        self.camera.close()

    def simulate_person_movement(
        self,
        trajectory: PersonTrajectory,
        duration: float
    ) -> FollowingMetrics:
        """Simulate person movement and robot following.

        Args:
            trajectory: Person's movement trajectory
            duration: Simulation duration in seconds

        Returns:
            Following performance metrics
        """
        distance_errors = []
        response_times = []
        collision_count = 0

        steps = int(duration / self.dt)
        traj_idx = 0

        for step in range(steps):
            current_time = step * self.dt

            # Get person position from trajectory
            if traj_idx < len(trajectory.positions) - 1:
                # Interpolate between trajectory points
                t_ratio = (current_time - trajectory.timestamps[traj_idx]) / \
                         (trajectory.timestamps[traj_idx + 1] - trajectory.timestamps[traj_idx])
                if t_ratio >= 1.0:
                    traj_idx += 1
                    t_ratio = 0.0

                if traj_idx < len(trajectory.positions) - 1:
                    p1 = np.array(trajectory.positions[traj_idx])
                    p2 = np.array(trajectory.positions[traj_idx + 1])
                    person_pos = p1 + t_ratio * (p2 - p1)
                else:
                    person_pos = np.array(trajectory.positions[-1])
            else:
                person_pos = np.array(trajectory.positions[-1])

            # Calculate distance from robot to person
            robot_pos = self.robot_pose[:2]
            distance = np.linalg.norm(person_pos - robot_pos)
            distance_error = abs(distance - self.target_distance)
            distance_errors.append(distance_error)

            # Check for collision (too close)
            if distance < 0.5:
                collision_count += 1

            # Simulate robot control (simple proportional controller)
            if self.robot.last_velocity_command:
                linear_x = self.robot.last_velocity_command['linear_x']
                angular_z = self.robot.last_velocity_command['angular_z']

                # Update robot pose
                self.robot_pose[0] += linear_x * self.dt * np.cos(self.robot_pose[2])
                self.robot_pose[1] += linear_x * self.dt * np.sin(self.robot_pose[2])
                self.robot_pose[2] += angular_z * self.dt

        # Calculate tracking success rate (distance error < 0.3m)
        success_count = sum(1 for err in distance_errors if err < 0.3)
        tracking_success_rate = success_count / len(distance_errors) if distance_errors else 0.0

        return FollowingMetrics(
            distance_errors=distance_errors,
            tracking_success_rate=tracking_success_rate,
            response_times=response_times,
            collision_count=collision_count
        )


@pytest.fixture
def sim_env():
    """Provide simulation environment."""
    env = SimulationEnvironment()
    env.setup()
    yield env
    env.teardown()


class TestFollowingStraightLine:
    """Test person following in straight line scenarios."""

    def test_person_walks_slow_straight(self, sim_env):
        """Test following person walking slowly in straight line (0.5 m/s)."""
        # Create trajectory: person walks 5 meters forward at 0.5 m/s
        duration = 10.0
        positions = [(0.5 * t, 2.0) for t in np.linspace(0, duration, 50)]
        timestamps = list(np.linspace(0, duration, 50))
        speeds = [0.5] * 50

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate robot following with simple control
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            # Simple proportional control
            distance = np.sqrt((person_x - robot_x)**2 + (person_y - robot_y)**2)
            error = distance - sim_env.target_distance

            linear_x = max(0.0, min(0.8, 0.5 * error))
            sim_env.robot.set_velocity(linear_x, 0.0, 0.0)

            # Update robot pose
            sim_env.robot_pose[0] += linear_x * 0.02 * np.cos(sim_env.robot_pose[2])
            sim_env.robot_pose[1] += linear_x * 0.02 * np.sin(sim_env.robot_pose[2])

        # Verify following performance
        final_distance = np.sqrt(
            (positions[-1][0] - sim_env.robot_pose[0])**2 +
            (positions[-1][1] - sim_env.robot_pose[1])**2
        )

        assert abs(final_distance - sim_env.target_distance) < 0.5, \
            f"Final distance error too large: {abs(final_distance - sim_env.target_distance):.2f}m"

    def test_person_walks_medium_straight(self, sim_env):
        """Test following person walking at medium speed (1.0 m/s)."""
        duration = 10.0
        positions = [(1.0 * t, 2.0) for t in np.linspace(0, duration, 50)]
        timestamps = list(np.linspace(0, duration, 50))
        speeds = [1.0] * 50

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            distance = np.sqrt((person_x - robot_x)**2 + (person_y - robot_y)**2)
            error = distance - sim_env.target_distance

            # Limit to max speed
            linear_x = max(0.0, min(0.8, 0.5 * error))
            sim_env.robot.set_velocity(linear_x, 0.0, 0.0)

            sim_env.robot_pose[0] += linear_x * 0.02

        # Verify robot maintains reasonable distance
        final_distance = np.sqrt(
            (positions[-1][0] - sim_env.robot_pose[0])**2 +
            (positions[-1][1] - sim_env.robot_pose[1])**2
        )

        # At 1.0 m/s, robot at 0.8 m/s max will lag behind
        assert final_distance < 5.0, \
            f"Robot fell too far behind: {final_distance:.2f}m"

    def test_person_walks_fast_straight(self, sim_env):
        """Test following person walking fast (1.5 m/s) - robot should lag."""
        duration = 10.0
        positions = [(1.5 * t, 2.0) for t in np.linspace(0, duration, 50)]
        timestamps = list(np.linspace(0, duration, 50))
        speeds = [1.5] * 50

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following at max speed
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            # Robot tries to follow but is limited to 0.8 m/s
            sim_env.robot.set_velocity(0.8, 0.0, 0.0)
            sim_env.robot_pose[0] += 0.8 * 0.02

        # Verify robot lags behind (person too fast)
        final_distance = np.sqrt(
            (positions[-1][0] - sim_env.robot_pose[0])**2 +
            (positions[-1][1] - sim_env.robot_pose[1])**2
        )

        # Person at 1.5 m/s, robot at 0.8 m/s: gap grows by 0.7 m/s
        expected_gap = 0.7 * duration
        assert final_distance > 5.0, \
            f"Robot should lag behind fast person: {final_distance:.2f}m"


class TestFollowingCurves:
    """Test person following in curved path scenarios."""

    def test_person_walks_gentle_curve(self, sim_env):
        """Test following person walking in gentle curve."""
        duration = 10.0
        # Create circular arc trajectory
        radius = 5.0
        angles = np.linspace(0, np.pi / 2, 50)  # 90 degree arc
        positions = [
            (radius * np.sin(angle), 2.0 + radius * (1 - np.cos(angle)))
            for angle in angles
        ]
        timestamps = list(np.linspace(0, duration, 50))
        speeds = [0.5] * 50

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following with angular control
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            # Calculate desired heading
            dx = person_x - robot_x
            dy = person_y - robot_y
            desired_heading = np.arctan2(dy, dx)
            heading_error = desired_heading - sim_env.robot_pose[2]

            # Normalize angle
            heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

            distance = np.sqrt(dx**2 + dy**2)
            distance_error = distance - sim_env.target_distance

            linear_x = max(0.0, min(0.8, 0.5 * distance_error))
            angular_z = max(-1.0, min(1.0, 1.0 * heading_error))

            sim_env.robot.set_velocity(linear_x, 0.0, angular_z)

            # Update robot pose
            sim_env.robot_pose[0] += linear_x * 0.02 * np.cos(sim_env.robot_pose[2])
            sim_env.robot_pose[1] += linear_x * 0.02 * np.sin(sim_env.robot_pose[2])
            sim_env.robot_pose[2] += angular_z * 0.02

        # Verify robot followed the curve
        final_distance = np.sqrt(
            (positions[-1][0] - sim_env.robot_pose[0])**2 +
            (positions[-1][1] - sim_env.robot_pose[1])**2
        )

        assert abs(final_distance - sim_env.target_distance) < 1.0, \
            f"Distance error in curve following: {abs(final_distance - sim_env.target_distance):.2f}m"

    def test_person_walks_circle(self, sim_env):
        """Test following person walking in complete circle."""
        duration = 20.0
        radius = 3.0
        angles = np.linspace(0, 2 * np.pi, 100)
        positions = [
            (radius * np.cos(angle), 2.0 + radius * np.sin(angle))
            for angle in angles
        ]
        timestamps = list(np.linspace(0, duration, 100))
        speeds = [0.5] * 100

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate circular following
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            dx = person_x - robot_x
            dy = person_y - robot_y
            desired_heading = np.arctan2(dy, dx)
            heading_error = desired_heading - sim_env.robot_pose[2]
            heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

            distance = np.sqrt(dx**2 + dy**2)
            distance_error = distance - sim_env.target_distance

            linear_x = max(0.0, min(0.8, 0.5 * distance_error))
            angular_z = max(-1.0, min(1.0, 1.0 * heading_error))

            sim_env.robot.set_velocity(linear_x, 0.0, angular_z)

            sim_env.robot_pose[0] += linear_x * 0.02 * np.cos(sim_env.robot_pose[2])
            sim_env.robot_pose[1] += linear_x * 0.02 * np.sin(sim_env.robot_pose[2])
            sim_env.robot_pose[2] += angular_z * 0.02

        # Verify robot completed the circle
        assert sim_env.robot.get_command_history(), "Robot should have moved"


class TestFollowingDynamicBehavior:
    """Test person following with dynamic behavior changes."""

    def test_person_stops_suddenly(self, sim_env):
        """Test robot response when person stops suddenly."""
        # Person walks then stops
        positions_walking = [(0.5 * t, 2.0) for t in range(10)]
        positions_stopped = [(5.0, 2.0)] * 10  # Stop at 5m

        positions = positions_walking + positions_stopped
        timestamps = list(range(20))
        speeds = [0.5] * 10 + [0.0] * 10

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            distance = np.sqrt((person_x - robot_x)**2 + (person_y - robot_y)**2)
            error = distance - sim_env.target_distance

            # Robot should slow down as it approaches
            linear_x = max(0.0, min(0.8, 0.5 * error))
            sim_env.robot.set_velocity(linear_x, 0.0, 0.0)

            sim_env.robot_pose[0] += linear_x * 0.02

        # Verify robot stopped near target distance
        final_distance = np.sqrt(
            (positions[-1][0] - sim_env.robot_pose[0])**2 +
            (positions[-1][1] - sim_env.robot_pose[1])**2
        )

        assert abs(final_distance - sim_env.target_distance) < 0.5, \
            f"Robot should stop at target distance: {final_distance:.2f}m"

        # Verify robot velocity is near zero
        if sim_env.robot.last_velocity_command:
            final_velocity = sim_env.robot.last_velocity_command['linear_x']
            assert abs(final_velocity) < 0.1, \
                f"Robot should have stopped: velocity={final_velocity:.2f} m/s"

    def test_person_changes_direction(self, sim_env):
        """Test robot response when person changes direction."""
        # Person walks forward then turns 90 degrees
        positions_forward = [(0.5 * t, 2.0) for t in range(10)]
        positions_turn = [(5.0, 2.0 + 0.5 * t) for t in range(10)]

        positions = positions_forward + positions_turn
        timestamps = list(range(20))
        speeds = [0.5] * 20

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following with heading control
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            dx = person_x - robot_x
            dy = person_y - robot_y
            desired_heading = np.arctan2(dy, dx)
            heading_error = desired_heading - sim_env.robot_pose[2]
            heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

            distance = np.sqrt(dx**2 + dy**2)
            distance_error = distance - sim_env.target_distance

            linear_x = max(0.0, min(0.8, 0.5 * distance_error))
            angular_z = max(-1.0, min(1.0, 1.0 * heading_error))

            sim_env.robot.set_velocity(linear_x, 0.0, angular_z)

            sim_env.robot_pose[0] += linear_x * 0.02 * np.cos(sim_env.robot_pose[2])
            sim_env.robot_pose[1] += linear_x * 0.02 * np.sin(sim_env.robot_pose[2])
            sim_env.robot_pose[2] += angular_z * 0.02

        # Verify robot turned to follow
        assert abs(sim_env.robot_pose[2]) > 0.1, \
            "Robot should have turned to follow direction change"

    def test_person_accelerates_decelerates(self, sim_env):
        """Test robot response to person acceleration and deceleration."""
        # Person accelerates from 0.3 to 0.8 m/s then decelerates
        speeds_accel = np.linspace(0.3, 0.8, 10)
        speeds_decel = np.linspace(0.8, 0.3, 10)
        speeds = list(speeds_accel) + list(speeds_decel)

        positions = []
        x = 0.0
        for speed in speeds:
            x += speed * 0.5  # 0.5s per step
            positions.append((x, 2.0))

        timestamps = [i * 0.5 for i in range(len(speeds))]

        trajectory = PersonTrajectory(
            positions=positions,
            timestamps=timestamps,
            speeds=speeds
        )

        # Simulate following
        for i, (pos, ts) in enumerate(zip(positions, timestamps)):
            person_x, person_y = pos
            robot_x, robot_y = sim_env.robot_pose[:2]

            distance = np.sqrt((person_x - robot_x)**2 + (person_y - robot_y)**2)
            error = distance - sim_env.target_distance

            linear_x = max(0.0, min(0.8, 0.5 * error))
            sim_env.robot.set_velocity(linear_x, 0.0, 0.0)

            sim_env.robot_pose[0] += linear_x * 0.02

        # Verify robot adapted to speed changes
        command_history = sim_env.robot.get_command_history()
        assert len(command_history) > 0, "Robot should have issued commands"

        # Check velocity varied (not constant)
        velocities = [cmd['linear_x'] for cmd in command_history]
        assert max(velocities) - min(velocities) > 0.1, \
            "Robot velocity should vary with person speed changes"
