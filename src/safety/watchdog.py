"""Watchdog timer for Go2 robot person following system.

This module monitors all critical components and triggers safety stops
if any component fails to send heartbeats or if critical data is missing.

CRITICAL: Watchdog ensures system liveness. If components stop responding,
the robot must stop immediately.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import yaml


class ComponentStatus(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass
class ComponentState:
    """State of a monitored component."""
    name: str
    last_heartbeat: float
    timeout: float
    status: ComponentStatus
    message: str = ""


class Watchdog:
    """Monitor critical components and trigger stops on timeout.

    This class monitors:
    - Perception: target detection heartbeats
    - Navigation: motion command generation
    - Localization: pose updates
    - Safety: health checker heartbeats

    If any component fails to send heartbeats within timeout,
    the watchdog triggers an emergency stop.
    """

    def __init__(
        self,
        config_path: str = "config/safety_params.yaml",
        stop_callback: Optional[Callable[[str], None]] = None
    ):
        """Initialize watchdog timer.

        Args:
            config_path: Path to safety configuration file
            stop_callback: Callback to trigger emergency stop
        """
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.stop_callback = stop_callback

        # Component states
        self._components = {
            'perception': ComponentState(
                name='perception',
                last_heartbeat=time.time(),
                timeout=self.config['target_timeout'],
                status=ComponentStatus.HEALTHY
            ),
            'navigation': ComponentState(
                name='navigation',
                last_heartbeat=time.time(),
                timeout=self.config['command_timeout'],
                status=ComponentStatus.HEALTHY
            ),
            'localization': ComponentState(
                name='localization',
                last_heartbeat=time.time(),
                timeout=self.config['pose_timeout'],
                status=ComponentStatus.HEALTHY
            ),
        }

        # Watchdog state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_triggered = False

        self.logger.info("Watchdog initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load watchdog configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['watchdog']
        except FileNotFoundError:
            # Use default values if config not found
            return {
                'target_timeout': 2.0,
                'pose_timeout': 0.5,
                'command_timeout': 1.0,
                'heartbeat_interval': 0.5
            }

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for watchdog."""
        logger = logging.getLogger("Watchdog")
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
        """Start watchdog monitoring."""
        with self._lock:
            if self._running:
                self.logger.warning("Watchdog already running")
                return

            self._running = True
            self._stop_triggered = False
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Watchdog monitoring started")

    def stop(self) -> None:
        """Stop watchdog monitoring."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

        self.logger.info("Watchdog monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        check_interval = self.config['heartbeat_interval']

        while self._running:
            current_time = time.time()

            with self._lock:
                for component_name, component in self._components.items():
                    time_since_heartbeat = current_time - component.last_heartbeat

                    # Check for timeout
                    if time_since_heartbeat > component.timeout:
                        if component.status != ComponentStatus.TIMEOUT:
                            component.status = ComponentStatus.TIMEOUT
                            component.message = (
                                f"No heartbeat for {time_since_heartbeat:.2f}s"
                            )
                            self.logger.error(
                                f"Component '{component_name}' timeout: "
                                f"{component.message}"
                            )

                            # Trigger emergency stop
                            if not self._stop_triggered:
                                self._trigger_stop(
                                    f"Watchdog timeout: {component_name}"
                                )

                    # Check for degraded performance
                    elif time_since_heartbeat > component.timeout * 0.7:
                        if component.status == ComponentStatus.HEALTHY:
                            component.status = ComponentStatus.DEGRADED
                            component.message = (
                                f"Slow heartbeat: {time_since_heartbeat:.2f}s"
                            )
                            self.logger.warning(
                                f"Component '{component_name}' degraded: "
                                f"{component.message}"
                            )

                    # Component is healthy
                    else:
                        if component.status != ComponentStatus.HEALTHY:
                            component.status = ComponentStatus.HEALTHY
                            component.message = "Recovered"
                            self.logger.info(
                                f"Component '{component_name}' recovered"
                            )

            time.sleep(check_interval)

    def _trigger_stop(self, reason: str) -> None:
        """Trigger emergency stop via callback.

        Args:
            reason: Reason for stop
        """
        self._stop_triggered = True
        self.logger.critical(f"Watchdog triggering stop: {reason}")

        if self.stop_callback:
            try:
                self.stop_callback(reason)
            except Exception as e:
                self.logger.error(f"Stop callback failed: {e}")

    def heartbeat(self, component: str) -> None:
        """Record heartbeat from component.

        Args:
            component: Component name ('perception', 'navigation', 'localization')
        """
        with self._lock:
            if component in self._components:
                self._components[component].last_heartbeat = time.time()
            else:
                self.logger.warning(f"Unknown component: {component}")

    def update_target_detected(self, detected: bool) -> None:
        """Update perception component based on target detection.

        Args:
            detected: True if target person is detected
        """
        if detected:
            self.heartbeat('perception')

    def update_pose_received(self) -> None:
        """Update localization component when pose is received."""
        self.heartbeat('localization')

    def update_command_sent(self) -> None:
        """Update navigation component when command is sent."""
        self.heartbeat('navigation')

    def get_component_status(self, component: str) -> Optional[ComponentState]:
        """Get status of a component.

        Args:
            component: Component name

        Returns:
            Component state or None if not found
        """
        with self._lock:
            return self._components.get(component)

    def get_all_status(self) -> dict[str, ComponentState]:
        """Get status of all components.

        Returns:
            Dictionary mapping component names to states
        """
        with self._lock:
            return self._components.copy()

    def is_all_healthy(self) -> bool:
        """Check if all components are healthy.

        Returns:
            True if all components are healthy
        """
        with self._lock:
            return all(
                comp.status == ComponentStatus.HEALTHY
                for comp in self._components.values()
            )

    def reset(self) -> None:
        """Reset watchdog state (clear stop trigger)."""
        with self._lock:
            self._stop_triggered = False
            current_time = time.time()
            for component in self._components.values():
                component.last_heartbeat = current_time
                component.status = ComponentStatus.HEALTHY
                component.message = ""
            self.logger.info("Watchdog reset")

    def shutdown(self) -> None:
        """Shutdown watchdog."""
        self.stop()
        self.logger.info("Watchdog shutdown complete")
