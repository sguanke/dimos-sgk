"""Pytest configuration for simulation tests."""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def video_generator():
    """Provide video generator for tests."""
    from tests.simulation.fixtures.test_data import VideoGenerator
    return VideoGenerator()


@pytest.fixture(scope="session")
def sensor_data_generator():
    """Provide sensor data generator for tests."""
    from tests.simulation.fixtures.test_data import SensorDataGenerator
    return SensorDataGenerator()


@pytest.fixture(scope="session")
def trajectory_generator():
    """Provide trajectory generator for tests."""
    from tests.simulation.fixtures.test_data import TrajectoryGenerator
    return TrajectoryGenerator()


@pytest.fixture
def test_scenarios():
    """Provide pre-defined test scenarios."""
    from tests.simulation.fixtures.test_data import TestScenarios
    return TestScenarios()


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Mark all simulation tests as slow
        if "simulation" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.simulation)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "simulation: marks tests as simulation tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
