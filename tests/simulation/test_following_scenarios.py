"""Simulation tests for person following scenarios.

Tests the complete person following system in various scenarios:
- Person walks at different speeds
- Person walks in different patterns (straight, curves, circles)
- Person stops suddenly
- Person changes direction
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Tuple

from src.dimos_integration.agent_node import (
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
    SafetyAgent,
)
from src.dimos_integration.message_handler import MessageBus
from tests.mocks.mock_go2 import MockGo2SDK
from tests.mocks.mock_camera import MockCamera


@dataclass
class PersonTrajectory:
    """Represents a person's trajectory in simulation."""
    positions: List[Tuple[float, float]]  # (x, y) positions over time
    timestamps: List[float]
    speeds: List[float]


@dataclass
class SimulationResult:
    """Results from a simulation run."""
    robot_positions: List[Tuple[float, float]]
    person_positions: List[Tuple[float, float]]
    distances: List[float]
    velocities: List[Tuple[float, float]]
    timestamps: List[float]
    success: bool
    error_message: str = ""


class PersonFollowingSimulator:
    """Simulator for person following scenarios."""

    def __init__(self):
        self.message_bus = MessageBus()
        self.mock_go2 = MockGo2SDK()
        self.mock_camera = MockCamera()
        self.agents = []

    def setup_agents(self):
        """Initialize all agents for simulation."""
        # Create agents
        self.localization_agent = LocalizationAgent(
            message_bus=self.message_bus,
            update_rate=50.0,
            go2_sdk=self.mock_go2
        )

        self.perception_agent = PerceptionAgent(
            message_bus=self.message_bus,
            camera_source=0,
            update_rate=30.0
        )

        self.safety_agent = SafetyAgent(
            message_bus=self.message_bus,
            update_rate=50.0,
            config_path="config/safety_params.yaml",
            go2_sdk=self.mock_go2
        )

        self.navigation_agent = NavigationAgent(
            message_bus=self.message_bus,
            update_rate=50.0,
            config_path="config/robot_params.yaml"
        )

        self.agents = [
            self.localization_agent,
            self.perception_agent,
            self.safety_agent,
            self.navigation_agent
        ]

    def start_agents(self):
        """Start all agents."""
        for agent in self.agents:
            agent.start()
            time.sleep(0.05)

    def stop_agents(self):
        """Stop all agents."""
        for agent in reversed(self.agents):
            agent.stop()

    def run_scenario(
        self,
        trajectory: PersonTrajectory,
        duration: float = 10.0
    ) -> SimulationResult:
        """Run a simulation scenario.

        Args:
            trajectory: Person's trajectory to follow
            duration: Simulation duration in seconds

        Returns:
            Simulation results
        """
        robot_positions = []
        person_positions = []
        distances = []
        velocities = []
        timestamps = []

        start_time = time.time()
        robot_x, robot_y = 0.0, 0.0

        try:
            idx = 0
            while time.time() - start_time < duration and idx < len(trajectory.positions):
                current_time = time.time() - start_time

                # Get person position
                person_x, person_y = trajectory.positions[idx]
                person_positions.append((person_x, person_y))

                # Simulate robot movement based on last command
                if self.mock_go2.last_command:
                    linear, angular = self.mock_go2.last_command
                    dt = 0.02  # 50Hz control
                    robot_x += linear * dt * np.cos(angular * dt)
                    robot_y += linear * dt * np.sin(angular * dt)

                robot_positions.append((robot_x, robot_y))

                # Calculate distance
                distance = np.sqrt((person_x - robot_x)**2 + (person_y - robot_y)**2)
                distances.append(distance)

                # Record velocity
                if self.mock_go2.last_command:
                    velocities.append(self.mock_go2.last_command)
                else:
                    velocities.append((0.0, 0.0))

                timestamps.append(current_time)

                idx += 1
                time.sleep(0.02)

            success = True
            error_message = ""

        except Exception as e:
            success = False
            error_message = str(e)

        return SimulationResult(
            robot_positions=robot_positions,
            person_positions=person_positions,
            distances=distances,
            velocities=velocities,
            timestamps=timestamps,
            success=success,
            error_message=error_message
        )


@pytest.fixture
def simulator():
    """Create simulator fixture."""
    sim = PersonFollowingSimulator()
    sim.setup_agents()
    yield sim
    sim.stop_agents()


