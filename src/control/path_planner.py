"""Dynamic Window Approach (DWA) path planner for obstacle avoidance.

This module implements local path planning using DWA to avoid obstacles
while maintaining target following behavior.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import logging
import yaml
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class Obstacle:
    """Obstacle representation."""
    x: float  # meters
    y: float  # meters
    radius: float  # meters


@dataclass
class Trajectory:
    """Candidate trajectory."""
    linear_vel: float  # m/s
    angular_vel: float  # rad/s
    cost: float
    positions: List[Tuple[float, float]]  # (x, y) positions


@dataclass
class LocalMap:
    """Local obstacle map."""
    obstacles: List[Obstacle]
    resolution: float  # meters
    size: float  # meters (map is size x size)


class PathPlanner:
    """Dynamic Window Approach path planner."""

    def __init__(self, config_path: str = "config/robot_params.yaml"):
        """Initialize path planner.

        Args:
            config_path: Path to robot configuration file
        """
        self.config = self._load_config(config_path)

        # Robot constraints
        self.max_linear = self.config['go2']['max_linear_velocity']
        self.max_angular = self.config['go2']['max_angular_velocity']
        self.max_accel = self.config['go2']['max_acceleration']

        # DWA parameters
        self.dt = 0.1  # Time step for trajectory prediction (10Hz)
        self.predict_time = 2.0  # Prediction horizon (seconds)
        self.linear_samples = 10
        self.angular_samples = 20

        # Cost weights
        self.heading_weight = 1.0
        self.clearance_weight = 2.0
        self.velocity_weight = 0.5

        # Safety parameters
        self.min_clearance = 0.3  # meters
        self.robot_radius = 0.25  # meters (Go2 approximate radius)

        logger.info("Path planner initialized with DWA")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()

        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            'go2': {
                'max_linear_velocity': 0.8,
                'max_angular_velocity': 1.0,
                'max_acceleration': 0.5
            }
        }

    def plan_path(
        self,
        current_vel: Tuple[float, float],
        target_pos: Tuple[float, float],
        local_map: Optional[LocalMap] = None
    ) -> Tuple[float, float]:
        """Plan path using Dynamic Window Approach.

        Args:
            current_vel: Current velocity (linear, angular)
            target_pos: Target position relative to robot (x, y)
            local_map: Local obstacle map (optional)

        Returns:
            Optimal velocity command (linear, angular)
        """
        # Generate dynamic window
        dw = self._compute_dynamic_window(current_vel)

        # Sample trajectories
        trajectories = self._sample_trajectories(dw, current_vel)

        # Evaluate trajectories
        best_traj = self._evaluate_trajectories(
            trajectories,
            target_pos,
            local_map
        )

        if best_traj is None:
            logger.warning("No valid trajectory found, stopping")
            return (0.0, 0.0)

        logger.debug(
            f"Selected trajectory: linear={best_traj.linear_vel:.2f} m/s, "
            f"angular={best_traj.angular_vel:.2f} rad/s, cost={best_traj.cost:.2f}"
        )

        return (best_traj.linear_vel, best_traj.angular_vel)

    def _compute_dynamic_window(
        self,
        current_vel: Tuple[float, float]
    ) -> Tuple[float, float, float, float]:
        """Compute dynamic window based on current velocity and constraints.

        Args:
            current_vel: Current velocity (linear, angular)

        Returns:
            Dynamic window (min_linear, max_linear, min_angular, max_angular)
        """
        linear, angular = current_vel

        # Velocity limits
        min_linear = max(0.0, linear - self.max_accel * self.dt)
        max_linear = min(self.max_linear, linear + self.max_accel * self.dt)

        min_angular = max(-self.max_angular, angular - self.max_accel * self.dt)
        max_angular = min(self.max_angular, angular + self.max_accel * self.dt)

        return (min_linear, max_linear, min_angular, max_angular)

    def _sample_trajectories(
        self,
        dw: Tuple[float, float, float, float],
        current_vel: Tuple[float, float]
    ) -> List[Trajectory]:
        """Sample candidate trajectories within dynamic window.

        Args:
            dw: Dynamic window (min_linear, max_linear, min_angular, max_angular)
            current_vel: Current velocity (linear, angular)

        Returns:
            List of candidate trajectories
        """
        min_linear, max_linear, min_angular, max_angular = dw
        trajectories = []

        # Sample linear velocities
        linear_vels = np.linspace(min_linear, max_linear, self.linear_samples)

        # Sample angular velocities
        angular_vels = np.linspace(min_angular, max_angular, self.angular_samples)

        # Generate trajectories
        for linear_vel in linear_vels:
            for angular_vel in angular_vels:
                positions = self._predict_trajectory(linear_vel, angular_vel)
                trajectories.append(Trajectory(
                    linear_vel=linear_vel,
                    angular_vel=angular_vel,
                    cost=float('inf'),
                    positions=positions
                ))

        return trajectories

    def _predict_trajectory(
        self,
        linear_vel: float,
        angular_vel: float
    ) -> List[Tuple[float, float]]:
        """Predict trajectory for given velocities.

        Args:
            linear_vel: Linear velocity (m/s)
            angular_vel: Angular velocity (rad/s)

        Returns:
            List of (x, y) positions along trajectory
        """
        positions = []
        x, y, theta = 0.0, 0.0, 0.0

        num_steps = int(self.predict_time / self.dt)
        for _ in range(num_steps):
            x += linear_vel * np.cos(theta) * self.dt
            y += linear_vel * np.sin(theta) * self.dt
            theta += angular_vel * self.dt
            positions.append((x, y))

        return positions

    def _evaluate_trajectories(
        self,
        trajectories: List[Trajectory],
        target_pos: Tuple[float, float],
        local_map: Optional[LocalMap]
    ) -> Optional[Trajectory]:
        """Evaluate trajectories and select best one.

        Args:
            trajectories: List of candidate trajectories
            target_pos: Target position (x, y)
            local_map: Local obstacle map

        Returns:
            Best trajectory or None if no valid trajectory
        """
        best_traj = None
        best_cost = float('inf')

        for traj in trajectories:
            # Check collision
            if local_map and self._check_collision(traj, local_map):
                continue

            # Compute cost
            heading_cost = self._heading_cost(traj, target_pos)
            clearance_cost = self._clearance_cost(traj, local_map)
            velocity_cost = self._velocity_cost(traj)

            total_cost = (
                self.heading_weight * heading_cost +
                self.clearance_weight * clearance_cost +
                self.velocity_weight * velocity_cost
            )

            traj.cost = total_cost

            if total_cost < best_cost:
                best_cost = total_cost
                best_traj = traj

        return best_traj

    def _check_collision(
        self,
        traj: Trajectory,
        local_map: LocalMap
    ) -> bool:
        """Check if trajectory collides with obstacles.

        Args:
            traj: Trajectory to check
            local_map: Local obstacle map

        Returns:
            True if collision detected, False otherwise
        """
        for x, y in traj.positions:
            for obstacle in local_map.obstacles:
                dist = np.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2)
                if dist < (self.robot_radius + obstacle.radius + self.min_clearance):
                    return True
        return False

    def _heading_cost(
        self,
        traj: Trajectory,
        target_pos: Tuple[float, float]
    ) -> float:
        """Compute heading cost (alignment with target).

        Args:
            traj: Trajectory
            target_pos: Target position (x, y)

        Returns:
            Heading cost (lower is better)
        """
        if not traj.positions:
            return float('inf')

        # Final position of trajectory
        final_x, final_y = traj.positions[-1]

        # Angle to target
        target_angle = np.arctan2(target_pos[1], target_pos[0])

        # Angle of trajectory
        traj_angle = np.arctan2(final_y, final_x)

        # Angular difference
        angle_diff = abs(target_angle - traj_angle)
        angle_diff = min(angle_diff, 2 * np.pi - angle_diff)

        return angle_diff

    def _clearance_cost(
        self,
        traj: Trajectory,
        local_map: Optional[LocalMap]
    ) -> float:
        """Compute clearance cost (distance to obstacles).

        Args:
            traj: Trajectory
            local_map: Local obstacle map

        Returns:
            Clearance cost (lower is better)
        """
        if not local_map or not local_map.obstacles:
            return 0.0

        min_clearance = float('inf')

        for x, y in traj.positions:
            for obstacle in local_map.obstacles:
                dist = np.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2)
                dist -= (self.robot_radius + obstacle.radius)
                min_clearance = min(min_clearance, dist)

        # Inverse clearance (closer obstacles have higher cost)
        if min_clearance < 0.1:
            return 10.0
        return 1.0 / min_clearance

    def _velocity_cost(self, traj: Trajectory) -> float:
        """Compute velocity cost (prefer higher velocities).

        Args:
            traj: Trajectory

        Returns:
            Velocity cost (lower is better)
        """
        # Prefer higher linear velocities
        return (self.max_linear - traj.linear_vel) / self.max_linear
