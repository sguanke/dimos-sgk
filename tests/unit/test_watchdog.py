"""Unit tests for watchdog module.

CRITICAL: This module requires 100% test coverage as it is safety-critical.
"""

import pytest
import time
from unittest.mock import patch, mock_open, MagicMock
from threading import Event

from src.safety.watchdog import (
    Watchdog, ComponentType, ComponentStatus
)


@pytest.fixture
def mock_config():
    """Mock watchdog configuration."""
    return {
        'watchdog': {
            'target_timeout': 2.0,
            'pose_timeout': 0.5,
            'command_timeout': 1.0,
            'heartbeat_interval': 0.5
        }
    }


@pytest.fixture
def timeout_callback():
    """Create mock timeout callback."""
    return MagicMock()


@pytest.fixture
def watchdog(mock_config, timeout_callback):
    """Create Watchdog with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                return Watchdog(on_timeout_callback=timeout_callback)


class TestWatchdog:
    """Test Watchdog class - SAFETY CRITICAL."""

    def test_initialization(self, watchdog):
        """Test watchdog initialization."""
        assert watchdog.target_timeout == 2.0
        assert watchdog.pose_timeout == 0.5
        assert watchdog.command_timeout == 1.0
        assert watchdog.heartbeat_interval == 0.5
        assert len(watchdog._components) == 3

    def test_start(self, watchdog):
        """Test starting watchdog monitoring."""
        watchdog.start()

        assert watchdog._running is True
        assert watchdog._monitor_thread is not None

        watchdog.stop()

    def test_start_already_running(self, watchdog):
        """Test starting when already running."""
        watchdog.start()
        watchdog.start()

        assert watchdog._running is True

        watchdog.stop()

    def test_stop(self, watchdog):
        """Test stopping watchdog monitoring."""
        watchdog.start()
        time.sleep(0.1)
        watchdog.stop()

        assert watchdog._running is False

    def test_stop_not_running(self, watchdog):
        """Test stopping when not running."""
        watchdog.stop()

        assert watchdog._running is False

    def test_heartbeat(self, watchdog):
        """Test receiving heartbeat from component."""
        initial_time = watchdog._components[ComponentType.PERCEPTION].last_heartbeat

        time.sleep(0.01)
        watchdog.heartbeat(ComponentType.PERCEPTION)

        assert watchdog._components[ComponentType.PERCEPTION].last_heartbeat > initial_time
        assert watchdog._components[ComponentType.PERCEPTION].is_healthy is True

    def test_update_target_detected(self, watchdog):
        """Test updating target detection timestamp."""
        initial_time = watchdog._components[ComponentType.PERCEPTION].last_data_update

        time.sleep(0.01)
        watchdog.update_target_detected()

        assert watchdog._components[ComponentType.PERCEPTION].last_data_update > initial_time

    def test_update_pose_received(self, watchdog):
        """Test updating pose reception timestamp."""
        initial_time = watchdog._components[ComponentType.LOCALIZATION].last_data_update

        time.sleep(0.01)
        watchdog.update_pose_received()

        assert watchdog._components[ComponentType.LOCALIZATION].last_data_update > initial_time

    def test_update_command_sent(self, watchdog):
        """Test updating command sent timestamp."""
        initial_time = watchdog._components[ComponentType.NAVIGATION].last_data_update

        time.sleep(0.01)
        watchdog.update_command_sent()

        assert watchdog._components[ComponentType.NAVIGATION].last_data_update > initial_time

    def test_target_timeout_triggers(self, watchdog, timeout_callback):
        """Test that target timeout triggers callback."""
        watchdog._components[ComponentType.PERCEPTION].last_data_update = time.time() - 3.0
        watchdog._components[ComponentType.PERCEPTION].is_healthy = True

        watchdog._check_timeouts()

        assert watchdog._components[ComponentType.PERCEPTION].is_healthy is False
        timeout_callback.assert_called_once()

    def test_pose_timeout_triggers(self, watchdog, timeout_callback):
        """Test that pose timeout triggers callback."""
        watchdog._components[ComponentType.LOCALIZATION].last_data_update = time.time() - 1.0
        watchdog._components[ComponentType.LOCALIZATION].is_healthy = True

        watchdog._check_timeouts()

        assert watchdog._components[ComponentType.LOCALIZATION].is_healthy is False
        timeout_callback.assert_called_once()

    def test_command_timeout_triggers(self, watchdog, timeout_callback):
        """Test that command timeout triggers callback."""
        watchdog._components[ComponentType.NAVIGATION].last_data_update = time.time() - 2.0
        watchdog._components[ComponentType.NAVIGATION].is_healthy = True

        watchdog._check_timeouts()

        assert watchdog._components[ComponentType.NAVIGATION].is_healthy is False
        timeout_callback.assert_called_once()

    def test_heartbeat_timeout_triggers(self, watchdog, timeout_callback):
        """Test that heartbeat timeout triggers callback."""
        watchdog._components[ComponentType.PERCEPTION].last_heartbeat = time.time() - 2.0
        watchdog._components[ComponentType.PERCEPTION].is_healthy = True

        watchdog._check_timeouts()

        assert watchdog._components[ComponentType.PERCEPTION].is_healthy is False
        timeout_callback.assert_called()

    def test_get_status(self, watchdog):
        """Test getting component status."""
        status = watchdog.get_status()

        assert len(status) == 3
        assert 'perception' in status
        assert 'navigation' in status
        assert 'localization' in status
        assert 'is_healthy' in status['perception']

    def test_is_all_healthy_true(self, watchdog):
        """Test all healthy check when all are healthy."""
        for component in watchdog._components.values():
            component.is_healthy = True

        assert watchdog.is_all_healthy() is True

    def test_is_all_healthy_false(self, watchdog):
        """Test all healthy check when one is unhealthy."""
        watchdog._components[ComponentType.PERCEPTION].is_healthy = False

        assert watchdog.is_all_healthy() is False

    def test_reset_component(self, watchdog):
        """Test resetting component status."""
        watchdog._components[ComponentType.PERCEPTION].is_healthy = False
        watchdog._components[ComponentType.PERCEPTION].timeout_count = 5

        watchdog.reset_component(ComponentType.PERCEPTION)

        assert watchdog._components[ComponentType.PERCEPTION].is_healthy is True

    def test_timeout_count_increments(self, watchdog, timeout_callback):
        """Test that timeout count increments on timeout."""
        initial_count = watchdog._components[ComponentType.PERCEPTION].timeout_count

        watchdog._components[ComponentType.PERCEPTION].last_data_update = time.time() - 3.0
        watchdog._components[ComponentType.PERCEPTION].is_healthy = True
        watchdog._check_timeouts()

        assert watchdog._components[ComponentType.PERCEPTION].timeout_count > initial_count

    def test_monitor_loop_runs(self, watchdog):
        """Test that monitor loop runs without errors."""
        watchdog.start()
        time.sleep(0.2)
        watchdog.stop()

    def test_callback_exception_handled(self, watchdog):
        """Test that callback exceptions are handled."""
        def failing_callback(component_type, reason):
            raise Exception("Test exception")

        watchdog._on_timeout_callback = failing_callback
        watchdog._components[ComponentType.PERCEPTION].last_data_update = time.time() - 3.0
        watchdog._components[ComponentType.PERCEPTION].is_healthy = True

        watchdog._check_timeouts()

    def test_no_callback_provided(self, mock_config):
        """Test watchdog without callback."""
        with patch('builtins.open', mock_open(read_data="")):
            with patch('yaml.safe_load', return_value=mock_config):
                with patch('pathlib.Path.exists', return_value=False):
                    watchdog = Watchdog(on_timeout_callback=None)

                    watchdog._components[ComponentType.PERCEPTION].last_data_update = time.time() - 3.0
                    watchdog._components[ComponentType.PERCEPTION].is_healthy = True
                    watchdog._check_timeouts()

    def test_load_config_failure(self):
        """Test fallback to defaults on config load failure."""
        with patch('builtins.open', side_effect=Exception("File not found")):
            watchdog = Watchdog()

            assert watchdog.target_timeout == 2.0
            assert watchdog.pose_timeout == 0.5

    def test_component_status_dataclass(self):
        """Test ComponentStatus dataclass."""
        status = ComponentStatus(
            component_type=ComponentType.PERCEPTION,
            last_heartbeat=123.456,
            last_data_update=123.456,
            is_healthy=True,
            timeout_count=0
        )

        assert status.component_type == ComponentType.PERCEPTION
        assert status.is_healthy is True
        assert status.timeout_count == 0

    def test_component_type_enum(self):
        """Test ComponentType enum values."""
        assert ComponentType.PERCEPTION.value == "perception"
        assert ComponentType.NAVIGATION.value == "navigation"
        assert ComponentType.LOCALIZATION.value == "localization"

    def test_all_components_initialized(self, watchdog):
        """Test that all component types are initialized."""
        for component_type in ComponentType:
            assert component_type in watchdog._components

    def test_multiple_heartbeats(self, watchdog):
        """Test multiple heartbeats from same component."""
        for _ in range(5):
            watchdog.heartbeat(ComponentType.PERCEPTION)
            time.sleep(0.01)

        assert watchdog._components[ComponentType.PERCEPTION].is_healthy is True
        assert watchdog._components[ComponentType.PERCEPTION].timeout_count == 0

    def test_timeout_only_triggers_once(self, watchdog, timeout_callback):
        """Test that timeout only triggers once until reset."""
        watchdog._components[ComponentType.PERCEPTION].last_data_update = time.time() - 3.0
        watchdog._components[ComponentType.PERCEPTION].is_healthy = True

        watchdog._check_timeouts()
        call_count_1 = timeout_callback.call_count

        watchdog._check_timeouts()
        call_count_2 = timeout_callback.call_count

        assert call_count_2 == call_count_1

    def test_status_includes_all_fields(self, watchdog):
        """Test that status includes all required fields."""
        status = watchdog.get_status()

        for component_name in status.values():
            assert 'is_healthy' in component_name
            assert 'last_heartbeat_age' in component_name
            assert 'last_data_age' in component_name
            assert 'timeout_count' in component_name

    def test_concurrent_updates(self, watchdog):
        """Test concurrent updates to different components."""
        watchdog.update_target_detected()
        watchdog.update_pose_received()
        watchdog.update_command_sent()
        watchdog.heartbeat(ComponentType.PERCEPTION)
        watchdog.heartbeat(ComponentType.NAVIGATION)
        watchdog.heartbeat(ComponentType.LOCALIZATION)

        assert watchdog.is_all_healthy() is True
