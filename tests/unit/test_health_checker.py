"""Unit tests for health_checker module.

Tests the system health monitoring functionality.
CRITICAL: This module requires 100% test coverage.
"""

import pytest
import time
import tempfile
from unittest.mock import Mock, patch
from src.safety.health_checker import (
    HealthChecker,
    HealthStatus,
    SystemMetrics,
    HealthReport
)


@pytest.fixture
def temp_config():
    """Create a temporary config file."""
    config_content = """
health:
  cpu_warning_threshold: 80
  memory_warning_threshold: 90
  fps_warning_threshold: 20
  battery_warning_threshold: 20
  battery_critical_threshold: 10
  network_latency_warning_ms: 100
  check_interval: 0.1
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        return f.name


@pytest.fixture
def warning_callback():
    """Create a mock warning callback."""
    return Mock()


@pytest.fixture
def critical_callback():
    """Create a mock critical callback."""
    return Mock()


@pytest.fixture
def health_checker(temp_config, warning_callback, critical_callback):
    """Create a HealthChecker instance."""
    return HealthChecker(
        config_path=temp_config,
        warning_callback=warning_callback,
        critical_callback=critical_callback
    )


@pytest.fixture
def health_checker_no_config(warning_callback, critical_callback):
    """Create a HealthChecker with default config."""
    return HealthChecker(
        config_path="nonexistent.yaml",
        warning_callback=warning_callback,
        critical_callback=critical_callback
    )


class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_health_status_values(self):
        """Test all health status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.CRITICAL.value == "critical"


class TestSystemMetrics:
    """Test SystemMetrics dataclass."""

    def test_system_metrics_creation(self):
        """Test creating SystemMetrics."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=60.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=50.0
        )
        assert metrics.cpu_percent == 50.0
        assert metrics.memory_percent == 60.0
        assert metrics.camera_fps == 30.0
        assert metrics.battery_percent == 80.0
        assert metrics.network_latency_ms == 50.0


class TestHealthReport:
    """Test HealthReport dataclass."""

    def test_health_report_creation(self):
        """Test creating HealthReport."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=60.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=50.0
        )
        report = HealthReport(
            timestamp=time.time(),
            status=HealthStatus.HEALTHY,
            metrics=metrics,
            warnings=[],
            recommendations=[]
        )
        assert report.status == HealthStatus.HEALTHY
        assert len(report.warnings) == 0
        assert len(report.recommendations) == 0


