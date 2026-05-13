"""Mock Go2 SDK for testing.

This module provides mock implementations of the Go2 SDK for unit testing
without requiring actual hardware.
"""

from typing import Optional, Tuple
from dataclasses import dataclass
import time


@dataclass
class MockIMUData:
    """Mock IMU data."""
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 9.81
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    timestamp: float = 0.0


@dataclass
class MockOdometryData:
    """Mock odometry data."""
    left_wheel: float = 0.0
    right_wheel: float = 0.0
    timestamp: float = 0.0


class MockGo2SDK:
    """Mock Go2 SDK client for testing."""

    def __init__(self, robot_ip: str = "192.168.123.161"):
        """Initialize mock Go2 SDK.

        Args:
            robot_ip: Robot IP address (ignored in mock)
        """
        self.robot_ip = robot_ip
        self.connected = False
        self.last_velocity_command = None
        self.command_history = []
        self.imu_data = MockIMUData()
        self.odometry_data = MockOdometryData()
        self.battery_level = 100.0

    def connect(self) -> bool:
        """Connect to robot (mock).

        Returns:
            True if connection successful
        """
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from robot (mock)."""
        self.connected = False

    def is_connected(self) -> bool:
        """Check if connected to robot.

        Returns:
            True if connected
        """
        return self.connected

    def set_velocity(
        self,
        linear_x: float,
        linear_y: float,
        angular_z: float
    ) -> bool:
        """Set robot velocity (mock).

        Args:
            linear_x: Forward velocity (m/s)
            linear_y: Lateral velocity (m/s)
            angular_z: Angular velocity (rad/s)

        Returns:
            True if command sent successfully
        """
        if not self.connected:
            raise RuntimeError("Not connected to robot")

        self.last_velocity_command = {
            'linear_x': linear_x,
            'linear_y': linear_y,
            'angular_z': angular_z,
            'timestamp': time.time()
        }
        self.command_history.append(self.last_velocity_command)
        return True

    def get_imu_data(self) -> MockIMUData:
        """Get IMU data (mock).

        Returns:
            Mock IMU data
        """
        self.imu_data.timestamp = time.time()
        return self.imu_data

    def get_odometry_data(self) -> MockOdometryData:
        """Get odometry data (mock).

        Returns:
            Mock odometry data
        """
        self.odometry_data.timestamp = time.time()
        return self.odometry_data

    def get_battery_level(self) -> float:
        """Get battery level (mock).

        Returns:
            Battery level (0-100%)
        """
        return self.battery_level

    def set_battery_level(self, level: float) -> None:
        """Set battery level for testing.

        Args:
            level: Battery level (0-100%)
        """
        self.battery_level = max(0.0, min(100.0, level))

    def emergency_stop(self) -> bool:
        """Trigger emergency stop (mock).

        Returns:
            True if successful
        """
        return self.set_velocity(0.0, 0.0, 0.0)

    def get_command_history(self) -> list:
        """Get history of velocity commands.

        Returns:
            List of velocity commands
        """
        return self.command_history.copy()

    def clear_command_history(self) -> None:
        """Clear command history."""
        self.command_history.clear()