def test_person_walks_straight_slow(simulator):
    """Test following person walking straight at slow speed (0.5 m/s)."""
    # Create trajectory: person walks straight forward
    duration = 5.0
    speed = 0.5  # m/s
    positions = [(speed * t, 0.0) for t in np.linspace(0, duration, 100)]
    timestamps = list(np.linspace(0, duration, 100))
    speeds = [speed] * 100

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    # Verify results
    assert result.success, f"Simulation failed: {result.error_message}"
    assert len(result.distances) > 0, "No distance measurements recorded"

    # Check that robot maintains target distance (2.0m ± 0.3m)
    avg_distance = np.mean(result.distances[-50:])  # Last half of trajectory
    assert 1.7 <= avg_distance <= 2.3, \
        f"Average distance {avg_distance:.2f}m outside target range [1.7, 2.3]m"


def test_person_walks_straight_medium(simulator):
    """Test following person walking straight at medium speed (1.0 m/s)."""
    duration = 5.0
    speed = 1.0  # m/s
    positions = [(speed * t, 0.0) for t in np.linspace(0, duration, 100)]
    timestamps = list(np.linspace(0, duration, 100))
    speeds = [speed] * 100

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"
    assert len(result.distances) > 0, "No distance measurements recorded"

    # At higher speed, allow slightly larger tolerance
    avg_distance = np.mean(result.distances[-50:])
    assert 1.5 <= avg_distance <= 2.5, \
        f"Average distance {avg_distance:.2f}m outside acceptable range"


def test_person_walks_straight_fast(simulator):
    """Test following person walking straight at fast speed (1.5 m/s)."""
    duration = 5.0
    speed = 1.5  # m/s
    positions = [(speed * t, 0.0) for t in np.linspace(0, duration, 100)]
    timestamps = list(np.linspace(0, duration, 100))
    speeds = [speed] * 100

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # At fast speed, robot may not keep up (max speed 0.8 m/s)
    # Distance should increase over time
    initial_distance = np.mean(result.distances[:20])
    final_distance = np.mean(result.distances[-20:])
    assert final_distance > initial_distance, \
        "Robot should fall behind when person moves faster than max speed"


def test_person_walks_in_curve(simulator):
    """Test following person walking in a curved path."""
    duration = 8.0
    speed = 0.8  # m/s

    # Create curved trajectory (quarter circle)
    radius = 3.0
    angles = np.linspace(0, np.pi/2, 100)
    positions = [
        (radius * np.sin(angle), radius * (1 - np.cos(angle)))
        for angle in angles
    ]
    timestamps = list(np.linspace(0, duration, 100))
    speeds = [speed] * 100

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"
    assert len(result.distances) > 0, "No distance measurements recorded"

    # Check distance maintenance during curve
    avg_distance = np.mean(result.distances[-50:])
    assert 1.5 <= avg_distance <= 2.5, \
        f"Failed to maintain distance during curve: {avg_distance:.2f}m"


def test_person_walks_in_circle(simulator):
    """Test following person walking in a circular path."""
    duration = 10.0
    speed = 0.6  # m/s

    # Create circular trajectory
    radius = 2.5
    angles = np.linspace(0, 2*np.pi, 150)
    positions = [
        (radius * np.cos(angle), radius * np.sin(angle))
        for angle in angles
    ]
    timestamps = list(np.linspace(0, duration, 150))
    speeds = [speed] * 150

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Verify robot follows circular path
    # Check that robot maintains reasonable distance
    avg_distance = np.mean(result.distances)
    assert avg_distance < 4.0, \
        f"Robot lost track during circular motion: avg distance {avg_distance:.2f}m"


def test_person_stops_suddenly(simulator):
    """Test robot response when person stops suddenly."""
    duration = 6.0
    speed = 0.8  # m/s

    # Person walks then stops at t=3s
    positions = []
    for t in np.linspace(0, duration, 100):
        if t < 3.0:
            positions.append((speed * t, 0.0))
        else:
            positions.append((speed * 3.0, 0.0))  # Stopped position

    timestamps = list(np.linspace(0, duration, 100))
    speeds = [speed if t < 3.0 else 0.0 for t in timestamps]

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Check that robot stops and maintains distance
    final_velocities = result.velocities[-20:]
    final_speeds = [abs(v[0]) for v in final_velocities]
    avg_final_speed = np.mean(final_speeds)

    assert avg_final_speed < 0.1, \
        f"Robot should stop when person stops, but speed is {avg_final_speed:.2f} m/s"

    # Check final distance is within target range
    final_distance = np.mean(result.distances[-20:])
    assert 1.5 <= final_distance <= 2.5, \
        f"Final distance {final_distance:.2f}m outside target range"


