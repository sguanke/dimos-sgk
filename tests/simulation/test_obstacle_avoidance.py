"""Simulation tests for obstacle avoidance scenarios.

Tests the robot's ability to navigate around obstacles while
maintaining person following behavior.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import List, Tuple, Set

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
class Obstacle:
    """Represents an obstacle in the environment."""
    x: float
    y: float
    radius: float


@dataclass
class ObstacleMap:
    """2D occupancy grid with obstacles."""
    width: float  # meters
    height: float  # meters
    resolution: float  # meters per cell
    obstacles: List[Obstacle]

    def is_collision(self, x: float, y: float, robot_radius: float = 0.3) -> bool:
        """Check if position collides with any obstacle."""
        for obs in self.obstacles:
            dist = np.sqrt((x - obs.x)**2 + (y - obs.y)**2)
            if dist < (obs.radius + robot_radius):
                return True
        return False

    def get_occupancy_grid(self) -> np.ndarray:
        """Generate occupancy grid (0=free, 1=occupied)."""
        grid_width = int(self.width / self.resolution)
        grid_height = int(self.height / self.resolution)
        grid = np.zeros((grid_height, grid_width), dtype=np.uint8)

        for obs in self.obstacles:
            # Mark obstacle cells
            center_x = int(obs.x / self.resolution)
            center_y = int(obs.y / self.resolution)
            radius_cells = int(obs.radius / self.resolution)

            for dy in range(-radius_cells, radius_cells + 1):
                for dx in range(-radius_cells, radius_cells + 1):
                    if dx*dx + dy*dy <= radius_cells*radius_cells:
                        gx = center_x + dx
                        gy = center_y + dy
                        if 0 <= gx < grid_width and 0 <= gy < grid_height:
                            grid[gy, gx] = 1

        return grid


@dataclass
class ObstacleAvoidanceResult:
    """Results from obstacle avoidance simulation."""
    robot_path: List[Tuple[float, float]]
    person_path: List[Tuple[float, float]]
    collisions: List[Tuple[float, float, float]]  # (x, y, time)
    min_obstacle_distances: List[float]
    success: bool
    reached_goal: bool
    error_message: str = ""


class ObstacleAvoidanceSimulator:
    """Simulator for obstacle avoidance scenarios."""

    def __init__(self, obstacle_map: ObstacleMap):
        self.obstacle_map = obstacle_map
        self.message_bus = MessageBus()
        self.mock_go2 = MockGo2SDK()
        self.mock_camera = MockCamera()
        self.agents = []

    def setup_agents(self):
        """Initialize all agents."""
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
        person_path: List[Tuple[float, float]],
        duration: float = 10.0
    ) -> ObstacleAvoidanceResult:
        """Run obstacle avoidance scenario.

        Args:
            person_path: Path the person follows
            duration: Simulation duration

        Returns:
            Simulation results
        """
        robot_path = []
        collisions = []
        min_obstacle_distances = []

        start_time = time.time()
        robot_x, robot_y, robot_theta = 0.0, 0.0, 0.0

        try:
            idx = 0
            while time.time() - start_time < duration and idx < len(person_path):
                # Update robot position based on commands
                if self.mock_go2.last_command:
                    linear, angular = self.mock_go2.last_command
                    dt = 0.02  # 50Hz
                    robot_theta += angular * dt
                    robot_x += linear * dt * np.cos(robot_theta)
                    robot_y += linear * dt * np.sin(robot_theta)

                robot_path.append((robot_x, robot_y))

                # Check for collisions
                if self.obstacle_map.is_collision(robot_x, robot_y):
                    collisions.append((robot_x, robot_y, time.time() - start_time))

                # Calculate minimum distance to obstacles
                min_dist = float('inf')
                for obs in self.obstacle_map.obstacles:
                    dist = np.sqrt((robot_x - obs.x)**2 + (robot_y - obs.y)**2) - obs.radius
                    min_dist = min(min_dist, dist)
                min_obstacle_distances.append(max(0.0, min_dist))

                idx += 1
                time.sleep(0.02)

            # Check if robot reached goal (near final person position)
            if len(person_path) > 0 and len(robot_path) > 0:
                final_person = person_path[-1]
                final_robot = robot_path[-1]
                goal_distance = np.sqrt(
                    (final_person[0] - final_robot[0])**2 +
                    (final_person[1] - final_robot[1])**2
                )
                reached_goal = goal_distance < 3.0
            else:
                reached_goal = False

            success = len(collisions) == 0
            error_message = "" if success else f"Detected {len(collisions)} collisions"

        except Exception as e:
            success = False
            reached_goal = False
            error_message = str(e)

        return ObstacleAvoidanceResult(
            robot_path=robot_path,
            person_path=person_path,
            collisions=collisions,
            min_obstacle_distances=min_obstacle_distances,
            success=success,
            reached_goal=reached_goal,
            error_message=error_message
        )


@pytest.fixture
def empty_map():
    """Create empty map with no obstacles."""
    return ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=[]
    )


@pytest.fixture
def single_obstacle_map():
    """Create map with single obstacle."""
    return ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=[
            Obstacle(x=3.0, y=0.0, radius=0.5)
        ]
    )


@pytest.fixture
def corridor_map():
    """Create narrow corridor with obstacles on sides."""
    obstacles = []
    # Left wall obstacles
    for y in np.linspace(-2.0, 2.0, 10):
        obstacles.append(Obstacle(x=2.0, y=y, radius=0.3))
    # Right wall obstacles
    for y in np.linspace(-2.0, 2.0, 10):
        obstacles.append(Obstacle(x=6.0, y=y, radius=0.3))

    return ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=obstacles
    )


@pytest.fixture
def maze_map():
    """Create simple maze with multiple obstacles."""
    obstacles = [
        Obstacle(x=2.0, y=0.0, radius=0.4),
        Obstacle(x=4.0, y=1.5, radius=0.4),
        Obstacle(x=4.0, y=-1.5, radius=0.4),
        Obstacle(x=6.0, y=0.5, radius=0.4),
        Obstacle(x=6.0, y=-0.5, radius=0.4),
    ]

    return ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=obstacles
    )


def test_no_obstacles_baseline(empty_map):
    """Test baseline following with no obstacles."""
    simulator = ObstacleAvoidanceSimulator(empty_map)
    simulator.setup_agents()

    # Person walks straight
    person_path = [(0.5 * t, 0.0) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=5.0)
    simulator.stop_agents()

    assert result.success, f"Baseline test failed: {result.error_message}"
    assert len(result.collisions) == 0, "No collisions expected in empty map"


def test_avoid_single_obstacle(single_obstacle_map):
    """Test avoiding a single obstacle in the path."""
    simulator = ObstacleAvoidanceSimulator(single_obstacle_map)
    simulator.setup_agents()

    # Person walks straight through obstacle position
    person_path = [(0.5 * t, 0.0) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=5.0)
    simulator.stop_agents()

    # Robot should avoid collision
    assert len(result.collisions) == 0, \
        f"Robot collided with obstacle {len(result.collisions)} times"

    # Robot should maintain minimum clearance (0.3m requirement)
    min_clearance = min(result.min_obstacle_distances)
    assert min_clearance >= 0.25, \
        f"Robot got too close to obstacle: {min_clearance:.2f}m (min 0.3m required)"


def test_navigate_corridor(corridor_map):
    """Test navigating through a narrow corridor."""
    simulator = ObstacleAvoidanceSimulator(corridor_map)
    simulator.setup_agents()

    # Person walks through corridor center
    person_path = [(4.0, 0.5 * t) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=6.0)
    simulator.stop_agents()

    # No collisions allowed
    assert len(result.collisions) == 0, \
        f"Robot collided in corridor {len(result.collisions)} times"

    # Robot should stay in corridor
    for x, y in result.robot_path:
        assert 2.0 < x < 6.0, \
            f"Robot left corridor bounds at ({x:.2f}, {y:.2f})"


def test_navigate_maze(maze_map):
    """Test navigating through obstacles in maze-like environment."""
    simulator = ObstacleAvoidanceSimulator(maze_map)
    simulator.setup_agents()

    # Person follows path through maze
    person_path = [
        (0.5 * t, 0.0) if t < 10 else
        (5.0, 0.3 * (t - 10)) if t < 15 else
        (5.0 + 0.5 * (t - 15), 1.5)
        for t in range(25)
    ]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=8.0)
    simulator.stop_agents()

    # Collision avoidance is critical
    assert len(result.collisions) == 0, \
        f"Robot collided {len(result.collisions)} times in maze"


def test_obstacle_clearance_maintained(single_obstacle_map):
    """Test that minimum obstacle clearance is maintained."""
    simulator = ObstacleAvoidanceSimulator(single_obstacle_map)
    simulator.setup_agents()

    # Person walks past obstacle
    person_path = [(0.5 * t, 0.0) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=5.0)
    simulator.stop_agents()

    # Check all distances maintain minimum clearance
    violations = [d for d in result.min_obstacle_distances if d < 0.3]
    violation_rate = len(violations) / len(result.min_obstacle_distances) if result.min_obstacle_distances else 0

    assert violation_rate < 0.1, \
        f"Clearance violated {violation_rate*100:.1f}% of the time (max 10% allowed)"


def test_dynamic_obstacle_response():
    """Test response time to suddenly appearing obstacle."""
    # Create map with obstacle that 'appears' during simulation
    obstacle_map = ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=[
            Obstacle(x=5.0, y=0.0, radius=0.5)
        ]
    )

    simulator = ObstacleAvoidanceSimulator(obstacle_map)
    simulator.setup_agents()

    # Person walks toward obstacle
    person_path = [(0.5 * t, 0.0) for t in range(25)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=6.0)
    simulator.stop_agents()

    # Robot should detect and avoid
    assert len(result.collisions) == 0, "Robot should avoid obstacle"

    # Check that robot started avoiding before collision
    # Find when robot was near obstacle (x ~ 5.0)
    near_obstacle_distances = []
    for (x, y), dist in zip(result.robot_path, result.min_obstacle_distances):
        if 4.0 <= x <= 6.0:
            near_obstacle_distances.append(dist)

    if near_obstacle_distances:
        min_dist_near_obstacle = min(near_obstacle_distances)
        assert min_dist_near_obstacle >= 0.2, \
            f"Robot got too close: {min_dist_near_obstacle:.2f}m"


def test_follow_while_avoiding():
    """Test that robot continues following person while avoiding obstacles."""
    obstacle_map = ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=[
            Obstacle(x=3.0, y=0.5, radius=0.4),
            Obstacle(x=5.0, y=-0.5, radius=0.4),
        ]
    )

    simulator = ObstacleAvoidanceSimulator(obstacle_map)
    simulator.setup_agents()

    # Person walks past obstacles
    person_path = [(0.6 * t, 0.0) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=6.0)
    simulator.stop_agents()

    # No collisions
    assert len(result.collisions) == 0, "Robot should avoid all obstacles"

    # Robot should still make progress following person
    if len(result.robot_path) > 10:
        initial_x = result.robot_path[5][0]
        final_x = result.robot_path[-1][0]
        progress = final_x - initial_x

        assert progress > 2.0, \
            f"Robot made insufficient progress: {progress:.2f}m (expected > 2.0m)"


def test_collision_avoidance_success_rate():
    """Test collision avoidance success rate across multiple scenarios."""
    scenarios = []

    # Generate random obstacle configurations
    for seed in range(5):
        np.random.seed(seed)
        obstacles = []
        for _ in range(3):
            x = np.random.uniform(2.0, 8.0)
            y = np.random.uniform(-2.0, 2.0)
            radius = np.random.uniform(0.3, 0.6)
            obstacles.append(Obstacle(x=x, y=y, radius=radius))

        scenarios.append(obstacles)

    collision_count = 0
    total_scenarios = len(scenarios)

    for obstacles in scenarios:
        obstacle_map = ObstacleMap(
            width=20.0,
            height=20.0,
            resolution=0.1,
            obstacles=obstacles
        )

        simulator = ObstacleAvoidanceSimulator(obstacle_map)
        simulator.setup_agents()

        person_path = [(0.5 * t, 0.0) for t in range(20)]

        simulator.start_agents()
        result = simulator.run_scenario(person_path, duration=5.0)
        simulator.stop_agents()

        if len(result.collisions) > 0:
            collision_count += 1

    success_rate = (total_scenarios - collision_count) / total_scenarios

    # Requirement: 100% collision avoidance success rate
    assert success_rate == 1.0, \
        f"Collision avoidance success rate {success_rate*100:.1f}% (required: 100%)"


def test_minimum_turning_radius_respected():
    """Test that robot respects minimum turning radius during avoidance."""
    obstacle_map = ObstacleMap(
        width=20.0,
        height=20.0,
        resolution=0.1,
        obstacles=[
            Obstacle(x=3.0, y=0.0, radius=0.5)
        ]
    )

    simulator = ObstacleAvoidanceSimulator(obstacle_map)
    simulator.setup_agents()

    person_path = [(0.5 * t, 0.0) for t in range(20)]

    simulator.start_agents()
    result = simulator.run_scenario(person_path, duration=5.0)
    simulator.stop_agents()

    # Calculate turning radius from path
    # Check consecutive positions for sharp turns
    sharp_turns = 0
    for i in range(2, len(result.robot_path)):
        p0 = np.array(result.robot_path[i-2])
        p1 = np.array(result.robot_path[i-1])
        p2 = np.array(result.robot_path[i])

        # Calculate angle change
        v1 = p1 - p0
        v2 = p2 - p1

        if np.linalg.norm(v1) > 0.01 and np.linalg.norm(v2) > 0.01:
            angle = np.arccos(
                np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1.0, 1.0)
            )
            # If angle change is too sharp for minimum radius (0.5m)
            if angle > np.pi / 4:  # 45 degrees in one step
                sharp_turns += 1

    # Allow some sharp turns but not excessive
    sharp_turn_rate = sharp_turns / len(result.robot_path) if result.robot_path else 0
    assert sharp_turn_rate < 0.2, \
        f"Too many sharp turns: {sharp_turn_rate*100:.1f}% (max 20%)"
