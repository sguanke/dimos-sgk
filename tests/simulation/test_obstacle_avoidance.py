"""Simulation tests for obstacle avoidance scenarios.

This module tests the robot's ability to navigate around obstacles while
maintaining person following behavior.
"""

import pytest
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from tests.mocks.mock_go2 import MockGo2SDK
from tests.mocks.mock_camera import MockCamera
from tests.mocks.mock_dimos import MockMessageBus


@dataclass
class Obstacle:
    """Represents an obstacle in the environment."""
    x: float
    y: float
    radius: float


@dataclass
class OccupancyGrid:
    """2D occupancy grid for obstacle representation."""
    width: int  # cells
    height: int  # cells
    resolution: float  # meters per cell
    origin: Tuple[float, float]  # (x, y) in meters
    data: np.ndarray  # 0=free, 1=occupied, -1=unknown


class ObstacleEnvironment:
    """Simulation environment with obstacles."""

    def __init__(self):
        """Initialize obstacle environment."""
        self.robot = MockGo2SDK()
        self.camera = MockCamera()
        self.message_bus = MockMessageBus()
        self.robot_pose = np.array([0.0, 0.0, 0.0])  # x, y, theta
        self.obstacles: List[Obstacle] = []
        self.min_clearance = 0.3  # meters
        self.target_distance = 2.0

    def setup(self):
        """Setup environment."""
        self.robot.connect()
        self.camera.open()
        self.robot.clear_command_history()

    def teardown(self):
        """Teardown environment."""
        self.robot.disconnect()
        self.camera.close()

    def add_obstacle(self, x: float, y: float, radius: float):
        """Add an obstacle to the environment.

        Args:
            x: X position in meters
            y: Y position in meters
            radius: Obstacle radius in meters
        """
        self.obstacles.append(Obstacle(x, y, radius))

    def clear_obstacles(self):
        """Clear all obstacles."""
        self.obstacles.clear()

    def create_occupancy_grid(
        self,
        width: int = 100,
        height: int = 100,
        resolution: float = 0.1
    ) -> OccupancyGrid:
        """Create occupancy grid from obstacles.

        Args:
            width: Grid width in cells
            height: Grid height in cells
            resolution: Meters per cell

        Returns:
            Occupancy grid
        """
        data = np.zeros((height, width), dtype=np.int8)
        origin = (-width * resolution / 2, -height * resolution / 2)

        # Mark obstacles
        for obstacle in self.obstacles:
            # Convert obstacle position to grid coordinates
            grid_x = int((obstacle.x - origin[0]) / resolution)
            grid_y = int((obstacle.y - origin[1]) / resolution)
            grid_radius = int(obstacle.radius / resolution)

            # Mark cells within obstacle radius
            for dy in range(-grid_radius, grid_radius + 1):
                for dx in range(-grid_radius, grid_radius + 1):
                    if dx**2 + dy**2 <= grid_radius**2:
                        gx = grid_x + dx
                        gy = grid_y + dy
                        if 0 <= gx < width and 0 <= gy < height:
                            data[gy, gx] = 1

        return OccupancyGrid(width, height, resolution, origin, data)

    def check_collision(self, x: float, y: float, robot_radius: float = 0.2) -> bool:
        """Check if position collides with obstacles.

        Args:
            x: X position
            y: Y position
            robot_radius: Robot radius in meters

        Returns:
            True if collision detected
        """
        for obstacle in self.obstacles:
            distance = np.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2)
            if distance < (robot_radius + obstacle.radius + self.min_clearance):
                return True
        return False

    def get_nearest_obstacle_distance(self, x: float, y: float) -> float:
        """Get distance to nearest obstacle.

        Args:
            x: X position
            y: Y position

        Returns:
            Distance to nearest obstacle in meters
        """
        if not self.obstacles:
            return float('inf')

        min_distance = float('inf')
        for obstacle in self.obstacles:
            distance = np.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2)
            distance -= obstacle.radius  # Distance to surface
            min_distance = min(min_distance, distance)

        return min_distance


