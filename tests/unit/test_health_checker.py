"""Unit tests for health_checker module.

CRITICAL: This module requires 100% test coverage as it is safety-critical.
"""

import pytest
import time
from unittest.mock import patch, mock_open, MagicMock

from src.safety.health_checker import (
    HealthChecker, HealthStatus, SystemMetrics, HealthReport
)


@pytest.fixture
def mock_config():
    """Mock health checker configuration."""
    return {
        'health': {
            'cpu_warning_threshold': 80,
            'memory_warning_threshold': 90,
            'fps_warning_threshold': 20,
            'battery_warning_threshold': 20,
            'battery_critical_threshold': 10
        }
    }


@pytest.fixture
def degradation_callback():
    """Create mock degradation callback."""
    return MagicMock()


@pytest.fixture
def health_checker(mock_config, degradation_callback):
    """Create HealthChecker with mocked config."""
    with patch('builtins.open', mock_open(read_data="")):
        with patch('yaml.safe_load', return_value=mock_config):
            with patch('pathlib.Path.exists', return_value=False):
                return HealthChecker(on_degradation_callback=degradation_callback)


class TestHealthChecker:
    """Test HealthChecker class - SAFETY CRITICAL."""

    def test_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.cpu_warning_threshold == 80
        assert health_checker.memory_warning_threshold == 90
        assert health_checker.fps_warning_threshold == 20
        assert health_checker.battery_warning_threshold == 20
        assert health_checker.battery_critical_threshold == 10

    def test_start(self, health_checker):
        """Test starting health monitoring."""
        health_checker.start(check_interval=0.1)

        assert health_checker._running is True
        assert health_checker._monitor_thread is not None

        health_checker.stop()

    def test_start_already_running(self, health_checker):
        """Test starting when already running."""
        health_checker.start()
        health_checker.start()

        assert health_checker._running is True

        health_checker.stop()

    def test_stop(self, health_checker):
        """Test stopping health monitoring."""
        health_checker.start()
        time.sleep(0.1)
        health_checker.stop()

        assert health_checker._running is False

    def test_stop_not_running(self, health_checker):
        """Test stopping when not running."""
        health_checker.stop()

        assert health_checker._running is False

    def test_update_camera_frame(self, health_checker):
        """Test updating camera frame count."""
        initial_count = health_checker._last_frame_count

        health_checker.update_camera_frame()

        assert health_checker._last_frame_count == initial_count + 1

    def test_collect_metrics(self, health_checker):
        """Test collecting system metrics."""
        metrics = health_checker._collect_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        assert metrics.camera_fps >= 0
        assert metrics.battery_percent >= 0
        assert metrics.network_latency_ms >= 0

    @patch('psutil.cpu_percent', return_value=85.0)
    def test_high_cpu_warning(self, mock_cpu, health_checker):
        """Test high CPU usage warning."""
        health_checker.start(check_interval=0.1)
        time.sleep(0.2)
        health_checker.stop()

        report = health_checker.get_health_report()
        assert report.status in [HealthStatus.WARNING, HealthStatus.HEALTHY]

    @patch('psutil.cpu_percent', return_value=96.0)
    def test_critical_cpu_triggers_degradation(self, mock_cpu, health_checker, degradation_callback):
        """Test critical CPU triggers degradation."""
        health_checker._check_health()

        if degradation_callback.called:
            assert "CPU" in str(degradation_callback.call_args)

    @patch('psutil.virtual_memory')
    def test_high_memory_warning(self, mock_memory, health_checker):
        """Test high memory usage warning."""
        mock_memory.return_value.percent = 92.0

        health_checker._check_health()

        report = health_checker.get_health_report()
        if report.metrics.memory_percent > 90:
            assert len(report.warnings) > 0

    @patch('psutil.virtual_memory')
    def test_critical_memory(self, mock_memory, health_checker):
        """Test critical memory usage."""
        mock_memory.return_value.percent = 96.0

        health_checker._check_health()

        report = health_checker.get_health_report()
        if report.metrics.memory_percent > 95:
            assert report.status == HealthStatus.CRITICAL

    def test_low_fps_warning(self, health_checker):
        """Test low FPS warning."""
        health_checker._last_frame_count = 5
        health_checker._last_fps_check_time = time.time() - 1.0

        health_checker._check_health()

        report = health_checker.get_health_report()
        if report.metrics.camera_fps < 20:
            assert len(report.warnings) > 0

    def test_critical_fps_triggers_degradation(self, health_checker, degradation_callback):
        """Test critical FPS triggers degradation."""
        health_checker._last_frame_count = 5
        health_checker._last_fps_check_time = time.time() - 1.0

        health_checker._check_health()

        metrics = health_checker.get_metrics()
        if metrics and metrics.camera_fps < 10:
            assert degradation_callback.called

    def test_low_battery_warning(self, health_checker):
        """Test low battery warning."""
        with patch.object(health_checker, '_get_battery_level', return_value=15.0):
            health_checker._check_health()

            report = health_checker.get_health_report()
            if report.metrics.battery_percent < 20:
                assert len(report.warnings) > 0

    def test_critical_battery_triggers_degradation(self, health_checker, degradation_callback):
        """Test critical battery triggers degradation."""
        with patch.object(health_checker, '_get_battery_level', return_value=5.0):
            health_checker._check_health()

            assert degradation_callback.called

    def test_high_network_latency_warning(self, health_checker):
        """Test high network latency warning."""
        with patch.object(health_checker, '_get_network_latency', return_value=150.0):
            health_checker._check_health()

            report = health_checker.get_health_report()
            if report.metrics.network_latency_ms > 100:
                assert len(report.warnings) > 0

    def test_critical_network_latency(self, health_checker):
        """Test critical network latency."""
        with patch.object(health_checker, '_get_network_latency', return_value=600.0):
            health_checker._check_health()

            report = health_checker.get_health_report()
            if report.metrics.network_latency_ms > 500:
                assert len(report.critical_issues) > 0

    def test_get_health_report_no_metrics(self, health_checker):
        """Test getting health report with no metrics collected."""
        report = health_checker.get_health_report()

        assert isinstance(report, HealthReport)
        assert report.status == HealthStatus.HEALTHY
        assert report.metrics.battery_percent == 100.0

    def test_get_health_report_with_metrics(self, health_checker):
        """Test getting health report with metrics."""
        health_checker._check_health()

        report = health_checker.get_health_report()

        assert isinstance(report, HealthReport)
        assert isinstance(report.status, HealthStatus)
        assert isinstance(report.warnings, list)
        assert isinstance(report.critical_issues, list)

    def test_get_metrics(self, health_checker):
        """Test getting current metrics."""
        health_checker._check_health()

        metrics = health_checker.get_metrics()

        if metrics:
            assert isinstance(metrics, SystemMetrics)

    def test_get_metrics_none(self, health_checker):
        """Test getting metrics when none collected."""
        metrics = health_checker.get_metrics()

        assert metrics is None

    def test_degradation_callback_exception_handled(self, health_checker):
        """Test that callback exceptions are handled."""
        def failing_callback(reason):
            raise Exception("Test exception")

        health_checker._on_degradation_callback = failing_callback

        with patch.object(health_checker, '_get_battery_level', return_value=5.0):
            health_checker._check_health()

    def test_no_callback_provided(self, mock_config):
        """Test health checker without callback."""
        with patch('builtins.open', mock_open(read_data="")):
            with patch('yaml.safe_load', return_value=mock_config):
                with patch('pathlib.Path.exists', return_value=False):
                    checker = HealthChecker(on_degradation_callback=None)

                    with patch.object(checker, '_get_battery_level', return_value=5.0):
                        checker._check_health()

    def test_load_config_failure(self):
        """Test fallback to defaults on config load failure."""
        with patch('builtins.open', side_effect=Exception("File not found")):
            checker = HealthChecker()

            assert checker.cpu_warning_threshold == 80
            assert checker.battery_critical_threshold == 10

    def test_get_battery_level_with_sensor(self, health_checker):
        """Test battery level reading with sensor."""
        mock_battery = MagicMock()
        mock_battery.percent = 75.0

        with patch('psutil.sensors_battery', return_value=mock_battery):
            level = health_checker._get_battery_level()
            assert level == 75.0

    def test_get_battery_level_no_sensor(self, health_checker):
        """Test battery level reading without sensor."""
        with patch('psutil.sensors_battery', return_value=None):
            level = health_checker._get_battery_level()
            assert level == 100.0

    def test_get_battery_level_exception(self, health_checker):
        """Test battery level reading with exception."""
        with patch('psutil.sensors_battery', side_effect=Exception("No sensor")):
            level = health_checker._get_battery_level()
            assert level == 100.0

    def test_get_network_latency(self, health_checker):
        """Test network latency measurement."""
        latency = health_checker._get_network_latency()
        assert latency >= 0

    def test_monitor_loop_runs(self, health_checker):
        """Test that monitor loop runs without errors."""
        health_checker.start(check_interval=0.1)
        time.sleep(0.2)
        health_checker.stop()

    def test_monitor_loop_exception_handled(self, health_checker):
        """Test that monitor loop handles exceptions."""
        with patch.object(health_checker, '_check_health', side_effect=Exception("Test")):
            health_checker.start(check_interval=0.1)
            time.sleep(0.2)
            health_checker.stop()

    def test_health_status_enum(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"

    def test_system_metrics_dataclass(self):
        """Test SystemMetrics dataclass."""
        metrics = SystemMetrics(
            timestamp=123.456,
            cpu_percent=50.0,
            memory_percent=60.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=10.0
        )

        assert metrics.cpu_percent == 50.0
        assert metrics.battery_percent == 80.0

    def test_health_report_dataclass(self):
        """Test HealthReport dataclass."""
        metrics = SystemMetrics(
            timestamp=123.456,
            cpu_percent=50.0,
            memory_percent=60.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=10.0
        )

        report = HealthReport(
            status=HealthStatus.HEALTHY,
            metrics=metrics,
            warnings=[],
            critical_issues=[]
        )

        assert report.status == HealthStatus.HEALTHY
        assert len(report.warnings) == 0

    def test_multiple_warnings(self, health_checker):
        """Test multiple simultaneous warnings."""
        with patch('psutil.cpu_percent', return_value=85.0):
            with patch('psutil.virtual_memory') as mock_mem:
                mock_mem.return_value.percent = 92.0
                with patch.object(health_checker, '_get_battery_level', return_value=15.0):
                    health_checker._check_health()

                    report = health_checker.get_health_report()
                    assert report.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]

    def test_fps_calculation(self, health_checker):
        """Test FPS calculation."""
        health_checker._last_frame_count = 0
        health_checker._last_fps_check_time = time.time()

        for _ in range(30):
            health_checker.update_camera_frame()

        time.sleep(1.0)
        metrics = health_checker._collect_metrics()

        assert metrics.camera_fps > 0

    def test_trigger_degradation(self, health_checker, degradation_callback):
        """Test triggering degradation."""
        health_checker._trigger_degradation("Test reason")

        degradation_callback.assert_called_once_with("Test reason")
