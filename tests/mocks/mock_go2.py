"""Mock Go2 SDK for testing."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MockWheelEncoderData:
    """Mock wheel encoder data."""
    left_ticks: int = 0
    right_ticks: int = 0
    timestamp: float = 0.0


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


class MockGo2SDK:
    """Mock Go2 SDK for testing."""

    def __init__(self):
        self.connected = False
        self.last_command = None
        self.encoder_data = MockWheelEncoderData()
        self.imu_data = MockIMUData()

    def connect(self, ip: str) -> bool:
        """Mock connection."""
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Mock disconnection."""
        self.connected = False

    def send_velocity_command(self, linear: float, angular: float) -> bool:
        """Mock velocity command."""
        self.last_command = (linear, angular)
        return True

    def get_encoder_data(self) -> MockWheelEncoderData:
        """Mock encoder data."""
        return self.encoder_data

    def get_imu_data(self) -> MockIMUData:
        """Mock IMU data."""
        return self.imu_data

    def get_battery_level(self) -> float:
        """Mock battery level."""
        return 100.0