@pytest.fixture
def obstacle_env():
    """Provide obstacle environment."""
    env = ObstacleEnvironment()
    env.setup()
    yield env
    env.teardown()


class TestSingleObstacleAvoidance:
    """Test obstacle avoidance with single obstacles."""

    def test_obstacle_in_direct_path(self, obstacle_env):
        """Test avoiding obstacle directly between robot and person."""
        # Place obstacle at (2.5, 2.0) - between robot and person
        obstacle_env.add_obstacle(2.5, 2.0, 0.5)

        # Person at (5.0, 2.0)
        person_pos = np.array([5.0, 2.0])

        # Simulate navigation around obstacle
        for step in range(100):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            # Check if direct path is blocked
            direct_blocked = obstacle_env.check_collision(
                robot_x + 0.1,
                robot_y,
                robot_radius=0.2
            )

            if direct_blocked:
                # Try to go around (simple avoidance: move sideways)
                linear_x = 0.3
                angular_z = 0.5  # Turn to avoid
            else:
                # Move toward person
                dx = person_pos[0] - robot_x
                dy = person_pos[1] - robot_y
                distance = np.sqrt(dx**2 + dy**2)

                if distance > obstacle_env.target_distance:
                    linear_x = 0.5
                    angular_z = 0.0
                else:
                    linear_x = 0.0
                    angular_z = 0.0

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            # Update robot pose
            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            # Check no collision occurred
            assert not obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ), f"Collision at step {step}"

        # Verify robot avoided obstacle
        assert obstacle_env.robot_pose[0] > 1.0, "Robot should have made progress"

    def test_obstacle_on_left_side(self, obstacle_env):
        """Test avoiding obstacle on left side of path."""
        # Place obstacle at (2.5, 2.5) - left of direct path
        obstacle_env.add_obstacle(2.5, 2.5, 0.4)

        person_pos = np.array([5.0, 2.0])

        for step in range(100):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            # Simple avoidance: steer away from obstacles
            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.5:
                # Too close, steer right
                linear_x = 0.3
                angular_z = -0.5
            else:
                # Navigate toward person
                dx = person_pos[0] - robot_x
                dy = person_pos[1] - robot_y
                desired_heading = np.arctan2(dy, dx)
                heading_error = desired_heading - obstacle_env.robot_pose[2]
                heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

                linear_x = 0.5
                angular_z = 0.5 * heading_error

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            # Verify no collision
            assert not obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ), "Collision detected"

    def test_obstacle_on_right_side(self, obstacle_env):
        """Test avoiding obstacle on right side of path."""
        # Place obstacle at (2.5, 1.5) - right of direct path
        obstacle_env.add_obstacle(2.5, 1.5, 0.4)

        person_pos = np.array([5.0, 2.0])

        for step in range(100):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.5:
                # Too close, steer left
                linear_x = 0.3
                angular_z = 0.5
            else:
                dx = person_pos[0] - robot_x
                dy = person_pos[1] - robot_y
                desired_heading = np.arctan2(dy, dx)
                heading_error = desired_heading - obstacle_env.robot_pose[2]
                heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

                linear_x = 0.5
                angular_z = 0.5 * heading_error

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            assert not obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ), "Collision detected"


