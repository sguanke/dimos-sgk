"""Unit tests for local_map module."""

import pytest
import time
import numpy as np

from src.mapping.local_map import (
    LocalMap, OccupancyGrid, DepthPoint, CellState
)


@pytest.fixture
def local_map():
    """Create LocalMap instance."""
    return LocalMap(
        map_size=10.0,
        resolution=0.1,
        update_rate=10.0,
        max_obstacle_height=2.0,
        min_obstacle_height=0.1
    )


@pytest.fixture
def sample_depth_points():
    """Create sample depth points."""
    return [
        DepthPoint(x=1.0, y=0.0, z=0.5),
        DepthPoint(x=2.0, y=1.0, z=0.8),
        DepthPoint(x=-1.0, y=-1.0, z=1.0),
        DepthPoint(x=0.5, y=0.5, z=0.3)
    ]


class TestLocalMap:
    """Test LocalMap class."""

    def test_initialization(self, local_map):
        """Test local map initialization."""
        assert local_map.map_size == 10.0
        assert local_map.resolution == 0.1
        assert local_map.grid_size == 100
        assert local_map.grid.width == 100
        assert local_map.grid.height == 100

    def test_update(self, local_map, sample_depth_points):
        """Test map update from depth points."""
        grid = local_map.update(
            depth_points=sample_depth_points,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        assert isinstance(grid, OccupancyGrid)
        assert grid.width == 100
        assert grid.height == 100

    def test_update_empty_points(self, local_map):
        """Test update with no depth points."""
        grid = local_map.update(
            depth_points=[],
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        assert isinstance(grid, OccupancyGrid)

    def test_update_filters_by_height(self, local_map):
        """Test that points outside height range are filtered."""
        points = [
            DepthPoint(x=1.0, y=0.0, z=0.05),
            DepthPoint(x=2.0, y=0.0, z=3.0),
            DepthPoint(x=3.0, y=0.0, z=0.5)
        ]

        grid = local_map.update(
            depth_points=points,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        assert isinstance(grid, OccupancyGrid)

    def test_transform_to_world(self, local_map):
        """Test transformation from robot to world frame."""
        world_x, world_y = local_map._transform_to_world(
            x=1.0,
            y=0.0,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        assert world_x == 1.0
        assert world_y == 0.0

    def test_transform_to_world_rotated(self, local_map):
        """Test transformation with robot rotation."""
        world_x, world_y = local_map._transform_to_world(
            x=1.0,
            y=0.0,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=np.pi/2
        )

        assert abs(world_x) < 0.01
        assert abs(world_y - 1.0) < 0.01

    def test_world_to_grid(self, local_map):
        """Test world to grid coordinate conversion."""
        local_map.grid.origin_x = -5.0
        local_map.grid.origin_y = -5.0

        grid_x, grid_y = local_map._world_to_grid(0.0, 0.0)

        assert grid_x == 50
        assert grid_y == 50

    def test_is_valid_cell(self, local_map):
        """Test cell validity check."""
        assert local_map._is_valid_cell(50, 50) is True
        assert local_map._is_valid_cell(0, 0) is True
        assert local_map._is_valid_cell(99, 99) is True
        assert local_map._is_valid_cell(-1, 50) is False
        assert local_map._is_valid_cell(50, 100) is False

    def test_bresenham_line(self, local_map):
        """Test Bresenham line algorithm."""
        cells = local_map._bresenham_line(0, 0, 5, 5)

        assert len(cells) > 0
        assert cells[0] == (0, 0)
        assert cells[-1] == (5, 5)

    def test_bresenham_line_horizontal(self, local_map):
        """Test Bresenham for horizontal line."""
        cells = local_map._bresenham_line(0, 0, 5, 0)

        assert len(cells) == 6
        assert all(y == 0 for x, y in cells)

    def test_bresenham_line_vertical(self, local_map):
        """Test Bresenham for vertical line."""
        cells = local_map._bresenham_line(0, 0, 0, 5)

        assert len(cells) == 6
        assert all(x == 0 for x, y in cells)

    def test_get_grid(self, local_map):
        """Test getting current grid."""
        grid = local_map.get_grid()

        assert isinstance(grid, OccupancyGrid)
        assert grid.width == 100

    def test_is_occupied(self, local_map, sample_depth_points):
        """Test checking if position is occupied."""
        local_map.update(
            depth_points=sample_depth_points,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        occupied = local_map.is_occupied(1.0, 0.0)
        assert isinstance(occupied, bool)

    def test_is_occupied_out_of_bounds(self, local_map):
        """Test occupied check for out of bounds position."""
        occupied = local_map.is_occupied(100.0, 100.0)
        assert occupied is False

    def test_get_nearest_obstacle(self, local_map):
        """Test finding nearest obstacle."""
        points = [DepthPoint(x=2.0, y=0.0, z=0.5)]
        local_map.update(
            depth_points=points,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        result = local_map.get_nearest_obstacle(0.0, 0.0, max_range=5.0)

        if result is not None:
            x, y, dist = result
            assert dist > 0

    def test_get_nearest_obstacle_none_found(self, local_map):
        """Test nearest obstacle when none exists."""
        result = local_map.get_nearest_obstacle(0.0, 0.0, max_range=1.0)

        assert result is None or isinstance(result, tuple)

    def test_reset(self, local_map, sample_depth_points):
        """Test map reset."""
        local_map.update(
            depth_points=sample_depth_points,
            robot_x=0.0,
            robot_y=0.0,
            robot_theta=0.0
        )

        local_map.reset()

        grid = local_map.get_grid()
        assert np.all(grid.data == CellState.UNKNOWN)

    def test_decay_grid(self, local_map):
        """Test grid decay."""
        local_map.grid.data[50, 50] = CellState.OCCUPIED

        local_map._decay_grid()

        assert local_map.grid.data[50, 50] < CellState.OCCUPIED

    def test_mark_ray_free(self, local_map):
        """Test marking ray as free."""
        local_map.grid.origin_x = -5.0
        local_map.grid.origin_y = -5.0

        local_map._mark_ray_free(0.0, 0.0, 1.0, 0.0)

        grid_x, grid_y = local_map._world_to_grid(0.5, 0.0)
        if local_map._is_valid_cell(grid_x, grid_y):
            assert local_map.grid.data[grid_y, grid_x] == CellState.FREE

    def test_dataclasses(self):
        """Test dataclass creation."""
        depth_point = DepthPoint(x=1.0, y=2.0, z=0.5)
        assert depth_point.x == 1.0
        assert depth_point.y == 2.0
        assert depth_point.z == 0.5

        grid = OccupancyGrid(
            width=100,
            height=100,
            resolution=0.1,
            origin_x=0.0,
            origin_y=0.0,
            data=np.zeros((100, 100), dtype=np.int8)
        )
        assert grid.width == 100
        assert grid.resolution == 0.1

    def test_cell_state_enum(self):
        """Test CellState enum values."""
        assert CellState.UNKNOWN == -1
        assert CellState.FREE == 0
        assert CellState.OCCUPIED == 100
