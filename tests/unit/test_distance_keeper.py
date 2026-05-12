"""Unit tests for distance_keeper module."""

import pytest
from unittest.mock import patch, mock_open

from src.control.distance_keeper import DistanceKeeper, DistanceCommand


@pytest.fixture
def mock_config():
    """Mock configuration data."""
    return {
        'go2': {
            'max_linear_velocity': 0.8,
            'max_acceleration': 0.5
        },
        'following': {
            'target_distance': 2.0,
            'distance_tolerance': 0.3,
            'emergency_distance': 0.5
        }
    }


@pytest.fixture
def keeper(mock_config):
    """Create DistanceKeeper with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                return DistanceKeeper()


class TestDistanceKeeper:
    """Test DistanceKeeper class."""

    def test_initialization(self, keeper):
        """Test keeper initialization."""
        assert keeper.target_distance == 2.0
        assert keeper.distance_tolerance == 0.3
        assert keeper.emergency_distance == 0.5
        assert keeper.max_linear == 0.8

    def test_emergency_stop_triggered(self, keeper):
        """Test emergency stop when too close."""
        command = keeper.compute_distance_command(0.3)

        assert command.emergency_stop is True
        assert command.should_stop is True
        assert command.target_linear_velocity == 0.0

    def test_within_tolerance_maintain(self, keeper):
        """Test maintaining distance within tolerance."""
        command = keeper.compute_distance_command(2.0)

        assert command.emergency_stop is False
        assert command.should_stop is False

    def test_too_close_slow_down(self, keeper):
        """Test slowing down when too close."""
        command = keeper.compute_distance_command(1.5)

        assert command.emergency_stop is False
        assert command.target_linear_velocity < keeper.max_linear

    def test_too_far_speed_up(self, keeper):
        """Test speeding up when too far."""
        command = keeper.compute_distance_command(3.0)

        assert command.emergency_stop is False
        assert command.should_stop is False
        assert command.target_linear_velocity > 0

    def test_at_emergency_distance(self, keeper):
        """Test behavior at exact emergency distance."""
        command = keeper.compute_distance_command(0.5)

        assert command.emergency_stop is True

    def test_at_min_distance(self, keeper):
        """Test behavior at minimum distance."""
        command = keeper.compute_distance_command(1.7)

        assert command.emergency_stop is False

    def test_at_max_distance(self, keeper):
        """Test behavior at maximum distance."""
        command = keeper.compute_distance_command(2.3)

        assert command.emergency_stop is False

    def test_compute_maintain_velocity(self, keeper):
        """Test maintain velocity computation."""
        velocity = keeper._compute_maintain_velocity(0.1)

        assert velocity >= 0.0
        assert velocity <= keeper.max_linear * 0.5

    def test_compute_slowdown_velocity(self, keeper):
        """Test slowdown velocity computation."""
        velocity = keeper._compute_slowdown_velocity(1.0)

        assert velocity >= 0.0
        assert velocity <= keeper.max_linear * 0.3

    def test_compute_slowdown_at_emergency(self, keeper):
        """Test slowdown at emergency distance."""
        velocity = keeper._compute_slowdown_velocity(0.5)
        assert velocity == 0.0

    def test_compute_speedup_velocity(self, keeper):
        """Test speedup velocity computation."""
        velocity = keeper._compute_speedup_velocity(1.0)

        assert velocity > 0.0
        assert velocity <= keeper.max_linear

    def test_compute_speedup_large_error(self, keeper):
        """Test speedup with large distance error."""
        velocity = keeper._compute_speedup_velocity(5.0)

        assert velocity == keeper.max_linear

    def test_clamp(self, keeper):
        """Test value clamping."""
        assert keeper._clamp(5.0, 0.0, 10.0) == 5.0
        assert keeper._clamp(-5.0, 0.0, 10.0) == 0.0
        assert keeper._clamp(15.0, 0.0, 10.0) == 10.0

    def test_is_safe_distance_safe(self, keeper):
        """Test safe distance check."""
        assert keeper.is_safe_distance(1.0) is True
        assert keeper.is_safe_distance(2.0) is True

    def test_is_safe_distance_unsafe(self, keeper):
        """Test unsafe distance check."""
        assert keeper.is_safe_distance(0.3) is False
        assert keeper.is_safe_distance(0.5) is True

    def test_is_within_tolerance_yes(self, keeper):
        """Test within tolerance check."""
        assert keeper.is_within_tolerance(2.0) is True
        assert keeper.is_within_tolerance(1.8) is True
        assert keeper.is_within_tolerance(2.2) is True

    def test_is_within_tolerance_no(self, keeper):
        """Test outside tolerance check."""
        assert keeper.is_within_tolerance(1.5) is False
        assert keeper.is_within_tolerance(2.5) is False

    def test_distance_command_dataclass(self):
        """Test DistanceCommand dataclass."""
        cmd = DistanceCommand(
            target_linear_velocity=0.5,
            should_stop=False,
            emergency_stop=False,
            reason="Test"
        )

        assert cmd.target_linear_velocity == 0.5
        assert cmd.should_stop is False
        assert cmd.emergency_stop is False
        assert cmd.reason == "Test"

    def test_default_config(self, keeper):
        """Test default configuration."""
        config = keeper._default_config()

        assert 'go2' in config
        assert 'following' in config
        assert config['following']['target_distance'] == 2.0

    def test_various_distances(self, keeper):
        """Test command generation for various distances."""
        distances = [0.3, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]

        for dist in distances:
            command = keeper.compute_distance_command(dist)
            assert isinstance(command, DistanceCommand)
            assert command.target_linear_velocity >= 0.0
            assert command.target_linear_velocity <= keeper.max_linear
