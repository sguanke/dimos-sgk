"""Safety monitor for Go2 robot person following system.

This module implements critical safety checks including emergency stop,
collision detection, and motion command validation. All motion commands
must pass through this monitor before being sent to the robot.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Optional

import yaml


class SafetyLevel(Enum):
    """Safety level indicators."""
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class VelocityCommand:
    """Robot velocity command."""
    linear_x: float  # m/s
    angular_z: float  # rad/s
    timestamp: float


@dataclass
class SafetyEvent:
    """Safety event record."""
    timestamp: float
    level: SafetyLevel
    reason: str
    command: Optional[VelocityCommand] = None


class SafetyMonitor:
    """Monitor and validate all robot motion commands for safety.

    This is a CRITICAL safety component. All motion commands from the
    navigation agent must pass through this monitor. Commands that
    violate safety constraints will be vetoed.
    """

    def __init__(self, config_path: str = "config/safety_params.yaml"):
        """Initialize safety monitor.

        Args:
            config_path: Path to safety configuration file
        """
        self.logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._emergency_stop_active = False
        self._last_command_time = 0.0

        # Load configuration
        self._load_config(config_path)

        # Setup safety event logging
        self._setup_safety_logging()

        self.logger.info("SafetyMonitor initialized")

    def _load_config(self, config_path: str) -> None:
        """Load safety parameters from config file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            monitor_config = config['safety_monitor']
            self.max_linear_velocity = monitor_config['max_linear_velocity']
            self.max_angular_velocity = monitor_config['max_angular_velocity']
            self.min_obstacle_distance = monitor_config['min_obstacle_distance']
            self.emergency_stop_distance = monitor_config['emergency_stop_distance']
            self.emergency_stop_timeout = monitor_config['emergency_stop_timeout']

            self.logger.info(f"Loaded safety config: max_vel={self.max_linear_velocity}, "
                           f"emergency_dist={self.emergency_stop_distance}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}, using defaults")
            # Fail-safe defaults
            self.max_linear_velocity = 0.8
            self.max_angular_velocity = 1.0
            self.min_obstacle_distance = 0.3
            self.emergency_stop_distance = 0.5
            self.emergency_stop_timeout = 0.1

    def _setup_safety_logging(self) -> None:
        """Setup dedicated safety event logging to file."""
        log_dir = Path("logs/safety")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"safety_events_{time.strftime('%Y%m%d_%H%M%S')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        file_handler.setFormatter(formatter)

        self.safety_logger = logging.getLogger('safety_events')
        self.safety_logger.addHandler(file_handler)
        self.safety_logger.setLevel(logging.INFO)

    def validate_command(
        self,
        command: VelocityCommand,
        distance_to_target: Optional[float] = None,
        distance_to_obstacle: Optional[float] = None
    ) -> tuple[bool, Optional[VelocityCommand], str]:
        """Validate motion command against safety constraints.

        This is the main safety check function. ALL motion commands must
        pass through this function before being sent to the robot.

        Args:
            command: Velocity command to validate
            distance_to_target: Distance to target person (meters)
            distance_to_obstacle: Distance to nearest obstacle (meters)

        Returns:
            Tuple of (is_safe, modified_command, reason)
            - is_safe: True if command is safe to execute
            - modified_command: Modified command if adjustments needed, None if vetoed
            - reason: Explanation of decision
        """
        with self._lock:
            current_time = time.time()

            # Check if emergency stop is active
            if self._emergency_stop_active:
                self._log_safety_event(
                    SafetyLevel.EMERGENCY_STOP,
                    "Command rejected: emergency stop active",
                    command
                )
                return False, None, "Emergency stop active"

            # Check velocity limits
            if abs(command.linear_x) > self.max_linear_velocity:
                self._log_safety_event(
                    SafetyLevel.CRITICAL,
                    f"Linear velocity {command.linear_x} exceeds limit {self.max_linear_velocity}",
                    command
                )
                return False, None, "Linear velocity exceeds safety limit"

            if abs(command.angular_z) > self.max_angular_velocity:
                self._log_safety_event(
                    SafetyLevel.CRITICAL,
                    f"Angular velocity {command.angular_z} exceeds limit {self.max_angular_velocity}",
                    command
                )
                return False, None, "Angular velocity exceeds safety limit"

            # Check distance to target (emergency stop condition)
            if distance_to_target is not None:
                if distance_to_target < self.emergency_stop_distance:
                    self._trigger_emergency_stop(
                        f"Target too close: {distance_to_target:.2f}m < {self.emergency_stop_distance}m"
                    )
                    return False, None, "Emergency stop: target too close"

            # Check distance to obstacles
            if distance_to_obstacle is not None:
                if distance_to_obstacle < self.min_obstacle_distance:
                    self._log_safety_event(
                        SafetyLevel.CRITICAL,
                        f"Obstacle too close: {distance_to_obstacle:.2f}m",
                        command
                    )
                    return False, None, "Obstacle too close"

            # Command is safe
            self._last_command_time = current_time
            return True, command, "Command validated"

    def _trigger_emergency_stop(self, reason: str) -> None:
        """Trigger emergency stop.

        This must execute within 100ms as per safety requirements.
        """
        start_time = time.time()

        self._emergency_stop_active = True

        self._log_safety_event(
            SafetyLevel.EMERGENCY_STOP,
            f"EMERGENCY STOP TRIGGERED: {reason}",
            None
        )

        self.logger.critical(f"EMERGENCY STOP: {reason}")

        # Verify execution time
        execution_time = time.time() - start_time
        if execution_time > self.emergency_stop_timeout:
            self.logger.error(
                f"Emergency stop took {execution_time*1000:.1f}ms "
                f"(limit: {self.emergency_stop_timeout*1000:.1f}ms)"
            )

    def reset_emergency_stop(self) -> bool:
        """Reset emergency stop after manual verification.

        Returns:
            True if reset successful
        """
        with self._lock:
            if self._emergency_stop_active:
                self._emergency_stop_active = False
                self._log_safety_event(
                    SafetyLevel.WARNING,
                    "Emergency stop reset by operator",
                    None
                )
                self.logger.warning("Emergency stop reset")
                return True
            return False

    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is currently active."""
        with self._lock:
            return self._emergency_stop_active

    def _log_safety_event(
        self,
        level: SafetyLevel,
        reason: str,
        command: Optional[VelocityCommand]
    ) -> None:
        """Log safety event to dedicated safety log file."""
        event = SafetyEvent(
            timestamp=time.time(),
            level=level,
            reason=reason,
            command=command
        )

        log_msg = f"[{level.value.upper()}] {reason}"
        if command:
            log_msg += f" | Command: linear={command.linear_x:.3f}, angular={command.angular_z:.3f}"

        self.safety_logger.info(log_msg)

        # Also log to main logger based on severity
        if level == SafetyLevel.EMERGENCY_STOP:
            self.logger.critical(log_msg)
        elif level == SafetyLevel.CRITICAL:
            self.logger.error(log_msg)
        elif level == SafetyLevel.WARNING:
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)

    def get_status(self) -> dict:
        """Get current safety monitor status.

        Returns:
            Dictionary with status information
        """
        with self._lock:
            return {
                'emergency_stop_active': self._emergency_stop_active,
                'last_command_time': self._last_command_time,
                'max_linear_velocity': self.max_linear_velocity,
                'max_angular_velocity': self.max_angular_velocity,
                'emergency_stop_distance': self.emergency_stop_distance
            }
