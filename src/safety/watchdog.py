"""Watchdog timer for monitoring critical system components.

This module monitors all critical components (perception, navigation, localization)
and triggers safety actions if any component fails to send heartbeats or data
within expected timeouts.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock, Thread
from typing import Callable, Dict, Optional

import yaml


class ComponentType(Enum):
    """Types of monitored components."""
    PERCEPTION = "perception"
    NAVIGATION = "navigation"
    LOCALIZATION = "localization"


@dataclass
class ComponentStatus:
    """Status of a monitored component."""
    component_type: ComponentType
    last_heartbeat: float
    last_data_update: float
    is_healthy: bool
    timeout_count: int


class Watchdog:
    """Monitor critical components and trigger safety actions on timeout.

    Each critical component must send heartbeats at regular intervals.
    If a component fails to send heartbeat or data within timeout period,
    the watchdog will trigger a safety action (typically stopping the robot).
    """

    def __init__(
        self,
        config_path: str = "config/safety_params.yaml",
        on_timeout_callback: Optional[Callable[[ComponentType, str], None]] = None
    ):
        """Initialize watchdog timer.

        Args:
            config_path: Path to safety configuration file
            on_timeout_callback: Callback function to execute on timeout
                                Signature: callback(component_type, reason)
        """
        self.logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._running = False
        self._monitor_thread: Optional[Thread] = None
        self._on_timeout_callback = on_timeout_callback

        # Component status tracking
        self._components: Dict[ComponentType, ComponentStatus] = {}

        # Load configuration
        self._load_config(config_path)

        # Initialize component tracking
        self._initialize_components()

        self.logger.info("Watchdog initialized")

    def _load_config(self, config_path: str) -> None:
        """Load watchdog parameters from config file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            watchdog_config = config['watchdog']
            self.target_timeout = watchdog_config['target_timeout']
            self.pose_timeout = watchdog_config['pose_timeout']
            self.command_timeout = watchdog_config['command_timeout']
            self.heartbeat_interval = watchdog_config['heartbeat_interval']

            self.logger.info(
                f"Loaded watchdog config: target_timeout={self.target_timeout}s, "
                f"pose_timeout={self.pose_timeout}s, command_timeout={self.command_timeout}s"
            )
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}, using defaults")
            # Fail-safe defaults
            self.target_timeout = 2.0
            self.pose_timeout = 0.5
            self.command_timeout = 1.0
            self.heartbeat_interval = 0.5

    def _initialize_components(self) -> None:
        """Initialize tracking for all critical components."""
        current_time = time.time()
        for component_type in ComponentType:
            self._components[component_type] = ComponentStatus(
                component_type=component_type,
                last_heartbeat=current_time,
                last_data_update=current_time,
                is_healthy=True,
                timeout_count=0
            )

    def start(self) -> None:
        """Start watchdog monitoring thread."""
        with self._lock:
            if self._running:
                self.logger.warning("Watchdog already running")
                return

            self._running = True
            self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            self.logger.info("Watchdog monitoring started")

    def stop(self) -> None:
        """Stop watchdog monitoring thread."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self.logger.info("Watchdog monitoring stopped")

    def heartbeat(self, component_type: ComponentType) -> None:
        """Receive heartbeat from a component.

        Components must call this method at least once per heartbeat_interval
        to indicate they are alive and functioning.

        Args:
            component_type: Type of component sending heartbeat
        """
        with self._lock:
            if component_type in self._components:
                status = self._components[component_type]
                status.last_heartbeat = time.time()
                status.is_healthy = True
                status.timeout_count = 0

    def update_target_detected(self) -> None:
        """Update timestamp when valid target is detected by perception."""
        with self._lock:
            if ComponentType.PERCEPTION in self._components:
                self._components[ComponentType.PERCEPTION].last_data_update = time.time()

    def update_pose_received(self) -> None:
        """Update timestamp when pose update is received from localization."""
        with self._lock:
            if ComponentType.LOCALIZATION in self._components:
                self._components[ComponentType.LOCALIZATION].last_data_update = time.time()

    def update_command_sent(self) -> None:
        """Update timestamp when motion command is sent by navigation."""
        with self._lock:
            if ComponentType.NAVIGATION in self._components:
                self._components[ComponentType.NAVIGATION].last_data_update = time.time()

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        while self._running:
            try:
                self._check_timeouts()
                time.sleep(0.1)  # Check every 100ms
            except Exception as e:
                self.logger.error(f"Error in watchdog monitor loop: {e}")

    def _check_timeouts(self) -> None:
        """Check all components for timeouts."""
        current_time = time.time()

        with self._lock:
            # Check perception: no valid target for > target_timeout
            perception = self._components[ComponentType.PERCEPTION]
            if current_time - perception.last_data_update > self.target_timeout:
                if perception.is_healthy:
                    perception.is_healthy = False
                    perception.timeout_count += 1
                    reason = f"No valid target detected for {self.target_timeout}s"
                    self.logger.error(f"TIMEOUT: {reason}")
                    self._trigger_timeout_action(ComponentType.PERCEPTION, reason)

            # Check localization: no pose update for > pose_timeout
            localization = self._components[ComponentType.LOCALIZATION]
            if current_time - localization.last_data_update > self.pose_timeout:
                if localization.is_healthy:
                    localization.is_healthy = False
                    localization.timeout_count += 1
                    reason = f"No pose update for {self.pose_timeout}s"
                    self.logger.error(f"TIMEOUT: {reason}")
                    self._trigger_timeout_action(ComponentType.LOCALIZATION, reason)

            # Check navigation: no motion command for > command_timeout
            navigation = self._components[ComponentType.NAVIGATION]
            if current_time - navigation.last_data_update > self.command_timeout:
                if navigation.is_healthy:
                    navigation.is_healthy = False
                    navigation.timeout_count += 1
                    reason = f"No motion command for {self.command_timeout}s"
                    self.logger.error(f"TIMEOUT: {reason}")
                    self._trigger_timeout_action(ComponentType.NAVIGATION, reason)

            # Check heartbeats for all components
            for component_type, status in self._components.items():
                heartbeat_age = current_time - status.last_heartbeat
                if heartbeat_age > self.heartbeat_interval * 2:
                    if status.is_healthy:
                        status.is_healthy = False
                        status.timeout_count += 1
                        reason = f"No heartbeat for {heartbeat_age:.2f}s"
                        self.logger.error(f"TIMEOUT: {component_type.value} - {reason}")
                        self._trigger_timeout_action(component_type, reason)

    def _trigger_timeout_action(self, component_type: ComponentType, reason: str) -> None:
        """Trigger safety action when timeout occurs.

        Args:
            component_type: Component that timed out
            reason: Description of timeout
        """
        self.logger.critical(f"Watchdog timeout: {component_type.value} - {reason}")

        if self._on_timeout_callback:
            try:
                self._on_timeout_callback(component_type, reason)
            except Exception as e:
                self.logger.error(f"Error in timeout callback: {e}")

    def get_status(self) -> Dict[str, dict]:
        """Get current status of all monitored components.

        Returns:
            Dictionary mapping component names to their status
        """
        with self._lock:
            current_time = time.time()
            status = {}
            for component_type, component_status in self._components.items():
                status[component_type.value] = {
                    'is_healthy': component_status.is_healthy,
                    'last_heartbeat_age': current_time - component_status.last_heartbeat,
                    'last_data_age': current_time - component_status.last_data_update,
                    'timeout_count': component_status.timeout_count
                }
            return status

    def is_all_healthy(self) -> bool:
        """Check if all components are healthy.

        Returns:
            True if all components are healthy
        """
        with self._lock:
            return all(status.is_healthy for status in self._components.values())

    def reset_component(self, component_type: ComponentType) -> None:
        """Reset timeout status for a component.

        Args:
            component_type: Component to reset
        """
        with self._lock:
            if component_type in self._components:
                current_time = time.time()
                status = self._components[component_type]
                status.last_heartbeat = current_time
                status.last_data_update = current_time
                status.is_healthy = True
                self.logger.info(f"Reset watchdog status for {component_type.value}")