class TestMultipleObstacleAvoidance:
    """Test obstacle avoidance with multiple obstacles."""

    def test_navigate_through_corridor(self, obstacle_env):
        """Test navigating through narrow corridor with obstacles on both sides."""
        # Create corridor with obstacles
        obstacle_env.add_obstacle(2.0, 1.0, 0.3)
        obstacle_env.add_obstacle(2.0, 3.0, 0.3)
        obstacle_env.add_obstacle(3.0, 1.0, 0.3)
        obstacle_env.add_obstacle(3.0, 3.0, 0.3)

        person_pos = np.array([5.0, 2.0])

        collision_count = 0
        for step in range(200):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            # Check for nearby obstacles
            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.4:
                # Very close, slow down and adjust
                linear_x = 0.2
                # Steer toward center of corridor (y=2.0)
                if robot_y < 2.0:
                    angular_z = 0.3
                else:
                    angular_z = -0.3
            else:
                # Navigate forward
                dx = person_pos[0] - robot_x
                dy = person_pos[1] - robot_y
                desired_heading = np.arctan2(dy, dx)
                heading_error = desired_heading - obstacle_env.robot_pose[2]
                heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

                linear_x = 0.4
                angular_z = 0.5 * heading_error

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            if obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ):
                collision_count += 1

        # Allow some tolerance but should mostly avoid collisions
        assert collision_count < 10, f"Too many collisions: {collision_count}"

    def test_cluttered_environment(self, obstacle_env):
        """Test navigation in cluttered environment with many obstacles."""
        # Add multiple random obstacles
        np.random.seed(42)
        for i in range(8):
            x = np.random.uniform(1.0, 4.0)
            y = np.random.uniform(0.5, 3.5)
            radius = np.random.uniform(0.2, 0.4)
            obstacle_env.add_obstacle(x, y, radius)

        person_pos = np.array([5.0, 2.0])

        collision_count = 0
        for step in range(300):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.5:
                # Avoid obstacle
                linear_x = 0.2
                # Try different directions
                angular_z = 0.8 if step % 20 < 10 else -0.8
            else:
                dx = person_pos[0] - robot_x
                dy = person_pos[1] - robot_y
                desired_heading = np.arctan2(dy, dx)
                heading_error = desired_heading - obstacle_env.robot_pose[2]
                heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

                linear_x = 0.4
                angular_z = 0.5 * heading_error

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            if obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ):
                collision_count += 1

        # Should make progress despite obstacles
        assert obstacle_env.robot_pose[0] > 2.0, "Robot should navigate through obstacles"


