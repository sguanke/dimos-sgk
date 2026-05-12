"""Safety module for Go2 robot person following system.

This module provides critical safety monitoring including:
- Emergency stop and collision detection
- Watchdog timer for component monitoring
- System health monitoring
"""

from .safety_monitor import SafetyMonitor, SafetyLevel, VelocityCommand, SafetyEvent
from .watchdog import Watchdog, ComponentType, ComponentStatus
from .health_checker import HealthChecker, HealthStatus, SystemMetrics, HealthReport

__all__ = [
    'SafetyMonitor',
    'SafetyLevel',
    'VelocityCommand',
    'SafetyEvent',
    'Watchdog',
    'ComponentType',
    'ComponentStatus',
    'HealthChecker',
    'HealthStatus',
    'SystemMetrics',
    'HealthReport',
]
