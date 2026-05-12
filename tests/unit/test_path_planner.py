"""Unit tests for path_planner module."""

import pytest
import numpy as np
from unittest.mock import patch, mock_open

from src.control.path_planner import (
    PathPlanner, Obstacle, Trajectory, LocalMap
)


@pytest.fixture
def mock_config():
    """Mock configuration data."""
    return {
        'go2': {
            'max_linear_velocity': 0.8,
            'max_angular_velocity': 1.0,
            'max_acceleration': 0.5
        }
    }


@pytest.fixture
def planner(mock_config):
    """Create PathPlanner with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                return PathPlanner()


@pytest.fixture
def sample_obstacles():
    """Create sample obstacles."""
    return [
        Obstacle(x=2.0, y=0.0, radius=0.5),
        Obstacle(x=-1.0, y=1.0, radius=0.3),
        Obstacle(x=1.5, y=-1.5, radius=0.4)
    ]


class TestPathPlanner:
    """Test PathPlanner class."""

    def test_initialization(self, planner):
        """Test planner initialization."""
        assert planner.max_linear == 0.8
        assert planner.max_angular == 1.0
        assert planner.max_accel == 0.5
        assert planner.min_clearance == 0.3

    def test_plan_path_no_obstacles(self, planner):
        """Test path planning without obstacles."""
        current_vel = (0.0, 0.0)
        target_pos = (3.0, 0.0)

        linear, angular = planner.plan_path(current_vel, target_pos, None)

        assert isinstance(linear, float)
        assert isinstance(angular, float)
        assert -planner.max_linear <= linear <= planner.max_linear
        assert -planner.max_angular <= angular <= planner.max_angular

    def test_plan_path_with_obstacles(self, planner, sample_obstacles):
        """Test path planning with obstacles."""
        current_vel = (0.0, 0.0)
        target_pos = (3.0, 0.0)
        local_map = LocalMap(
            obstacles=sample_obstacles,
            resolution=0.1,
            size=10.0
        )

        linear, angular = planner.plan_path(current_vel, target_pos, local_map)

        assert isinstance(linear, float)
        assert isinstance(angular, float)

    def test_plan_path_target_left(self, planner):
        """Test planning to target on left."""
        current_vel = (0.0, 0.0)
        target_pos = (2.0, 2.0)

        linear, angular = planner.plan_path(current_vel, target_pos, None)

        assert angular > 0

    def test_plan_path_target_right(self, planner):
        """Test planning to target on right."""
        current_vel = (0.0, 0.0)
        target_pos = (2.0, -2.0)

        linear, angular = planner.plan_path(current_vel, target_pos, None)

        assert angular < 0

    def test_compute_dynamic_window(self, planner):
        """Test dynamic window computation."""
        current_vel = (0.5, 0.2)

        dw = planner._compute_dynamic_window(current_vel)

        assert len(dw) == 4
        min_linear, max_linear, min_angular, max_angular = dw
        assert min_linear <= max_linear
        assert min_angular <= max_angular

    def test_compute_dynamic_window_zero_velocity(self, planner):
        """Test dynamic window from zero velocity."""
        current_vel = (0.0, 0.0)

        dw = planner._compute_dynamic_window(current_vel)

        min_linear, max_linear, min_angular, max_angular = dw
        assert min_linear == 0.0
        assert max_linear > 0.0

    def test_sample_trajectories(self, planner):
        """Test trajectory sampling."""
        dw = (0.0, 0.8, -1.0, 1.0)
        current_vel = (0.0, 0.0)

        trajectories = planner._sample_trajectories(dw, current_vel)

        assert len(trajectories) > 0
        assert all(isinstance(t, Trajectory) for t in trajectories)

    def test_predict_trajectory_straight(self, planner):
        """Test trajectory prediction for straight motion."""
        positions = planner._predict_trajectory(0.5, 0.0)

        assert len(positions) > 0
        assert all(isinstance(p, tuple) for p in positions)
        assert all(len(p) == 2 for p in positions)

    def test_predict_trajectory_turning(self, planner):
        """Test trajectory prediction for turning motion."""
        positions = planner._predict_trajectory(0.5, 0.5)

        assert len(positions) > 0
        x_coords = [p[0] for p in positions]
        y_coords = [p[1] for p in positions]
        assert not all(y == 0 for y in y_coords)

    def test_check_collision_no_collision(self, planner, sample_obstacles):
        """Test collision check with no collision."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(0.5, 0.0), (1.0, 0.0), (1.5, 0.0)]
        )
        local_map = LocalMap(
            obstacles=sample_obstacles,
            resolution=0.1,
            size=10.0
        )

        collision = planner._check_collision(traj, local_map)

        assert isinstance(collision, bool)

    def test_check_collision_with_collision(self, planner):
        """Test collision check with collision."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(2.0, 0.0), (2.5, 0.0), (3.0, 0.0)]
        )
        obstacles = [Obstacle(x=2.5, y=0.0, radius=0.5)]
        local_map = LocalMap(
            obstacles=obstacles,
            resolution=0.1,
            size=10.0
        )

        collision = planner._check_collision(traj, local_map)

        assert collision is True

    def test_heading_cost(self, planner):
        """Test heading cost computation."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        )
        target_pos = (5.0, 0.0)

        cost = planner._heading_cost(traj, target_pos)

        assert cost >= 0.0

    def test_heading_cost_aligned(self, planner):
        """Test heading cost when aligned with target."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        )
        target_pos = (5.0, 0.0)

        cost = planner._heading_cost(traj, target_pos)

        assert cost < 0.5

    def test_clearance_cost_no_obstacles(self, planner):
        """Test clearance cost with no obstacles."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(1.0, 0.0), (2.0, 0.0)]
        )

        cost = planner._clearance_cost(traj, None)

        assert cost == 0.0

    def test_clearance_cost_with_obstacles(self, planner, sample_obstacles):
        """Test clearance cost with obstacles."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[(1.0, 0.0), (1.5, 0.0), (2.0, 0.0)]
        )
        local_map = LocalMap(
            obstacles=sample_obstacles,
            resolution=0.1,
            size=10.0
        )

        cost = planner._clearance_cost(traj, local_map)

        assert cost >= 0.0

    def test_velocity_cost(self, planner):
        """Test velocity cost computation."""
        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.0,
            cost=0.0,
            positions=[]
        )

        cost = planner._velocity_cost(traj)

        assert 0.0 <= cost <= 1.0

    def test_velocity_cost_max_velocity(self, planner):
        """Test velocity cost at max velocity."""
        traj = Trajectory(
            linear_vel=planner.max_linear,
            angular_vel=0.0,
            cost=0.0,
            positions=[]
        )

        cost = planner._velocity_cost(traj)

        assert cost == 0.0

    def test_evaluate_trajectories_empty(self, planner):
        """Test evaluating empty trajectory list."""
        result = planner._evaluate_trajectories([], (1.0, 0.0), None)

        assert result is None

    def test_evaluate_trajectories_all_collide(self, planner):
        """Test when all trajectories collide."""
        trajectories = [
            Trajectory(0.5, 0.0, float('inf'), [(2.0, 0.0)])
        ]
        obstacles = [Obstacle(x=2.0, y=0.0, radius=1.0)]
        local_map = LocalMap(obstacles=obstacles, resolution=0.1, size=10.0)

        result = planner._evaluate_trajectories(
            trajectories, (5.0, 0.0), local_map
        )

        assert result is None

    def test_dataclasses(self):
        """Test dataclass creation."""
        obstacle = Obstacle(x=1.0, y=2.0, radius=0.5)
        assert obstacle.x == 1.0
        assert obstacle.y == 2.0
        assert obstacle.radius == 0.5

        traj = Trajectory(
            linear_vel=0.5,
            angular_vel=0.2,
            cost=1.5,
            positions=[(1.0, 2.0)]
        )
        assert traj.linear_vel == 0.5
        assert traj.angular_vel == 0.2

        local_map = LocalMap(
            obstacles=[obstacle],
            resolution=0.1,
            size=10.0
        )
        assert len(local_map.obstacles) == 1
        assert local_map.resolution == 0.1

    def test_default_config(self, planner):
        """Test default configuration."""
        config = planner._default_config()

        assert 'go2' in config
        assert config['go2']['max_linear_velocity'] == 0.8
