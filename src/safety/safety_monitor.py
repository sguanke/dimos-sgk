"""Safety monitor for Go2 robot person following system.

This module implements critical safety checks including emergency stop,
collision detection, and motion command validation. All motion commands
must pass through this monitor before being sent to the robot.

CRITICAL: This module has absolute priority. NEVER disable safety checks.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class SafetyLevel(Enum):
    """Safety event severity levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


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
    event_type: str
    description: str
    command: Optional[VelocityCommand] = None


class SafetyMonitor:
    """Monitor and validate all robot motion commands.

    This class implements critical safety checks:
    - Velocity limit validation
    - Distance-based emergency stop
    - Obstacle collision detection
    - Command validation and veto

    All safety events are logged for post-incident analysis.
    """

    def __init__(self, config_path: str = "config/safety_params.yaml"):
        """Initialize safety monitor.

        Args:
            config_path: Path to safety configuration file
        """
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.safety_log_path = Path("logs/safety_events.log")
        self.safety_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Safety state
        self._emergency_stop_active = False
        self._last_command_time = 0.0
        self._lock = threading.Lock()

        # Statistics
        self._total_commands = 0
        self._vetoed_commands = 0
        self._emergency_stops = 0

        self.logger.info("Safety monitor initialized")
        self._log_safety_event(SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.NORMAL,
            event_type="INIT",
            description="Safety monitor started"
        ))

    def _load_config(self, config_path: str) -> dict:
        """Load safety configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config['safety_monitor']
        except FileNotFoundError:
            # Use default values if config not found
            return {
                'max_linear_velocity': 0.8,
                'max_angular_velocity': 1.0,
                'min_obstacle_distance': 0.3,
                'emergency_stop_distance': 0.5,
                'emergency_stop_timeout': 0.1
            }

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for safety monitor."""
        logger = logging.getLogger("SafetyMonitor")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _log_safety_event(self, event: SafetyEvent) -> None:
        """Log safety event to file.

        Args:
            event: Safety event to log
        """
        with open(self.safety_log_path, 'a') as f:
            log_line = (
                f"{event.timestamp:.6f}|{event.level.value}|"
                f"{event.event_type}|{event.description}"
            )
            if event.command:
                log_line += (
                    f"|linear_x={event.command.linear_x:.3f}|"
                    f"angular_z={event.command.angular_z:.3f}"
                )
            f.write(log_line + "\n")

    def validate_command(
        self,
        command: VelocityCommand,
        target_distance: Optional[float] = None,
        min_obstacle_distance: Optional[float] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate motion command against safety constraints.

        Args:
            command: Velocity command to validate
            target_distance: Distance to target person (meters)
            min_obstacle_distance: Distance to nearest obstacle (meters)

        Returns:
            Tuple of (is_valid, reason). If invalid, reason explains why.
        """
        with self._lock:
            self._total_commands += 1

            # Check if emergency stop is active
            if self._emergency_stop_active:
                self._vetoed_commands += 1
                return False, "Emergency stop active"

            # Validate velocity limits
            if abs(command.linear_x) > self.config['max_linear_velocity']:
                self._vetoed_commands += 1
                self._log_safety_event(SafetyEvent(
                    timestamp=time.time(),
                    level=SafetyLevel.WARNING,
                    event_type="VELOCITY_LIMIT",
                    description=f"Linear velocity {command.linear_x:.3f} exceeds limit",
                    command=command
                ))
                return False, f"Linear velocity exceeds limit: {command.linear_x:.3f}"

            if abs(command.angular_z) > self.config['max_angular_velocity']:
                self._vetoed_commands += 1
                self._log_safety_event(SafetyEvent(
                    timestamp=time.time(),
                    level=SafetyLevel.WARNING,
                    event_type="VELOCITY_LIMIT",
                    description=f"Angular velocity {command.angular_z:.3f} exceeds limit",
                    command=command
                ))
                return False, f"Angular velocity exceeds limit: {command.angular_z:.3f}"

            # Check target distance for emergency stop
            if target_distance is not None:
                if target_distance < self.config['emergency_stop_distance']:
                    self._trigger_emergency_stop(
                        f"Target too close: {target_distance:.3f}m",
                        command
                    )
                    return False, f"Emergency stop: target distance {target_distance:.3f}m"

            # Check obstacle distance
            if min_obstacle_distance is not None:
                if min_obstacle_distance < self.config['min_obstacle_distance']:
                    self._vetoed_commands += 1
                    self._log_safety_event(SafetyEvent(
                        timestamp=time.time(),
                        level=SafetyLevel.CRITICAL,
                        event_type="OBSTACLE_TOO_CLOSE",
                        description=f"Obstacle at {min_obstacle_distance:.3f}m",
                        command=command
                    ))
                    return False, f"Obstacle too close: {min_obstacle_distance:.3f}m"

            # Command is valid
            self._last_command_time = time.time()
            return True, None

    def _trigger_emergency_stop(
        self,
        reason: str,
        command: Optional[VelocityCommand] = None
    ) -> None:
        """Trigger emergency stop.

        Args:
            reason: Reason for emergency stop
            command: Command that triggered the stop (if any)
        """
        self._emergency_stop_active = True
        self._emergency_stops += 1

        self.logger.critical(f"EMERGENCY STOP: {reason}")
        self._log_safety_event(SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.EMERGENCY,
            event_type="EMERGENCY_STOP",
            description=reason,
            command=command
        ))

    def trigger_emergency_stop(self, reason: str) -> None:
        """Public method to trigger emergency stop.

        Args:
            reason: Reason for emergency stop
        """
        with self._lock:
            self._trigger_emergency_stop(reason)

    def reset_emergency_stop(self) -> bool:
        """Reset emergency stop state.

        Returns:
            True if reset successful, False otherwise
        """
        with self._lock:
            if self._emergency_stop_active:
                self._emergency_stop_active = False
                self.logger.info("Emergency stop reset")
                self._log_safety_event(SafetyEvent(
                    timestamp=time.time(),
                    level=SafetyLevel.NORMAL,
                    event_type="EMERGENCY_RESET",
                    description="Emergency stop manually reset"
                ))
                return True
            return False

    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is active.

        Returns:
            True if emergency stop is active
        """
        with self._lock:
            return self._emergency_stop_active

    def get_statistics(self) -> dict:
        """Get safety monitor statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                'total_commands': self._total_commands,
                'vetoed_commands': self._vetoed_commands,
                'emergency_stops': self._emergency_stops,
                'veto_rate': (
                    self._vetoed_commands / self._total_commands
                    if self._total_commands > 0 else 0.0
                )
            }

    def shutdown(self) -> None:
        """Shutdown safety monitor."""
        self.logger.info("Safety monitor shutting down")
        self._log_safety_event(SafetyEvent(
            timestamp=time.time(),
            level=SafetyLevel.NORMAL,
            event_type="SHUTDOWN",
            description=f"Safety monitor stopped. Stats: {self.get_statistics()}"
        ))
