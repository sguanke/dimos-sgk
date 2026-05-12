"""Test fixtures and data generators for simulation tests.

Provides reusable test data including:
- Video sequences
- Synthetic trajectories
- Mock sensor data
- Test scenarios
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import cv2


@dataclass
class VideoSequence:
    """Represents a recorded or synthetic video sequence."""
    frames: List[np.ndarray]
    fps: float
    person_positions: List[Tuple[float, float]]  # Ground truth positions
    timestamps: List[float]


@dataclass
class SensorData:
    """Mock sensor data for testing."""
    imu_readings: List[Tuple[float, float, float, float, float, float]]  # ax, ay, az, gx, gy, gz
    odometry_readings: List[Tuple[int, int]]  # left_ticks, right_ticks
    timestamps: List[float]


class VideoGenerator:
    """Generate synthetic video sequences for testing."""

    def __init__(self, width: int = 1920, height: int = 1080, fps: float = 30.0):
        self.width = width
        self.height = height
        self.fps = fps

    def generate_person_walking_straight(
        self,
        duration: float = 5.0,
        speed: float = 0.5
    ) -> VideoSequence:
        """Generate video of person walking straight.

        Args:
            duration: Video duration in seconds
            speed: Person walking speed in m/s

        Returns:
            Video sequence with ground truth
        """
        num_frames = int(duration * self.fps)
        frames = []
        positions = []
        timestamps = []

        for i in range(num_frames):
            t = i / self.fps
            timestamps.append(t)

            # Create frame
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

            # Calculate person position (in pixels)
            # Assume person starts at center, moves forward
            x_meters = speed * t
            y_meters = 0.0

            # Convert to pixel coordinates (simple projection)
            # Assume camera at origin, person at distance
            distance = 2.0 + x_meters
            pixel_x = self.width // 2
            pixel_y = self.height // 2

            # Draw person as rectangle
            person_width = int(100 / distance)  # Perspective scaling
            person_height = int(200 / distance)

            x1 = pixel_x - person_width // 2
            y1 = pixel_y - person_height // 2
            x2 = x1 + person_width
            y2 = y1 + person_height

            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), -1)

            frames.append(frame)
            positions.append((x_meters, y_meters))

        return VideoSequence(
            frames=frames,
            fps=self.fps,
            person_positions=positions,
            timestamps=timestamps
        )

    def generate_person_turning(
        self,
        duration: float = 8.0,
        speed: float = 0.7,
        turn_angle: float = 90.0
    ) -> VideoSequence:
        """Generate video of person turning.

        Args:
            duration: Video duration in seconds
            speed: Walking speed in m/s
            turn_angle: Turn angle in degrees

        Returns:
            Video sequence with ground truth
        """
        num_frames = int(duration * self.fps)
        frames = []
        positions = []
        timestamps = []

        turn_time = duration / 2
        turn_angle_rad = np.radians(turn_angle)

        for i in range(num_frames):
            t = i / self.fps
            timestamps.append(t)

            # Calculate position
            if t < turn_time:
                # Walk straight
                x = speed * t
                y = 0.0
            else:
                # Turn and walk
                x = speed * turn_time
                t_after_turn = t - turn_time
                y = speed * t_after_turn * np.sin(turn_angle_rad)
                x += speed * t_after_turn * np.cos(turn_angle_rad)

            # Create frame (simplified)
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frames.append(frame)
            positions.append((x, y))

        return VideoSequence(
            frames=frames,
            fps=self.fps,
            person_positions=positions,
            timestamps=timestamps
        )

    def generate_multiple_people(
        self,
        duration: float = 5.0,
        num_people: int = 3
    ) -> VideoSequence:
        """Generate video with multiple people.

        Args:
            duration: Video duration in seconds
            num_people: Number of people in scene

        Returns:
            Video sequence with ground truth for all people
        """
        num_frames = int(duration * self.fps)
        frames = []
        positions = []
        timestamps = []

        for i in range(num_frames):
            t = i / self.fps
            timestamps.append(t)

            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

            # Generate positions for all people
            frame_positions = []
            for person_id in range(num_people):
                # Each person walks at different speed/direction
                speed = 0.5 + person_id * 0.2
                angle = person_id * 30  # degrees
                x = speed * t * np.cos(np.radians(angle))
                y = speed * t * np.sin(np.radians(angle))
                frame_positions.append((x, y))

            frames.append(frame)
            positions.append(frame_positions[0])  # Track first person as target

        return VideoSequence(
            frames=frames,
            fps=self.fps,
            person_positions=positions,
            timestamps=timestamps
        )


class SensorDataGenerator:
    """Generate mock sensor data for testing."""

    def generate_stationary_imu(self, duration: float = 5.0, rate: float = 50.0) -> SensorData:
        """Generate IMU data for stationary robot.

        Args:
            duration: Duration in seconds
            rate: Sample rate in Hz

        Returns:
            Sensor data
        """
        num_samples = int(duration * rate)
        imu_readings = []
        odometry_readings = []
        timestamps = []

        for i in range(num_samples):
            t = i / rate
            timestamps.append(t)

            # Stationary: only gravity on z-axis
            imu_readings.append((0.0, 0.0, 9.81, 0.0, 0.0, 0.0))

            # No wheel movement
            odometry_readings.append((0, 0))

        return SensorData(
            imu_readings=imu_readings,
            odometry_readings=odometry_readings,
            timestamps=timestamps
        )

    def generate_moving_forward_imu(
        self,
        duration: float = 5.0,
        rate: float = 50.0,
        speed: float = 0.5
    ) -> SensorData:
        """Generate IMU data for robot moving forward.

        Args:
            duration: Duration in seconds
            rate: Sample rate in Hz
            speed: Linear speed in m/s

        Returns:
            Sensor data
        """
        num_samples = int(duration * rate)
        imu_readings = []
        odometry_readings = []
        timestamps = []

        # Wheel encoder parameters
        ticks_per_meter = 1000

        for i in range(num_samples):
            t = i / rate
            timestamps.append(t)

            # Small forward acceleration, gravity on z
            imu_readings.append((0.1, 0.0, 9.81, 0.0, 0.0, 0.0))

            # Wheel ticks accumulate
            ticks = int(speed * t * ticks_per_meter)
            odometry_readings.append((ticks, ticks))

        return SensorData(
            imu_readings=imu_readings,
            odometry_readings=odometry_readings,
            timestamps=timestamps
        )

    def generate_turning_imu(
        self,
        duration: float = 5.0,
        rate: float = 50.0,
        angular_velocity: float = 0.5
    ) -> SensorData:
        """Generate IMU data for robot turning.

        Args:
            duration: Duration in seconds
            rate: Sample rate in Hz
            angular_velocity: Angular velocity in rad/s

        Returns:
            Sensor data
        """
        num_samples = int(duration * rate)
        imu_readings = []
        odometry_readings = []
        timestamps = []

        ticks_per_meter = 1000
        wheel_base = 0.3  # meters

        for i in range(num_samples):
            t = i / rate
            timestamps.append(t)

            # Gyroscope shows rotation
            imu_readings.append((0.0, 0.0, 9.81, 0.0, 0.0, angular_velocity))

            # Differential wheel ticks for turning
            left_ticks = int((0.5 - angular_velocity * wheel_base / 2) * t * ticks_per_meter)
            right_ticks = int((0.5 + angular_velocity * wheel_base / 2) * t * ticks_per_meter)
            odometry_readings.append((left_ticks, right_ticks))

        return SensorData(
            imu_readings=imu_readings,
            odometry_readings=odometry_readings,
            timestamps=timestamps
        )


class TrajectoryGenerator:
    """Generate test trajectories for person following."""

    @staticmethod
    def straight_line(
        length: float = 10.0,
        speed: float = 0.5,
        num_points: int = 100
    ) -> List[Tuple[float, float]]:
        """Generate straight line trajectory."""
        duration = length / speed
        times = np.linspace(0, duration, num_points)
        return [(speed * t, 0.0) for t in times]

    @staticmethod
    def circular(
        radius: float = 3.0,
        speed: float = 0.6,
        num_points: int = 150
    ) -> List[Tuple[float, float]]:
        """Generate circular trajectory."""
        circumference = 2 * np.pi * radius
        duration = circumference / speed
        times = np.linspace(0, duration, num_points)
        angles = (speed / radius) * times
        return [(radius * np.cos(a), radius * np.sin(a)) for a in angles]

    @staticmethod
    def figure_eight(
        size: float = 2.0,
        speed: float = 0.5,
        num_points: int = 200
    ) -> List[Tuple[float, float]]:
        """Generate figure-eight trajectory."""
        duration = 4 * np.pi * size / speed
        times = np.linspace(0, duration, num_points)
        return [
            (size * np.sin(speed * t / size), size * np.sin(2 * speed * t / size) / 2)
            for t in times
        ]

    @staticmethod
    def zigzag(
        length: float = 10.0,
        amplitude: float = 1.0,
        frequency: float = 2.0,
        speed: float = 0.6,
        num_points: int = 150
    ) -> List[Tuple[float, float]]:
        """Generate zigzag trajectory."""
        duration = length / speed
        times = np.linspace(0, duration, num_points)
        return [
            (speed * t, amplitude * np.sin(2 * np.pi * frequency * t))
            for t in times
        ]

    @staticmethod
    def random_walk(
        num_steps: int = 100,
        step_size: float = 0.1,
        seed: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """Generate random walk trajectory."""
        if seed is not None:
            np.random.seed(seed)

        x, y = 0.0, 0.0
        trajectory = [(x, y)]

        for _ in range(num_steps):
            angle = np.random.uniform(0, 2 * np.pi)
            x += step_size * np.cos(angle)
            y += step_size * np.sin(angle)
            trajectory.append((x, y))

        return trajectory


# Pre-generated test scenarios
class TestScenarios:
    """Pre-defined test scenarios."""

    @staticmethod
    def get_basic_following():
        """Basic person following scenario."""
        return {
            'name': 'basic_following',
            'duration': 5.0,
            'trajectory': TrajectoryGenerator.straight_line(5.0, 0.5, 100),
            'description': 'Person walks straight at constant speed'
        }

    @staticmethod
    def get_complex_path():
        """Complex path following scenario."""
        return {
            'name': 'complex_path',
            'duration': 10.0,
            'trajectory': TrajectoryGenerator.figure_eight(2.0, 0.5, 200),
            'description': 'Person walks in figure-eight pattern'
        }

    @staticmethod
    def get_stop_and_go():
        """Stop and go scenario."""
        trajectory = []
        # Walk for 2 seconds
        trajectory.extend(TrajectoryGenerator.straight_line(1.0, 0.5, 40))
        # Stop for 2 seconds (repeat last position)
        last_pos = trajectory[-1]
        trajectory.extend([last_pos] * 40)
        # Walk again
        trajectory.extend([
            (last_pos[0] + 0.5 * (i * 0.05), last_pos[1])
            for i in range(40)
        ])

        return {
            'name': 'stop_and_go',
            'duration': 6.0,
            'trajectory': trajectory,
            'description': 'Person walks, stops, then continues'
        }

    @staticmethod
    def get_all_scenarios():
        """Get all pre-defined scenarios."""
        return [
            TestScenarios.get_basic_following(),
            TestScenarios.get_complex_path(),
            TestScenarios.get_stop_and_go(),
        ]


# Pytest fixtures
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "simulation: marks tests as simulation tests"
    )