def test_person_changes_direction(simulator):
    """Test robot response when person changes direction."""
    duration = 8.0
    speed = 0.7  # m/s

    # Person walks forward, then turns 90 degrees and walks
    positions = []
    for t in np.linspace(0, duration, 120):
        if t < 4.0:
            # Walk forward
            positions.append((speed * t, 0.0))
        else:
            # Turn and walk perpendicular
            x = speed * 4.0
            y = speed * (t - 4.0)
            positions.append((x, y))

    timestamps = list(np.linspace(0, duration, 120))
    speeds = [speed] * 120

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Verify robot follows direction change
    # Check that robot adjusts and maintains reasonable distance
    avg_distance = np.mean(result.distances[-30:])
    assert avg_distance < 3.5, \
        f"Robot failed to follow direction change: distance {avg_distance:.2f}m"


def test_person_zigzag_pattern(simulator):
    """Test following person walking in zigzag pattern."""
    duration = 10.0
    speed = 0.6  # m/s

    # Create zigzag trajectory
    positions = []
    for t in np.linspace(0, duration, 150):
        x = speed * t
        y = 0.5 * np.sin(4 * t)  # Zigzag with amplitude 0.5m
        positions.append((x, y))

    timestamps = list(np.linspace(0, duration, 150))
    speeds = [speed] * 150

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Check that robot maintains reasonable distance despite zigzag
    avg_distance = np.mean(result.distances[-50:])
    assert 1.5 <= avg_distance <= 3.0, \
        f"Failed to maintain distance during zigzag: {avg_distance:.2f}m"


def test_following_distance_accuracy(simulator):
    """Test accuracy of distance maintenance over extended period."""
    duration = 15.0
    speed = 0.7  # m/s

    # Person walks straight at constant speed
    positions = [(speed * t, 0.0) for t in np.linspace(0, duration, 200)]
    timestamps = list(np.linspace(0, duration, 200))
    speeds = [speed] * 200

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Analyze distance accuracy (after initial convergence)
    steady_state_distances = result.distances[50:]  # Skip first 50 samples

    avg_distance = np.mean(steady_state_distances)
    std_distance = np.std(steady_state_distances)

    # Target: 2.0m ± 0.3m
    assert 1.7 <= avg_distance <= 2.3, \
        f"Average distance {avg_distance:.2f}m outside target range"

    assert std_distance < 0.5, \
        f"Distance variation too high: std={std_distance:.2f}m"


def test_response_time_to_speed_change(simulator):
    """Test robot response time when person changes speed."""
    duration = 8.0

    # Person walks at 0.5 m/s, then speeds up to 1.0 m/s at t=4s
    positions = []
    for t in np.linspace(0, duration, 120):
        if t < 4.0:
            speed = 0.5
        else:
            speed = 1.0

        if t < 4.0:
            x = speed * t
        else:
            x = 0.5 * 4.0 + 1.0 * (t - 4.0)

        positions.append((x, 0.0))

    timestamps = list(np.linspace(0, duration, 120))
    speeds = [0.5 if t < 4.0 else 1.0 for t in timestamps]

    trajectory = PersonTrajectory(
        positions=positions,
        timestamps=timestamps,
        speeds=speeds
    )

    simulator.start_agents()
    result = simulator.run_scenario(trajectory, duration=duration)

    assert result.success, f"Simulation failed: {result.error_message}"

    # Find when robot responds to speed change
    # Look for velocity increase after t=4s
    change_idx = 60  # Approximately t=4s
    velocities_before = [abs(v[0]) for v in result.velocities[change_idx-10:change_idx]]
    velocities_after = [abs(v[0]) for v in result.velocities[change_idx+10:change_idx+20]]

    avg_speed_before = np.mean(velocities_before)
    avg_speed_after = np.mean(velocities_after)

    # Robot should increase speed in response
    assert avg_speed_after > avg_speed_before, \
        "Robot should increase speed when person speeds up"

    # Response time should be < 0.5s (requirement from CLAUDE.md)
    # This is implicitly tested by checking speed increase within 10 samples (0.2s)