class TestObstacleAvoidanceWithFollowing:
    """Test combined obstacle avoidance and person following."""

    def test_follow_person_around_obstacle(self, obstacle_env):
        """Test following person who walks around an obstacle."""
        # Place obstacle in path
        obstacle_env.add_obstacle(2.5, 2.0, 0.5)

        # Person trajectory: walks around obstacle
        person_trajectory = [
            (1.0 * t, 2.0) if t < 2.0 else
            (2.0, 2.0 + 0.5 * (t - 2.0)) if t < 4.0 else
            (2.0 + 0.5 * (t - 4.0), 3.0) if t < 6.0 else
            (3.0 + 0.5 * (t - 6.0), 3.0 - 0.5 * (t - 6.0)) if t < 8.0 else
            (4.0 + 0.5 * (t - 8.0), 2.0)
            for t in np.linspace(0, 10, 100)
        ]

        collision_count = 0
        for i, person_pos in enumerate(person_trajectory):
            robot_x, robot_y = obstacle_env.robot_pose[:2]
            person_x, person_y = person_pos

            # Calculate distance to person
            dx = person_x - robot_x
            dy = person_y - robot_y
            distance = np.sqrt(dx**2 + dy**2)

            # Check for obstacles
            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.4:
                # Avoid obstacle
                linear_x = 0.2
                angular_z = 0.5
            else:
                # Follow person
                desired_heading = np.arctan2(dy, dx)
                heading_error = desired_heading - obstacle_env.robot_pose[2]
                heading_error = np.arctan2(np.sin(heading_error), np.cos(heading_error))

                distance_error = distance - obstacle_env.target_distance
                linear_x = max(0.0, min(0.6, 0.5 * distance_error))
                angular_z = 0.5 * heading_error

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            if obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ):
                collision_count += 1

        # Verify collision-free navigation
        assert collision_count == 0, f"Collisions occurred: {collision_count}"

        # Verify robot followed person
        final_person_pos = person_trajectory[-1]
        final_distance = np.sqrt(
            (final_person_pos[0] - obstacle_env.robot_pose[0])**2 +
            (final_person_pos[1] - obstacle_env.robot_pose[1])**2
        )
        assert final_distance < 4.0, "Robot should stay reasonably close to person"

    def test_maintain_distance_with_obstacles(self, obstacle_env):
        """Test maintaining target distance while avoiding obstacles."""
        # Place obstacles near target following distance
        obstacle_env.add_obstacle(1.8, 2.0, 0.3)

        person_pos = np.array([3.0, 2.0])

        for step in range(100):
            robot_x, robot_y = obstacle_env.robot_pose[:2]

            dx = person_pos[0] - robot_x
            dy = person_pos[1] - robot_y
            distance = np.sqrt(dx**2 + dy**2)

            nearest_dist = obstacle_env.get_nearest_obstacle_distance(robot_x, robot_y)

            if nearest_dist < 0.4:
                # Obstacle too close, prioritize avoidance
                linear_x = 0.1
                angular_z = 0.5
            else:
                # Try to maintain target distance
                distance_error = distance - obstacle_env.target_distance

                if abs(distance_error) < 0.3:
                    # At target distance, stop
                    linear_x = 0.0
                    angular_z = 0.0
                else:
                    linear_x = max(0.0, min(0.5, 0.5 * distance_error))
                    angular_z = 0.0

            obstacle_env.robot.set_velocity(linear_x, 0.0, angular_z)

            obstacle_env.robot_pose[0] += linear_x * 0.02 * np.cos(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[1] += linear_x * 0.02 * np.sin(obstacle_env.robot_pose[2])
            obstacle_env.robot_pose[2] += angular_z * 0.02

            # Verify no collision
            assert not obstacle_env.check_collision(
                obstacle_env.robot_pose[0],
                obstacle_env.robot_pose[1]
            ), "Collision with obstacle"

        # Verify reasonable distance maintained
        final_distance = np.sqrt(
            (person_pos[0] - obstacle_env.robot_pose[0])**2 +
            (person_pos[1] - obstacle_env.robot_pose[1])**2
        )
        assert final_distance < 3.0, "Robot should be reasonably close despite obstacles"


class TestOccupancyGridGeneration:
    """Test occupancy grid generation from obstacles."""

    def test_create_empty_grid(self, obstacle_env):
        """Test creating empty occupancy grid."""
        grid = obstacle_env.create_occupancy_grid()

        assert grid.width == 100
        assert grid.height == 100
        assert grid.resolution == 0.1
        assert np.all(grid.data == 0), "Empty grid should have all free cells"

    def test_create_grid_with_obstacles(self, obstacle_env):
        """Test creating occupancy grid with obstacles."""
        obstacle_env.add_obstacle(0.0, 0.0, 0.5)
        obstacle_env.add_obstacle(1.0, 1.0, 0.3)

        grid = obstacle_env.create_occupancy_grid()

        # Check that some cells are occupied
        occupied_cells = np.sum(grid.data == 1)
        assert occupied_cells > 0, "Grid should have occupied cells"

        # Check that not all cells are occupied
        free_cells = np.sum(grid.data == 0)
        assert free_cells > 0, "Grid should have free cells"

    def test_grid_resolution(self, obstacle_env):
        """Test occupancy grid with different resolutions."""
        obstacle_env.add_obstacle(0.0, 0.0, 0.5)

        # High resolution
        grid_high = obstacle_env.create_occupancy_grid(resolution=0.05)
        occupied_high = np.sum(grid_high.data == 1)

        # Low resolution
        grid_low = obstacle_env.create_occupancy_grid(resolution=0.2)
        occupied_low = np.sum(grid_low.data == 1)

        # Higher resolution should have more occupied cells for same obstacle
        assert occupied_high > occupied_low, \
            "Higher resolution should have more cells"
