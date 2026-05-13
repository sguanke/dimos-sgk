"""Conftest for pytest configuration and shared fixtures.

This file provides common fixtures and configuration for all tests.
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_frame():
    """Provide a sample camera frame for testing."""
    import numpy as np
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_frame_hd():
    """Provide a sample HD camera frame for testing."""
    import numpy as np
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def mock_go2_client():
    """Provide a mock Go2 SDK client."""
    from tests.mocks.mock_go2 import MockGo2SDK
    client = MockGo2SDK()
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture
def mock_camera():
    """Provide a mock camera."""
    from tests.mocks.mock_camera import MockCamera
    camera = MockCamera()
    camera.open()
    yield camera
    camera.close()


@pytest.fixture
def mock_message_bus():
    """Provide a mock dimos message bus."""
    from tests.mocks.mock_dimos import MockMessageBus
    return MockMessageBus()


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration between tests."""
    import logging
    # Clear all handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    # Reset level
    logging.root.setLevel(logging.WARNING)
    yield
    # Cleanup after test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)


@pytest.fixture
def temp_log_dir(tmp_path):
    """Provide a temporary directory for log files."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def temp_config_dir(tmp_path):
    """Provide a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir
