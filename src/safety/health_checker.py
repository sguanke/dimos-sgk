"""System health monitoring for Go2 robot person following system.

This module monitors system resources (CPU, memory, camera FPS, battery, network)
and triggers warnings or graceful degradation when thresholds are exceeded.
"""

import logging
import psutil
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock, Thread
from typing import Callable, Dict, Optional

import yaml


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
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
    status: HealthStatus
    metrics: SystemMetrics
    warnings: list[str]
    critical_issues: list[str]


class HealthChecker:
    """Monitor system health and trigger warnings or degradation.

    Monitors:
    - CPU usage
    - Memory usage
    - Camera frame rate
    - Battery level
    - Network latency to Go2 robot
    """

    def __init__(
        self,
        config_path: str = "config/safety_params.yaml",
        on_degradation_callback: Optional[Callable[[str], None]] = None
    ):
        """Initialize health checker.

        Args:
            config_path: Path to safety configuration file
            on_degradation_callback: Callback for graceful degradation actions
                                    Signature: callback(reason)
        """
        self.logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._running = False
        self._monitor_thread: Optional[Thread] = None
        self._on_degradation_callback = on_degradation_callback

        # Current metrics
        self._current_metrics: Optional[SystemMetrics] = None
        self._last_frame_count = 0
        self._last_fps_check_time = time.time()

        # Load configuration
        self._load_config(config_path)

        self.logger.info("HealthChecker initialized")

    def _load_config(self, config_path: str) -> None:
        """Load health check parameters from config file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            health_config = config['health']
            self.cpu_warning_threshold = health_config['cpu_warning_threshold']
            self.memory_warning_threshold = health_config['memory_warning_threshold']
            self.fps_warning_threshold = health_config['fps_warning_threshold']
            self.battery_warning_threshold = health_config['battery_warning_threshold']
            self.battery_critical_threshold = health_config['battery_critical_threshold']

            self.logger.info(
                f"Loaded health config: cpu_warn={self.cpu_warning_threshold}%, "
                f"mem_warn={self.memory_warning_threshold}%, "
                f"battery_crit={self.battery_critical_threshold}%"
            )
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}, using defaults")
            # Fail-safe defaults
            self.cpu_warning_threshold = 80
            self.memory_warning_threshold = 90
            self.fps_warning_threshold = 20
            self.battery_warning_threshold = 20
            self.battery_critical_threshold = 10

    def start(self, check_interval: float = 1.0) -> None:
        """Start health monitoring thread.

        Args:
            check_interval: Interval between health checks in seconds
        """
        with self._lock:
            if self._running:
                self.logger.warning("HealthChecker already running")
                return

            self._running = True
            self._check_interval = check_interval
            self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            self.logger.info("Health monitoring started")

    def stop(self) -> None:
        """Stop health monitoring thread."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self.logger.info("Health monitoring stopped")

    def update_camera_frame(self) -> None:
        """Update camera frame count for FPS calculation.

        Should be called each time a new camera frame is processed.
        """
        with self._lock:
            self._last_frame_count += 1

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        while self._running:
            try:
                self._check_health()
                time.sleep(self._check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitor loop: {e}")

    def _check_health(self) -> None:
        """Perform health checks on all monitored resources."""
        # Collect metrics
        metrics = self._collect_metrics()

        # Analyze metrics
        warnings = []
        critical_issues = []

        # Check CPU usage
        if metrics.cpu_percent > self.cpu_warning_threshold:
            msg = f"High CPU usage: {metrics.cpu_percent:.1f}%"
            warnings.append(msg)
            self.logger.warning(msg)

            if metrics.cpu_percent > 95:
                critical_issues.append(msg)
                self._trigger_degradation("High CPU usage, reducing processing load")

        # Check memory usage
        if metrics.memory_percent > self.memory_warning_threshold:
            msg = f"High memory usage: {metrics.memory_percent:.1f}%"
            warnings.append(msg)
            self.logger.warning(msg)

            if metrics.memory_percent > 95:
                critical_issues.append(msg)

        # Check camera FPS
        if metrics.camera_fps < self.fps_warning_threshold:
            msg = f"Low camera FPS: {metrics.camera_fps:.1f}"
            warnings.append(msg)
            self.logger.warning(msg)

            if metrics.camera_fps < 10:
                critical_issues.append(msg)
                self._trigger_degradation("Low camera FPS, reducing speed")

        # Check battery level
        if metrics.battery_percent < self.battery_warning_threshold:
            msg = f"Low battery: {metrics.battery_percent:.1f}%"
            warnings.append(msg)
            self.logger.warning(msg)

            if metrics.battery_percent < self.battery_critical_threshold:
                critical_issues.append(f"Critical battery: {metrics.battery_percent:.1f}%")
                self.logger.critical(msg)
                self._trigger_degradation("Critical battery level, stopping robot")

        # Check network latency
        if metrics.network_latency_ms > 100:
            msg = f"High network latency: {metrics.network_latency_ms:.1f}ms"
            warnings.append(msg)
            self.logger.warning(msg)

            if metrics.network_latency_ms > 500:
                critical_issues.append(msg)

        # Store current metrics
        with self._lock:
            self._current_metrics = metrics

    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics.

        Returns:
            SystemMetrics object with current values
        """
        current_time = time.time()

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Camera FPS
        with self._lock:
            time_delta = current_time - self._last_fps_check_time
            if time_delta > 0:
                camera_fps = self._last_frame_count / time_delta
            else:
                camera_fps = 0.0
            self._last_frame_count = 0
            self._last_fps_check_time = current_time

        # Battery level (mock for now, would read from Go2 SDK)
        battery_percent = self._get_battery_level()

        # Network latency (mock for now, would ping Go2)
        network_latency_ms = self._get_network_latency()

        return SystemMetrics(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            camera_fps=camera_fps,
            battery_percent=battery_percent,
            network_latency_ms=network_latency_ms
        )

    def _get_battery_level(self) -> float:
        """Get battery level from Go2 robot.

        Returns:
            Battery percentage (0-100)
        """
        # TODO: Implement actual battery reading from Go2 SDK
        # For now, return mock value
        try:
            battery = psutil.sensors_battery()
            if battery:
                return battery.percent
        except Exception:
            pass
        return 100.0  # Mock: assume full battery

    def _get_network_latency(self) -> float:
        """Get network latency to Go2 robot.

        Returns:
            Latency in milliseconds
        """
        # TODO: Implement actual network latency measurement to Go2
        # For now, return mock value
        return 10.0  # Mock: assume 10ms latency

    def _trigger_degradation(self, reason: str) -> None:
        """Trigger graceful degradation action.

        Args:
            reason: Reason for degradation
        """
        self.logger.warning(f"Triggering graceful degradation: {reason}")

        if self._on_degradation_callback:
            try:
                self._on_degradation_callback(reason)
            except Exception as e:
                self.logger.error(f"Error in degradation callback: {e}")

    def get_health_report(self) -> HealthReport:
        """Get current health report.

        Returns:
            HealthReport with current status and metrics
        """
        with self._lock:
            if not self._current_metrics:
                # No metrics yet, return default
                return HealthReport(
                    status=HealthStatus.HEALTHY,
                    metrics=SystemMetrics(
                        timestamp=time.time(),
                        cpu_percent=0.0,
                        memory_percent=0.0,
                        camera_fps=0.0,
                        battery_percent=100.0,
                        network_latency_ms=0.0
                    ),
                    warnings=[],
                    critical_issues=[]
                )

            metrics = self._current_metrics
            warnings = []
            critical_issues = []

            # Determine status based on current metrics
            if metrics.cpu_percent > self.cpu_warning_threshold:
                warnings.append(f"High CPU: {metrics.cpu_percent:.1f}%")
            if metrics.memory_percent > self.memory_warning_threshold:
                warnings.append(f"High memory: {metrics.memory_percent:.1f}%")
            if metrics.camera_fps < self.fps_warning_threshold:
                warnings.append(f"Low FPS: {metrics.camera_fps:.1f}")
            if metrics.battery_percent < self.battery_warning_threshold:
                warnings.append(f"Low battery: {metrics.battery_percent:.1f}%")
            if metrics.network_latency_ms > 100:
                warnings.append(f"High latency: {metrics.network_latency_ms:.1f}ms")

            # Critical issues
            if metrics.battery_percent < self.battery_critical_threshold:
                critical_issues.append(f"Critical battery: {metrics.battery_percent:.1f}%")
            if metrics.cpu_percent > 95:
                critical_issues.append(f"Critical CPU: {metrics.cpu_percent:.1f}%")
            if metrics.memory_percent > 95:
                critical_issues.append(f"Critical memory: {metrics.memory_percent:.1f}%")

            # Determine overall status
            if critical_issues:
                status = HealthStatus.CRITICAL
            elif warnings:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY

            return HealthReport(
                status=status,
                metrics=metrics,
                warnings=warnings,
                critical_issues=critical_issues
            )

    def get_metrics(self) -> Optional[SystemMetrics]:
        """Get current system metrics.

        Returns:
            SystemMetrics object or None if no metrics collected yet
        """
        with self._lock:
            return self._current_metrics