class TestHealthChecker:
    """Test HealthChecker class."""

    def test_initialization_with_config(self, health_checker):
        """Test initialization with config file."""
        assert health_checker.config['cpu_warning_threshold'] == 80
        assert health_checker.config['memory_warning_threshold'] == 90
        assert health_checker.config['fps_warning_threshold'] == 20
        assert health_checker.config['battery_warning_threshold'] == 20
        assert health_checker.config['battery_critical_threshold'] == 10
        assert not health_checker._running

    def test_initialization_without_config(self, health_checker_no_config):
        """Test initialization with default config."""
        assert health_checker_no_config.config['cpu_warning_threshold'] == 80
        assert health_checker_no_config.config['memory_warning_threshold'] == 90

    def test_start(self, health_checker):
        """Test starting health monitoring."""
        assert not health_checker._running

        health_checker.start()

        assert health_checker._running
        assert health_checker._monitor_thread is not None
        assert health_checker._monitor_thread.is_alive()

        health_checker.stop()

    def test_start_when_already_running(self, health_checker):
        """Test starting when already running."""
        health_checker.start()
        assert health_checker._running

        health_checker.start()

        assert health_checker._running

        health_checker.stop()

    def test_stop(self, health_checker):
        """Test stopping health monitoring."""
        health_checker.start()
        assert health_checker._running

        health_checker.stop()

        assert not health_checker._running

    def test_stop_when_not_running(self, health_checker):
        """Test stopping when not running."""
        assert not health_checker._running

        health_checker.stop()

        assert not health_checker._running

    def test_update_camera_fps(self, health_checker):
        """Test updating camera FPS."""
        health_checker.update_camera_fps(30.0)

        assert health_checker._camera_fps == 30.0

    def test_update_frame_received(self, health_checker):
        """Test updating frame counter."""
        # Send multiple frames
        for _ in range(30):
            health_checker.update_frame_received()
            time.sleep(0.033)  # ~30 FPS

        # FPS should be calculated
        assert health_checker._camera_fps > 0

    def test_update_battery_level(self, health_checker):
        """Test updating battery level."""
        health_checker.update_battery_level(75.0)

        assert health_checker._battery_percent == 75.0

    def test_update_battery_level_clamping(self, health_checker):
        """Test battery level clamping."""
        health_checker.update_battery_level(150.0)
        assert health_checker._battery_percent == 100.0

        health_checker.update_battery_level(-10.0)
        assert health_checker._battery_percent == 0.0

    def test_update_network_latency(self, health_checker):
        """Test updating network latency."""
        health_checker.update_network_latency(50.0)

        assert health_checker._network_latency_ms == 50.0

    def test_get_current_metrics_initially_none(self, health_checker):
        """Test getting metrics before monitoring starts."""
        metrics = health_checker.get_current_metrics()

        assert metrics is None

    def test_get_current_metrics_after_start(self, health_checker):
        """Test getting metrics after monitoring starts."""
        health_checker.start()

        # Wait for first check
        time.sleep(0.2)

        metrics = health_checker.get_current_metrics()

        assert metrics is not None
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0

        health_checker.stop()

    def test_get_health_status_initially_healthy(self, health_checker):
        """Test health status before monitoring."""
        status = health_checker.get_health_status()

        assert status == HealthStatus.HEALTHY

    def test_get_health_report_initially_none(self, health_checker):
        """Test health report before monitoring."""
        report = health_checker.get_health_report()

        assert report is None

    def test_get_health_report_after_start(self, health_checker):
        """Test health report after monitoring starts."""
        health_checker.start()

        # Wait for first check
        time.sleep(0.2)

        report = health_checker.get_health_report()

        assert report is not None
        assert report.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]

        health_checker.stop()

    @patch('psutil.cpu_percent', return_value=85.0)
    def test_analyze_health_high_cpu(self, mock_cpu, health_checker):
        """Test health analysis with high CPU usage."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=85.0,
            memory_percent=50.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert any("CPU" in w for w in report.warnings)
        assert len(report.recommendations) > 0

    @patch('psutil.virtual_memory')
    def test_analyze_health_high_memory(self, mock_memory, health_checker):
        """Test health analysis with high memory usage."""
        mock_memory.return_value.percent = 95.0

        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=95.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert any("memory" in w.lower() for w in report.warnings)

    def test_analyze_health_low_fps(self, health_checker):
        """Test health analysis with low camera FPS."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=50.0,
            camera_fps=15.0,  # Below threshold of 20
            battery_percent=80.0,
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert any("FPS" in w for w in report.warnings)

    def test_analyze_health_low_battery_warning(self, health_checker):
        """Test health analysis with low battery (warning level)."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=50.0,
            camera_fps=30.0,
            battery_percent=15.0,  # Below warning threshold of 20
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert any("battery" in w.lower() for w in report.warnings)

    def test_analyze_health_low_battery_critical(self, health_checker):
        """Test health analysis with critically low battery."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=50.0,
            camera_fps=30.0,
            battery_percent=5.0,  # Below critical threshold of 10
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.CRITICAL
        assert any("CRITICAL" in w for w in report.warnings)
        assert any("Stop robot" in r for r in report.recommendations)

    def test_analyze_health_high_network_latency(self, health_checker):
        """Test health analysis with high network latency."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=50.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=150.0  # Above threshold of 100
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert any("latency" in w.lower() for w in report.warnings)

    def test_analyze_health_all_healthy(self, health_checker):
        """Test health analysis with all metrics healthy."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_percent=50.0,
            camera_fps=30.0,
            battery_percent=80.0,
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.HEALTHY
        assert len(report.warnings) == 0

    def test_analyze_health_multiple_issues(self, health_checker):
        """Test health analysis with multiple issues."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=85.0,  # High
            memory_percent=95.0,  # High
            camera_fps=15.0,  # Low
            battery_percent=80.0,
            network_latency_ms=50.0
        )

        report = health_checker._analyze_health(metrics)

        assert report.status == HealthStatus.DEGRADED
        assert len(report.warnings) >= 3
        assert len(report.recommendations) >= 3

    def test_monitor_loop_calls_callbacks(self, health_checker, warning_callback):
        """Test that monitor loop calls warning callback."""
        # Set low FPS to trigger warning
        health_checker.update_camera_fps(10.0)

        health_checker.start()

        # Wait for monitoring cycle
        time.sleep(0.3)

        # Warning callback should be called
        assert warning_callback.called

        health_checker.stop()

    def test_monitor_loop_calls_critical_callback(self, health_checker, critical_callback):
        """Test that monitor loop calls critical callback."""
        # Set critical battery level
        health_checker.update_battery_level(5.0)

        health_checker.start()

        # Wait for monitoring cycle
        time.sleep(0.3)

        # Critical callback should be called
        assert critical_callback.called

        health_checker.stop()

    def test_monitor_loop_exception_handling(self, health_checker):
        """Test that exceptions in monitor loop are handled."""
        health_checker.start()

        # Wait for a few cycles
        time.sleep(0.3)

        # Should still be running despite any errors
        assert health_checker._running

        health_checker.stop()

    def test_shutdown(self, health_checker):
        """Test shutting down health checker."""
        health_checker.start()
        assert health_checker._running

        health_checker.shutdown()

        assert not health_checker._running

    def test_thread_safety_concurrent_updates(self, health_checker):
        """Test thread safety with concurrent metric updates."""
        import threading

        def update_metrics():
            for i in range(100):
                health_checker.update_camera_fps(30.0 + i % 10)
                health_checker.update_battery_level(80.0 - i % 20)
                time.sleep(0.001)

        threads = [threading.Thread(target=update_metrics) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash
        assert health_checker._camera_fps >= 0
        assert health_checker._battery_percent >= 0

    def test_no_callbacks(self):
        """Test health checker without callbacks."""
        checker_no_callbacks = HealthChecker(
            config_path="nonexistent.yaml",
            warning_callback=None,
            critical_callback=None
        )

        # Set low battery to trigger critical
        checker_no_callbacks.update_battery_level(5.0)

        checker_no_callbacks.start()

        # Wait for monitoring
        time.sleep(0.3)

        # Should not crash even without callbacks
        assert checker_no_callbacks._running

        checker_no_callbacks.stop()

    def test_collect_metrics(self, health_checker):
        """Test collecting system metrics."""
        health_checker.update_camera_fps(30.0)
        health_checker.update_battery_level(75.0)
        health_checker.update_network_latency(50.0)

        metrics = health_checker._collect_metrics()

        assert metrics.camera_fps == 30.0
        assert metrics.battery_percent == 75.0
        assert metrics.network_latency_ms == 50.0
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
