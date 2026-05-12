"""Local obstacle mapping for navigation.

This module builds a 2D occupancy grid around the robot using depth camera
or LiDAR data for obstacle avoidance during person following.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional
import numpy as np


class CellState(IntEnum):
    """Occupancy grid cell states."""
    UNKNOWN = -1
    FREE = 0
    OCCUPIED = 100


@dataclass
class OccupancyGrid:
    """2D occupancy grid map.

    Attributes:
        width: Grid width in cells
        height: Grid height in cells
        resolution: Cell size in meters
        origin_x: Grid origin x in world frame (meters)
        origin_y: Grid origin y in world frame (meters)
        data: Grid data (height x width array)
        timestamp: Map update timestamp
    """
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    data: np.ndarray
    timestamp: float = field(default_factory=time.time)


@dataclass
class DepthPoint:
    """3D point from depth sensor."""
    x: float  # meters
    y: float  # meters
    z: float  # meters


class LocalMap:
    """Builds and maintains local obstacle map around robot.

    Attributes:
        map_size: Map size in meters (square map)
        resolution: Cell size in meters
        update_rate: Map update frequency (Hz)
        max_obstacle_height: Maximum height to consider as obstacle
        min_obstacle_height: Minimum height to consider as obstacle
    """

    def __init__(
        self,
        map_size: float = 10.0,
        resolution: float = 0.1,
        update_rate: float = 10.0,
        max_obstacle_height: float = 2.0,
        min_obstacle_height: float = 0.1
    ):
        """Initialize local map.

        Args:
            map_size: Map size in meters (creates square map)
            resolution: Cell size in meters
            update_rate: Update frequency in Hz
            max_obstacle_height: Max height for obstacles (meters)
            min_obstacle_height: Min height for obstacles (meters)
        """
        self.map_size = map_size
        self.resolution = resolution
        self.update_rate = update_rate
        self.max_obstacle_height = max_obstacle_height
        self.min_obstacle_height = min_obstacle_height

        # Calculate grid dimensions
        self.grid_size = int(map_size / resolution)

        # Initialize occupancy grid
        self.grid = self._create_empty_grid()

        self._logger = logging.getLogger(__name__)
        self._logger.info(
            f"LocalMap initialized: size={map_size}m, "
            f"resolution={resolution}m, grid={self.grid_size}x{self.grid_size}"
        )

    def update(
        self,
        depth_points: list[DepthPoint],
        robot_x: float,
        robot_y: float,
        robot_theta: float
    ) -> OccupancyGrid:
        """Update map from depth sensor data.

        Args:
            depth_points: List of 3D points from depth sensor
            robot_x: Robot x position in world frame
            robot_y: Robot y position in world frame
            robot_theta: Robot orientation in radians

        Returns:
            Updated occupancy grid
        """
        # Clear grid (decay old observations)
        self._decay_grid()

        # Update grid origin to center on robot
        self.grid.origin_x = robot_x - self.map_size / 2
        self.grid.origin_y = robot_y - self.map_size / 2

        # Process depth points
        for point in depth_points:
            self._process_depth_point(
                point, robot_x, robot_y, robot_theta
            )

        self.grid.timestamp = time.time()
        return self.grid

    def _create_empty_grid(self) -> OccupancyGrid:
        """Create empty occupancy grid.

        Returns:
            Initialized occupancy grid
        """
        data = np.full(
            (self.grid_size, self.grid_size),
            CellState.UNKNOWN,
            dtype=np.int8
        )

        return OccupancyGrid(
            width=self.grid_size,
            height=self.grid_size,
            resolution=self.resolution,
            origin_x=0.0,
            origin_y=0.0,
            data=data
        )

    def _decay_grid(self, decay_rate: float = 0.9) -> None:
        """Decay old observations to handle dynamic obstacles.

        Args:
            decay_rate: Decay factor for occupied cells
        """
        # Decay occupied cells toward unknown
        occupied_mask = self.grid.data == CellState.OCCUPIED
        self.grid.data[occupied_mask] = int(
            CellState.OCCUPIED * decay_rate
        )

        # Reset cells below threshold to unknown
        low_confidence = (self.grid.data > 0) & (self.grid.data < 50)
        self.grid.data[low_confidence] = CellState.UNKNOWN

    def _process_depth_point(
        self,
        point: DepthPoint,
        robot_x: float,
        robot_y: float,
        robot_theta: float
    ) -> None:
        """Process single depth point and update grid.

        Args:
            point: 3D point from depth sensor
            robot_x: Robot x position
            robot_y: Robot y position
            robot_theta: Robot orientation
        """
        # Filter by height (ignore ground and ceiling)
        if (point.z < self.min_obstacle_height or
            point.z > self.max_obstacle_height):
            return

        # Transform point to world frame
        world_x, world_y = self._transform_to_world(
            point.x, point.y, robot_x, robot_y, robot_theta
        )

        # Convert to grid coordinates
        grid_x, grid_y = self._world_to_grid(world_x, world_y)

        # Update grid cell
        if self._is_valid_cell(grid_x, grid_y):
            self.grid.data[grid_y, grid_x] = CellState.OCCUPIED

            # Mark ray from robot to obstacle as free
            self._mark_ray_free(robot_x, robot_y, world_x, world_y)

    def _transform_to_world(
        self,
        x: float,
        y: float,
        robot_x: float,
        robot_y: float,
        robot_theta: float
    ) -> tuple[float, float]:
        """Transform point from robot frame to world frame.

        Args:
            x: X in robot frame
            y: Y in robot frame
            robot_x: Robot x position
            robot_y: Robot y position
            robot_theta: Robot orientation

        Returns:
            Tuple of (world_x, world_y)
        """
        cos_theta = np.cos(robot_theta)
        sin_theta = np.sin(robot_theta)

        world_x = robot_x + x * cos_theta - y * sin_theta
        world_y = robot_y + x * sin_theta + y * cos_theta

        return world_x, world_y

    def _world_to_grid(
        self, world_x: float, world_y: float
    ) -> tuple[int, int]:
        """Convert world coordinates to grid coordinates.

        Args:
            world_x: X in world frame
            world_y: Y in world frame

        Returns:
            Tuple of (grid_x, grid_y)
        """
        grid_x = int((world_x - self.grid.origin_x) / self.resolution)
        grid_y = int((world_y - self.grid.origin_y) / self.resolution)

        return grid_x, grid_y

    def _is_valid_cell(self, grid_x: int, grid_y: int) -> bool:
        """Check if grid coordinates are valid.

        Args:
            grid_x: Grid x coordinate
            grid_y: Grid y coordinate

        Returns:
            True if coordinates are within grid bounds
        """
        return (0 <= grid_x < self.grid_size and
                0 <= grid_y < self.grid_size)

    def _mark_ray_free(
        self,
        robot_x: float,
        robot_y: float,
        obstacle_x: float,
        obstacle_y: float
    ) -> None:
        """Mark cells along ray from robot to obstacle as free.

        Args:
            robot_x: Robot x position
            robot_y: Robot y position
            obstacle_x: Obstacle x position
            obstacle_y: Obstacle y position
        """
        # Convert to grid coordinates
        start_x, start_y = self._world_to_grid(robot_x, robot_y)
        end_x, end_y = self._world_to_grid(obstacle_x, obstacle_y)

        # Bresenham's line algorithm
        cells = self._bresenham_line(start_x, start_y, end_x, end_y)

        # Mark cells as free (except last cell which is obstacle)
        for x, y in cells[:-1]:
            if self._is_valid_cell(x, y):
                self.grid.data[y, x] = CellState.FREE

    def _bresenham_line(
        self, x0: int, y0: int, x1: int, y1: int
    ) -> list[tuple[int, int]]:
        """Bresenham's line algorithm for ray tracing.

        Args:
            x0: Start x
            y0: Start y
            x1: End x
            y1: End y

        Returns:
            List of (x, y) cells along line
        """
        cells = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0

        while True:
            cells.append((x, y))

            if x == x1 and y == y1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

        return cells

    def get_grid(self) -> OccupancyGrid:
        """Get current occupancy grid.

        Returns:
            Current occupancy grid
        """
        return self.grid

    def is_occupied(self, world_x: float, world_y: float) -> bool:
        """Check if world position is occupied.

        Args:
            world_x: X position in world frame
            world_y: Y position in world frame

        Returns:
            True if position is occupied
        """
        grid_x, grid_y = self._world_to_grid(world_x, world_y)

        if not self._is_valid_cell(grid_x, grid_y):
            return False

        return self.grid.data[grid_y, grid_x] == CellState.OCCUPIED

    def get_nearest_obstacle(
        self, robot_x: float, robot_y: float, max_range: float = 5.0
    ) -> Optional[tuple[float, float, float]]:
        """Find nearest obstacle to robot.

        Args:
            robot_x: Robot x position
            robot_y: Robot y position
            max_range: Maximum search range in meters

        Returns:
            Tuple of (x, y, distance) or None if no obstacle found
        """
        robot_grid_x, robot_grid_y = self._world_to_grid(robot_x, robot_y)
        max_cells = int(max_range / self.resolution)

        min_dist = float('inf')
        nearest_x, nearest_y = None, None

        # Search in grid around robot
        for dy in range(-max_cells, max_cells + 1):
            for dx in range(-max_cells, max_cells + 1):
                gx = robot_grid_x + dx
                gy = robot_grid_y + dy

                if not self._is_valid_cell(gx, gy):
                    continue

                if self.grid.data[gy, gx] == CellState.OCCUPIED:
                    dist = np.sqrt(dx**2 + dy**2) * self.resolution
                    if dist < min_dist:
                        min_dist = dist
                        nearest_x = gx
                        nearest_y = gy

        if nearest_x is not None:
            world_x = (nearest_x * self.resolution +
                      self.grid.origin_x)
            world_y = (nearest_y * self.resolution +
                      self.grid.origin_y)
            return world_x, world_y, min_dist

        return None

    def reset(self) -> None:
        """Reset map to empty state."""
        self.grid = self._create_empty_grid()
        self._logger.info("Local map reset")
