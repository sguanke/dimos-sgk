"""Safety module for Go2 robot person following system.

This module provides critical safety monitoring including:
- Emergency stop and collision detection (safety_monitor)
- Component timeout monitoring (watchdog)
- System health monitoring (health_checker)

CRITICAL: All motion commands must pass through the safety monitor.
NEVER disable or bypass safety checks.
"""

from .safety_monitor import SafetyMonitor, SafetyEvent, SafetyLevel, VelocityCommand
from .watchdog import Watchdog, ComponentStatus, ComponentState
from .health_checker import HealthChecker, HealthStatus, SystemMetrics, HealthReport

__all__ = [
    'SafetyMonitor',
    'SafetyEvent',
    'SafetyLevel',
    'VelocityCommand',
    'Watchdog',
    'ComponentStatus',
    'ComponentState',
    'HealthChecker',
    'HealthStatus',
    'SystemMetrics',
    'HealthReport',
]
