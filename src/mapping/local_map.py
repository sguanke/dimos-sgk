"""Local obstacle map for path planning.

This module builds a 2D occupancy grid around the robot using depth camera
or LiDAR data for obstacle avoidance.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import logging
import time

from ..localization.odometry import Pose2D

logger = logging.getLogger(__name__)


@dataclass
class OccupancyGrid:
    """2D occupancy grid map."""
    data: np.ndarray  # 2D array: 0=free, 100=occupied, -1=unknown
    resolution: float  # meters per cell
    width: int  # number of cells in x
    height: int  # number of cells in y
    origin_x: float  # world coordinates of grid origin
    origin_y: float  # world coordinates of grid origin
    timestamp: float = 0.0


@dataclass
class DepthPoint:
    """3D point from depth sensor."""
    x: float  # meters
    y: float  # meters
    z: float  # meters


class LocalMap:
    """Builds and maintains local obstacle map around robot."""

    def __init__(
        self,
        map_size: float = 10.0,
        resolution: float = 0.1,
        obstacle_threshold: float = 0.3,
        max_obstacle_height: float = 1.5
    ):
        """Initialize local map.

        Args:
            map_size: Size of square map (meters)
            resolution: Grid cell size (meters)
            obstacle_threshold: Height threshold for obstacles (meters)
            max_obstacle_height: Maximum height to consider (meters)
        """
        self.map_size = map_size
        self.resolution = resolution
        self.obstacle_threshold = obstacle_threshold
        self.max_obstacle_height = max_obstacle_height

        self.width = int(map_size / resolution)
        self.height = int(map_size / resolution)

        self.grid = np.full((self.height, self.width), -1, dtype=np.int8)

        self.robot_pose: Optional[Pose2D] = None

        logger.info(
            f"LocalMap initialized: size={map_size}m, "
            f"resolution={resolution}m, grid={self.width}x{self.height}"
        )

    def update(
        self,
        depth_points: list[DepthPoint],
        robot_pose: Pose2D
    ) -> OccupancyGrid:
        """Update map with new depth sensor data.

        Args:
            depth_points: List of 3D points from depth sensor
            robot_pose: Current robot pose

        Returns:
            Updated occupancy grid
        """
        self.robot_pose = robot_pose

        self._recenter_map(robot_pose)

        self._clear_sensor_cone(robot_pose)

        self._add_obstacles(depth_points, robot_pose)

        occupancy_grid = self._create_occupancy_grid()

        logger.debug(
            f"Map updated: {len(depth_points)} points, "
            f"{np.sum(self.grid == 100)} occupied cells"
        )

        return occupancy_grid

    def _recenter_map(self, robot_pose: Pose2D) -> None:
        """Recenter map around robot position.

        Args:
            robot_pose: Current robot pose
        """
        pass

    def _clear_sensor_cone(self, robot_pose: Pose2D) -> None:
        """Clear cells in sensor field of view.

        Args:
            robot_pose: Current robot pose
        """
        center_x = self.width // 2
        center_y = self.height // 2

        max_range_cells = int(5.0 / self.resolution)

        for dy in range(-max_range_cells, max_range_cells + 1):
            for dx in range(-max_range_cells, max_range_cells + 1):
                cell_x = center_x + dx
                cell_y = center_y + dy

                if not self._is_valid_cell(cell_x, cell_y):
                    continue

                distance = np.sqrt(dx**2 + dy**2) * self.resolution
                if distance > 5.0:
                    continue

                angle = np.arctan2(dy, dx)
                angle_diff = abs(self._normalize_angle(
                    angle - robot_pose.theta
                ))

                if angle_diff < np.radians(60):
                    if self.grid[cell_y, cell_x] != 100:
                        self.grid[cell_y, cell_x] = 0

    def _add_obstacles(
        self, depth_points: list[DepthPoint], robot_pose: Pose2D
    ) -> None:
        """Add obstacles from depth points to map.

        Args:
            depth_points: List of 3D points
            robot_pose: Current robot pose
        """
        for point in depth_points:
            if point.z < self.obstacle_threshold:
                continue
            if point.z > self.max_obstacle_height:
                continue

            world_x, world_y = self._transform_to_world(
                point.x, point.y, robot_pose
            )

            cell_x, cell_y = self._world_to_grid(world_x, world_y)

            if self._is_valid_cell(cell_x, cell_y):
                self.grid[cell_y, cell_x] = 100

    def _transform_to_world(
        self, x: float, y: float, robot_pose: Pose2D
    ) -> tuple[float, float]:
        """Transform point from robot frame to world frame.

        Args:
            x: X coordinate in robot frame
            y: Y coordinate in robot frame
            robot_pose: Current robot pose

        Returns:
            Tuple of (world_x, world_y)
        """
        cos_theta = np.cos(robot_pose.theta)
        sin_theta = np.sin(robot_pose.theta)

        world_x = robot_pose.x + x * cos_theta - y * sin_theta
        world_y = robot_pose.y + x * sin_theta + y * cos_theta

        return world_x, world_y

    def _world_to_grid(
        self, world_x: float, world_y: float
    ) -> tuple[int, int]:
        """Convert world coordinates to grid cell indices.

        Args:
            world_x: X coordinate in world frame
            world_y: Y coordinate in world frame

        Returns:
            Tuple of (cell_x, cell_y)
        """
        if self.robot_pose is None:
            return self.width // 2, self.height // 2

        half_size = self.map_size / 2.0

        rel_x = world_x - (self.robot_pose.x - half_size)
        rel_y = world_y - (self.robot_pose.y - half_size)

        cell_x = int(rel_x / self.resolution)
        cell_y = int(rel_y / self.resolution)

        return cell_x, cell_y

    def _is_valid_cell(self, cell_x: int, cell_y: int) -> bool:
        """Check if cell indices are within grid bounds.

        Args:
            cell_x: Cell x index
            cell_y: Cell y index

        Returns:
            True if valid
        """
        return (
            0 <= cell_x < self.width and
            0 <= cell_y < self.height
        )

    def _create_occupancy_grid(self) -> OccupancyGrid:
        """Create occupancy grid message.

        Returns:
            Occupancy grid with current map data
        """
        if self.robot_pose is None:
            origin_x = 0.0
            origin_y = 0.0
        else:
            half_size = self.map_size / 2.0
            origin_x = self.robot_pose.x - half_size
            origin_y = self.robot_pose.y - half_size

        return OccupancyGrid(
            data=self.grid.copy(),
            resolution=self.resolution,
            width=self.width,
            height=self.height,
            origin_x=origin_x,
            origin_y=origin_y,
            timestamp=time.time()
        )

    def is_occupied(self, world_x: float, world_y: float) -> bool:
        """Check if world position is occupied.

        Args:
            world_x: X coordinate in world frame
            world_y: Y coordinate in world frame

        Returns:
            True if occupied
        """
        cell_x, cell_y = self._world_to_grid(world_x, world_y)

        if not self._is_valid_cell(cell_x, cell_y):
            return True

        return self.grid[cell_y, cell_x] == 100

    def get_nearest_obstacle_distance(
        self, world_x: float, world_y: float, max_range: float = 2.0
    ) -> float:
        """Get distance to nearest obstacle from given position.

        Args:
            world_x: X coordinate in world frame
            world_y: Y coordinate in world frame
            max_range: Maximum search range (meters)

        Returns:
            Distance to nearest obstacle (meters), or max_range if none
        """
        cell_x, cell_y = self._world_to_grid(world_x, world_y)

        if not self._is_valid_cell(cell_x, cell_y):
            return 0.0

        max_cells = int(max_range / self.resolution)

        min_distance = max_range

        for dy in range(-max_cells, max_cells + 1):
            for dx in range(-max_cells, max_cells + 1):
                check_x = cell_x + dx
                check_y = cell_y + dy

                if not self._is_valid_cell(check_x, check_y):
                    continue

                if self.grid[check_y, check_x] == 100:
                    distance = np.sqrt(dx**2 + dy**2) * self.resolution
                    min_distance = min(min_distance, distance)

        return min_distance

    def reset(self) -> None:
        """Reset map to unknown state."""
        self.grid.fill(-1)
        self.robot_pose = None
        logger.info("Local map reset")

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi].

        Args:
            angle: Angle in radians

        Returns:
            Normalized angle
        """
        while angle > np.pi:
            angle -= 2.0 * np.pi
        while angle < -np.pi:
            angle += 2.0 * np.pi
        return angle
