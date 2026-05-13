"""Health checker for Go2 robot person following system.

This module monitors system health including CPU, memory, camera FPS,
battery level, and network latency. It triggers warnings and graceful
degradation when resources are constrained.

CRITICAL: Health checker enables graceful degradation and prevents
system failures due to resource exhaustion.
"""

import logging
import psutil
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import yaml


class HealthStatus(Enum):
    """Overall system health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """System health metrics."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    camera_fps: float
    battery_percent: float
    network_latency_ms: float


@dataclass
class HealthReport:
    """Health check report."""
    timestamp: float
    status: HealthStatus
    metrics: SystemMetrics
    warnings: list[str]
    recommendations: list[str]


class HealthChecker:
    """Monitor system health and trigger graceful degradation.

    This class monitors:
    - CPU usage (warn if >80%)
    - Memory usage (warn if >90%)
    - Camera frame rate (warn if <20 FPS)
    - Battery level (warn if <20%, stop if <10%)
    - Network latency to Go2 (warn if >100ms)

    When resources are constrained, it recommends graceful degradation
    (e.g., reduce speed, lower detection frequency).
    """

    def __init__(
        self,
        config_path: str = "config/safety_params.yaml",
        warning_callback: Optional[Callable[[str], None]] = None,
        critical_callback: Optional[Callable[[str], None]] = None
    ):
        """Initialize health checker.

        Args:
            config_path: Path to safety configuration file
            warning_callback: Callback for warnings
            critical_callback: Callback for critical issues
        """
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.warning_callback = warning_callback
        self.critical_callback = critical_callback

        # Health state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Metrics tracking
        self._current_metrics: Optional[SystemMetrics] = None
        self._camera_fps = 0.0
        self._battery_percent = 100.0
        self._network_latency_ms = 0.0
        self._last_frame_time = time.time()
        self._frame_count = 0

        self.logger.info("Health checker initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load health checker configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['health']
        except FileNotFoundError:
            # Use default values if config not found
            return {
                'cpu_warning_threshold': 80,
                'memory_warning_threshold': 90,
                'fps_warning_threshold': 20,
                'battery_warning_threshold': 20,
                'battery_critical_threshold': 10,
                'network_latency_warning_ms': 100,
                'check_interval': 1.0
            }

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for health checker."""
        logger = logging.getLogger("HealthChecker")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def start(self) -> None:
        """Start health monitoring."""
        with self._lock:
            if self._running:
                self.logger.warning("Health checker already running")
                return

            self._running = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Health monitoring started")

    def stop(self) -> None:
        """Stop health monitoring."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

        self.logger.info("Health monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        check_interval = self.config.get('check_interval', 1.0)

        while self._running:
            try:
                # Collect metrics
                metrics = self._collect_metrics()

                # Analyze health
                report = self._analyze_health(metrics)

                # Store current metrics
                with self._lock:
                    self._current_metrics = metrics

                # Handle warnings and critical issues
                if report.status == HealthStatus.CRITICAL:
                    for warning in report.warnings:
                        self.logger.critical(warning)
                        if self.critical_callback:
                            self.critical_callback(warning)
                elif report.status == HealthStatus.DEGRADED:
                    for warning in report.warnings:
                        self.logger.warning(warning)
                        if self.warning_callback:
                            self.warning_callback(warning)

                # Log recommendations
                for rec in report.recommendations:
                    self.logger.info(f"Recommendation: {rec}")

            except Exception as e:
                self.logger.error(f"Health check failed: {e}")

            time.sleep(check_interval)

    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics.

        Returns:
            Current system metrics
        """
        with self._lock:
            camera_fps = self._camera_fps
            battery_percent = self._battery_percent
            network_latency_ms = self._network_latency_ms

        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
            camera_fps=camera_fps,
            battery_percent=battery_percent,
            network_latency_ms=network_latency_ms
        )

    def _analyze_health(self, metrics: SystemMetrics) -> HealthReport:
        """Analyze system health based on metrics.

        Args:
            metrics: Current system metrics

        Returns:
            Health report with status and recommendations
        """
        warnings = []
        recommendations = []
        status = HealthStatus.HEALTHY

        # Check CPU usage
        if metrics.cpu_percent > self.config['cpu_warning_threshold']:
            warnings.append(
                f"High CPU usage: {metrics.cpu_percent:.1f}%"
            )
            recommendations.append("Reduce detection frequency or lower resolution")
            status = HealthStatus.DEGRADED

        # Check memory usage
        if metrics.memory_percent > self.config['memory_warning_threshold']:
            warnings.append(
                f"High memory usage: {metrics.memory_percent:.1f}%"
            )
            recommendations.append("Clear caches or reduce tracking history")
            status = HealthStatus.DEGRADED

        # Check camera FPS
        if metrics.camera_fps < self.config['fps_warning_threshold']:
            warnings.append(
                f"Low camera FPS: {metrics.camera_fps:.1f}"
            )
            recommendations.append("Check camera connection or reduce processing load")
            status = HealthStatus.DEGRADED

        # Check battery level
        if metrics.battery_percent < self.config['battery_critical_threshold']:
            warnings.append(
                f"CRITICAL: Battery at {metrics.battery_percent:.1f}%"
            )
            recommendations.append("Stop robot immediately and recharge")
            status = HealthStatus.CRITICAL
        elif metrics.battery_percent < self.config['battery_warning_threshold']:
            warnings.append(
                f"Low battery: {metrics.battery_percent:.1f}%"
            )
            recommendations.append("Return to charging station soon")
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED

        # Check network latency
        network_warning_ms = self.config.get('network_latency_warning_ms', 100)
        if metrics.network_latency_ms > network_warning_ms:
            warnings.append(
                f"High network latency: {metrics.network_latency_ms:.1f}ms"
            )
            recommendations.append("Check WiFi connection to Go2")
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED

        return HealthReport(
            timestamp=metrics.timestamp,
            status=status,
            metrics=metrics,
            warnings=warnings,
            recommendations=recommendations
        )

    def update_camera_fps(self, fps: float) -> None:
        """Update camera frame rate.

        Args:
            fps: Current camera FPS
        """
        with self._lock:
            self._camera_fps = fps

    def update_frame_received(self) -> None:
        """Update frame counter (alternative to direct FPS update)."""
        current_time = time.time()
        with self._lock:
            self._frame_count += 1
            time_elapsed = current_time - self._last_frame_time

            # Calculate FPS every second
            if time_elapsed >= 1.0:
                self._camera_fps = self._frame_count / time_elapsed
                self._frame_count = 0
                self._last_frame_time = current_time

    def update_battery_level(self, percent: float) -> None:
        """Update battery level.

        Args:
            percent: Battery percentage (0-100)
        """
        with self._lock:
            self._battery_percent = max(0.0, min(100.0, percent))

    def update_network_latency(self, latency_ms: float) -> None:
        """Update network latency to Go2.

        Args:
            latency_ms: Latency in milliseconds
        """
        with self._lock:
            self._network_latency_ms = latency_ms

    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get current system metrics.

        Returns:
            Current metrics or None if not available
        """
        with self._lock:
            return self._current_metrics

    def get_health_status(self) -> HealthStatus:
        """Get current health status.

        Returns:
            Current health status
        """
        if self._current_metrics is None:
            return HealthStatus.HEALTHY

        report = self._analyze_health(self._current_metrics)
        return report.status

    def get_health_report(self) -> Optional[HealthReport]:
        """Get latest health report.

        Returns:
            Latest health report or None if not available
        """
        metrics = self.get_current_metrics()
        if metrics is None:
            return None

        return self._analyze_health(metrics)

    def shutdown(self) -> None:
        """Shutdown health checker."""
        self.stop()
        self.logger.info("Health checker shutdown complete")
