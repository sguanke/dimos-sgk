"""Path planner with obstacle avoidance using Dynamic Window Approach (DWA).

This module implements local path planning to avoid obstacles while following
the target person.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import time
import logging
import math
import numpy as np

from .motion_controller import VelocityCommand, RobotPose, TargetPosition

logger = logging.getLogger(__name__)


@dataclass
class PathPlannerConfig:
    """Configuration for path planner."""

    replanning_frequency: float = 10.0  # Hz
    min_obstacle_clearance: float = 0.3  # meters
    local_map_size: float = 10.0  # meters
    dwa_time_horizon: float = 2.0  # seconds
    dwa_velocity_samples: int = 10
    dwa_angular_samples: int = 20
    max_linear_velocity: float = 0.8  # m/s
    max_angular_velocity: float = 1.0  # rad/s
    max_acceleration: float = 0.5  # m/s²


@dataclass
class Obstacle:
    """Obstacle representation."""

    x: float  # meters
    y: float  # meters
    radius: float  # meters


@dataclass
class OccupancyGrid:
    """2D occupancy grid for local obstacles."""

    data: np.ndarray  # 2D array: 0=free, 1=occupied, -1=unknown
    resolution: float  # meters per cell
    origin_x: float  # meters
    origin_y: float  # meters
    timestamp: float = field(default_factory=time.time)

    def get_obstacles(self, min_clearance: float) -> List[Obstacle]:
        """Extract obstacles from occupancy grid.

        Args:
            min_clearance: Minimum clearance around obstacles (meters)

        Returns:
            List of obstacles
        """
        obstacles = []
        rows, cols = self.data.shape

        for i in range(rows):
            for j in range(cols):
                if self.data[i, j] == 1:  # Occupied cell
                    # Convert grid coordinates to world coordinates
                    x = self.origin_x + j * self.resolution
                    y = self.origin_y + i * self.resolution
                    obstacles.append(
                        Obstacle(x=x, y=y, radius=min_clearance)
                    )

        return obstacles


class PathPlanner:
    """Dynamic Window Approach (DWA) path planner."""

    def __init__(self, config: Optional[PathPlannerConfig] = None):
        """Initialize path planner.

        Args:
            config: Path planner configuration
        """
        self.config = config or PathPlannerConfig()
        self.last_plan_time = time.time()
        self.current_velocity = VelocityCommand(linear_x=0.0, angular_z=0.0)

        logger.info(
            f"PathPlanner initialized: DWA with "
            f"{self.config.dwa_velocity_samples}x"
            f"{self.config.dwa_angular_samples} samples"
        )

    def plan(
        self,
        robot_pose: RobotPose,
        target: TargetPosition,
        obstacle_map: Optional[OccupancyGrid],
        desired_velocity: VelocityCommand,
    ) -> VelocityCommand:
        """Plan path to target while avoiding obstacles.

        Args:
            robot_pose: Current robot pose
            target: Target person position
            obstacle_map: Local obstacle map
            desired_velocity: Desired velocity from motion controller

        Returns:
            Velocity command with obstacle avoidance
        """
        current_time = time.time()

        # Check if replanning is needed
        if (
            current_time - self.last_plan_time
            < 1.0 / self.config.replanning_frequency
        ):
            return self.current_velocity

        self.last_plan_time = current_time

        # If no obstacle map, return desired velocity
        if obstacle_map is None:
            logger.debug("No obstacle map available, using desired velocity")
            self.current_velocity = desired_velocity
            return desired_velocity

        # Extract obstacles from map
        obstacles = obstacle_map.get_obstacles(
            self.config.min_obstacle_clearance
        )

        if not obstacles:
            logger.debug("No obstacles detected, using desired velocity")
            self.current_velocity = desired_velocity
            return desired_velocity

        # Run DWA to find best velocity
        best_velocity = self._dynamic_window_approach(
            robot_pose, target, obstacles, desired_velocity
        )

        self.current_velocity = best_velocity
        return best_velocity

    def _dynamic_window_approach(
        self,
        robot_pose: RobotPose,
        target: TargetPosition,
        obstacles: List[Obstacle],
        desired_velocity: VelocityCommand,
    ) -> VelocityCommand:
        """Dynamic Window Approach for local planning.

        Args:
            robot_pose: Current robot pose
            target: Target person position
            obstacles: List of obstacles
            desired_velocity: Desired velocity

        Returns:
            Best velocity command
        """
        # Compute dynamic window (feasible velocities)
        v_min, v_max, w_min, w_max = self._compute_dynamic_window(
            self.current_velocity
        )

        # Sample velocities in dynamic window
        v_samples = np.linspace(v_min, v_max, self.config.dwa_velocity_samples)
        w_samples = np.linspace(
            w_min, w_max, self.config.dwa_angular_samples
        )

        best_score = -float("inf")
        best_v = 0.0
        best_w = 0.0

        # Evaluate each velocity sample
        for v in v_samples:
            for w in w_samples:
                # Predict trajectory
                trajectory = self._predict_trajectory(
                    robot_pose, v, w, self.config.dwa_time_horizon
                )

                # Check collision
                if self._check_collision(trajectory, obstacles):
                    continue

                # Compute score
                score = self._compute_trajectory_score(
                    trajectory, target, desired_velocity, v, w
                )

                if score > best_score:
                    best_score = score
                    best_v = v
                    best_w = w

        # If no safe velocity found, stop
        if best_score == -float("inf"):
            logger.warning("No collision-free path found, stopping")
            return VelocityCommand(linear_x=0.0, angular_z=0.0)

        logger.debug(
            f"DWA selected: v={best_v:.3f} m/s, w={best_w:.3f} rad/s "
            f"(score={best_score:.2f})"
        )

        return VelocityCommand(linear_x=best_v, angular_z=best_w)

    def _compute_dynamic_window(
        self, current_velocity: VelocityCommand
    ) -> Tuple[float, float, float, float]:
        """Compute dynamic window of feasible velocities.

        Args:
            current_velocity: Current velocity

        Returns:
            Tuple of (v_min, v_max, w_min, w_max)
        """
        dt = 1.0 / self.config.replanning_frequency
        max_dv = self.config.max_acceleration * dt

        # Linear velocity window
        v_min = max(
            0.0, current_velocity.linear_x - max_dv
        )  # No backward motion
        v_max = min(
            self.config.max_linear_velocity,
            current_velocity.linear_x + max_dv,
        )

        # Angular velocity window
        w_min = max(
            -self.config.max_angular_velocity,
            current_velocity.angular_z - max_dv,
        )
        w_max = min(
            self.config.max_angular_velocity,
            current_velocity.angular_z + max_dv,
        )

        return v_min, v_max, w_min, w_max

    def _predict_trajectory(
        self, robot_pose: RobotPose, v: float, w: float, time_horizon: float
    ) -> List[Tuple[float, float]]:
        """Predict robot trajectory for given velocities.

        Args:
            robot_pose: Current robot pose
            v: Linear velocity (m/s)
            w: Angular velocity (rad/s)
            time_horizon: Prediction time (seconds)

        Returns:
            List of (x, y) positions along trajectory
        """
        trajectory = []
        dt = 0.1  # 100ms time step
        num_steps = int(time_horizon / dt)

        x, y, theta = robot_pose.x, robot_pose.y, robot_pose.theta

        for _ in range(num_steps):
            # Update pose using motion model
            x += v * math.cos(theta) * dt
            y += v * math.sin(theta) * dt
            theta += w * dt

            trajectory.append((x, y))

        return trajectory

    def _check_collision(
        self, trajectory: List[Tuple[float, float]], obstacles: List[Obstacle]
    ) -> bool:
        """Check if trajectory collides with obstacles.

        Args:
            trajectory: List of (x, y) positions
            obstacles: List of obstacles

        Returns:
            True if collision detected
        """
        for x, y in trajectory:
            for obs in obstacles:
                dist = math.sqrt((x - obs.x) ** 2 + (y - obs.y) ** 2)
                if dist < obs.radius:
                    return True
        return False

    def _compute_trajectory_score(
        self,
        trajectory: List[Tuple[float, float]],
        target: TargetPosition,
        desired_velocity: VelocityCommand,
        v: float,
        w: float,
    ) -> float:
        """Compute score for trajectory.

        Args:
            trajectory: List of (x, y) positions
            target: Target person position
            desired_velocity: Desired velocity
            v: Linear velocity
            w: Angular velocity

        Returns:
            Trajectory score (higher is better)
        """
        # Goal heading: prefer trajectories toward target
        end_x, end_y = trajectory[-1]
        target_x = target.x
        target_y = target.y
        heading_error = math.atan2(target_y - end_y, target_x - end_x)
        heading_score = 1.0 - abs(heading_error) / math.pi

        # Velocity matching: prefer velocities close to desired
        velocity_error = abs(v - desired_velocity.linear_x) + abs(
            w - desired_velocity.angular_z
        )
        velocity_score = 1.0 / (1.0 + velocity_error)

        # Speed: prefer higher speeds (within limits)
        speed_score = v / self.config.max_linear_velocity

        # Combine scores with weights
        score = (
            2.0 * heading_score + 1.0 * velocity_score + 0.5 * speed_score
        )

        return score

    def reset(self) -> None:
        """Reset path planner state."""
        self.current_velocity = VelocityCommand(linear_x=0.0, angular_z=0.0)
        self.last_plan_time = time.time()
        logger.info("PathPlanner reset")
