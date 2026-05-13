"""Unit tests for watchdog module.

Tests the watchdog timer functionality for component monitoring.
CRITICAL: This module requires 100% test coverage.
"""

import pytest
import time
import tempfile
from unittest.mock import Mock, patch
from src.safety.watchdog import (
    Watchdog,
    ComponentStatus,
    ComponentState
)


@pytest.fixture
def temp_config():
    """Create a temporary config file."""
    config_content = """
watchdog:
  target_timeout: 2.0
  pose_timeout: 0.5
  command_timeout: 1.0
  heartbeat_interval: 0.1
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        return f.name


@pytest.fixture
def stop_callback():
    """Create a mock stop callback."""
    return Mock()


@pytest.fixture
def watchdog(temp_config, stop_callback):
    """Create a Watchdog instance."""
    return Watchdog(config_path=temp_config, stop_callback=stop_callback)


@pytest.fixture
def watchdog_no_config(stop_callback):
    """Create a Watchdog with default config."""
    return Watchdog(config_path="nonexistent.yaml", stop_callback=stop_callback)


class TestComponentStatus:
    """Test ComponentStatus enum."""

    def test_component_status_values(self):
        """Test all component status values."""
        assert ComponentStatus.HEALTHY.value == "healthy"
        assert ComponentStatus.DEGRADED.value == "degraded"
        assert ComponentStatus.TIMEOUT.value == "timeout"
        assert ComponentStatus.FAILED.value == "failed"


class TestComponentState:
    """Test ComponentState dataclass."""

    def test_component_state_creation(self):
        """Test creating a ComponentState."""
        state = ComponentState(
            name="test",
            last_heartbeat=time.time(),
            timeout=1.0,
            status=ComponentStatus.HEALTHY,
            message="All good"
        )
        assert state.name == "test"
        assert state.timeout == 1.0
        assert state.status == ComponentStatus.HEALTHY
        assert state.message == "All good"


class TestWatchdog:
    """Test Watchdog class."""

    def test_initialization_with_config(self, watchdog):
        """Test initialization with config file."""
        assert watchdog.config['target_timeout'] == 2.0
        assert watchdog.config['pose_timeout'] == 0.5
        assert watchdog.config['command_timeout'] == 1.0
        assert watchdog.config['heartbeat_interval'] == 0.1
        assert not watchdog._running

    def test_initialization_without_config(self, watchdog_no_config):
        """Test initialization with default config."""
        assert watchdog_no_config.config['target_timeout'] == 2.0
        assert watchdog_no_config.config['pose_timeout'] == 0.5
        assert watchdog_no_config.config['command_timeout'] == 1.0

    def test_initialization_creates_components(self, watchdog):
        """Test that all components are initialized."""
        assert 'perception' in watchdog._components
        assert 'navigation' in watchdog._components
        assert 'localization' in watchdog._components

        for comp in watchdog._components.values():
            assert comp.status == ComponentStatus.HEALTHY

    def test_start(self, watchdog):
        """Test starting watchdog monitoring."""
        assert not watchdog._running

        watchdog.start()

        assert watchdog._running
        assert watchdog._monitor_thread is not None
        assert watchdog._monitor_thread.is_alive()

        watchdog.stop()

    def test_start_when_already_running(self, watchdog):
        """Test starting watchdog when already running."""
        watchdog.start()
        assert watchdog._running

        # Try to start again
        watchdog.start()

        # Should still be running
        assert watchdog._running

        watchdog.stop()

    def test_stop(self, watchdog):
        """Test stopping watchdog monitoring."""
        watchdog.start()
        assert watchdog._running

        watchdog.stop()

        assert not watchdog._running
        # Thread should be cleaned up
        time.sleep(0.2)
        assert watchdog._monitor_thread is None or not watchdog._monitor_thread.is_alive()

    def test_stop_when_not_running(self, watchdog):
        """Test stopping watchdog when not running."""
        assert not watchdog._running

        # Should not raise error
        watchdog.stop()

        assert not watchdog._running

    def test_heartbeat_valid_component(self, watchdog):
        """Test recording heartbeat for valid component."""
        before = watchdog._components['perception'].last_heartbeat
        time.sleep(0.01)

        watchdog.heartbeat('perception')

        after = watchdog._components['perception'].last_heartbeat
        assert after > before

    def test_heartbeat_invalid_component(self, watchdog):
        """Test recording heartbeat for invalid component."""
        # Should not raise error, just log warning
        watchdog.heartbeat('invalid_component')

    def test_update_target_detected_true(self, watchdog):
        """Test updating perception when target is detected."""
        before = watchdog._components['perception'].last_heartbeat
        time.sleep(0.01)

        watchdog.update_target_detected(True)

        after = watchdog._components['perception'].last_heartbeat
        assert after > before

    def test_update_target_detected_false(self, watchdog):
        """Test that no heartbeat is sent when target not detected."""
        before = watchdog._components['perception'].last_heartbeat

        watchdog.update_target_detected(False)

        after = watchdog._components['perception'].last_heartbeat
        assert after == before

    def test_update_pose_received(self, watchdog):
        """Test updating localization when pose is received."""
        before = watchdog._components['localization'].last_heartbeat
        time.sleep(0.01)

        watchdog.update_pose_received()

        after = watchdog._components['localization'].last_heartbeat
        assert after > before

    def test_update_command_sent(self, watchdog):
        """Test updating navigation when command is sent."""
        before = watchdog._components['navigation'].last_heartbeat
        time.sleep(0.01)

        watchdog.update_command_sent()

        after = watchdog._components['navigation'].last_heartbeat
        assert after > before

    def test_get_component_status_valid(self, watchdog):
        """Test getting status of valid component."""
        status = watchdog.get_component_status('perception')

        assert status is not None
        assert status.name == 'perception'
        assert status.status == ComponentStatus.HEALTHY

    def test_get_component_status_invalid(self, watchdog):
        """Test getting status of invalid component."""
        status = watchdog.get_component_status('invalid')

        assert status is None

    def test_get_all_status(self, watchdog):
        """Test getting status of all components."""
        all_status = watchdog.get_all_status()

        assert len(all_status) == 3
        assert 'perception' in all_status
        assert 'navigation' in all_status
        assert 'localization' in all_status

    def test_is_all_healthy_initially(self, watchdog):
        """Test that all components are healthy initially."""
        assert watchdog.is_all_healthy()

    def test_is_all_healthy_after_timeout(self, watchdog, stop_callback):
        """Test health check after component timeout."""
        watchdog.start()

        # Wait for localization to timeout (0.5s timeout + margin)
        time.sleep(0.7)

        assert not watchdog.is_all_healthy()

        watchdog.stop()

    def test_reset(self, watchdog):
        """Test resetting watchdog state."""
        # Trigger a stop
        watchdog._stop_triggered = True

        # Modify component status
        watchdog._components['perception'].status = ComponentStatus.TIMEOUT

        watchdog.reset()

        assert not watchdog._stop_triggered
        assert watchdog._components['perception'].status == ComponentStatus.HEALTHY

    def test_shutdown(self, watchdog):
        """Test shutting down watchdog."""
        watchdog.start()
        assert watchdog._running

        watchdog.shutdown()

        assert not watchdog._running

    def test_monitor_loop_detects_timeout(self, watchdog, stop_callback):
        """Test that monitor loop detects component timeout."""
        watchdog.start()

        # Wait for localization timeout (0.5s + margin)
        time.sleep(0.7)

        # Stop callback should have been called
        assert stop_callback.called

        watchdog.stop()

    def test_monitor_loop_detects_degraded(self, watchdog):
        """Test that monitor loop detects degraded performance."""
        watchdog.start()

        # Wait for degraded threshold (70% of 0.5s = 0.35s)
        time.sleep(0.4)

        status = watchdog.get_component_status('localization')
        # Should be degraded or timeout
        assert status.status in [ComponentStatus.DEGRADED, ComponentStatus.TIMEOUT]

        watchdog.stop()

    def test_monitor_loop_recovery(self, watchdog):
        """Test that components can recover after degradation."""
        watchdog.start()

        # Wait for degradation
        time.sleep(0.4)

        # Send heartbeat to recover
        watchdog.heartbeat('localization')

        # Wait a bit for monitor to update
        time.sleep(0.2)

        status = watchdog.get_component_status('localization')
        assert status.status == ComponentStatus.HEALTHY

        watchdog.stop()

    def test_stop_callback_called_on_timeout(self, watchdog, stop_callback):
        """Test that stop callback is called on timeout."""
        watchdog.start()

        # Wait for timeout
        time.sleep(0.7)

        # Callback should be called with reason
        assert stop_callback.called
        call_args = stop_callback.call_args[0][0]
        assert "Watchdog timeout" in call_args

        watchdog.stop()

    def test_stop_callback_not_called_twice(self, watchdog, stop_callback):
        """Test that stop callback is only called once."""
        watchdog.start()

        # Wait for multiple timeouts
        time.sleep(1.5)

        # Callback should only be called once
        assert stop_callback.call_count == 1

        watchdog.stop()

    def test_stop_callback_exception_handling(self, watchdog):
        """Test that exceptions in stop callback are handled."""
        failing_callback = Mock(side_effect=Exception("Callback failed"))
        watchdog_with_failing_callback = Watchdog(
            config_path="nonexistent.yaml",
            stop_callback=failing_callback
        )

        watchdog_with_failing_callback.start()

        # Wait for timeout
        time.sleep(0.7)

        # Should not crash, just log error
        assert watchdog_with_failing_callback._running

        watchdog_with_failing_callback.stop()

    def test_thread_safety_concurrent_heartbeats(self, watchdog):
        """Test thread safety with concurrent heartbeats."""
        import threading

        def send_heartbeats():
            for _ in range(100):
                watchdog.heartbeat('perception')
                time.sleep(0.001)

        threads = [threading.Thread(target=send_heartbeats) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash
        status = watchdog.get_component_status('perception')
        assert status is not None

    def test_component_timeouts_are_different(self, watchdog):
        """Test that different components have different timeouts."""
        perception_timeout = watchdog._components['perception'].timeout
        navigation_timeout = watchdog._components['navigation'].timeout
        localization_timeout = watchdog._components['localization'].timeout

        assert perception_timeout == 2.0
        assert navigation_timeout == 1.0
        assert localization_timeout == 0.5

    def test_no_stop_callback(self):
        """Test watchdog without stop callback."""
        watchdog_no_callback = Watchdog(
            config_path="nonexistent.yaml",
            stop_callback=None
        )

        watchdog_no_callback.start()

        # Wait for timeout
        time.sleep(0.7)

        # Should not crash even without callback
        assert watchdog_no_callback._stop_triggered

        watchdog_no_callback.stop()
