"""Inter-agent communication message types and message bus.

This module defines all message types used for communication between
agents in the dimos framework, and implements a publish-subscribe
message bus for inter-agent communication.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import numpy as np


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages exchanged between agents."""
    PERSON_DETECTION = "person_detection"
    ROBOT_POSE = "robot_pose"
    MOTION_COMMAND = "motion_command"
    SAFETY_EVENT = "safety_event"
    HEALTH_STATUS = "health_status"


@dataclass
class BaseMessage:
    """Base class for all messages."""
    timestamp: float = field(default_factory=time.time)
    sequence_number: int = 0
    source_agent: str = ""


@dataclass
class PersonDetectionMessage(BaseMessage):
    """Message containing detected target person information.

    Published by: PerceptionAgent
    Subscribed by: NavigationAgent
    """
    target_id: Optional[int] = None
    bbox: Optional[tuple[float, float, float, float]] = None
    distance: Optional[float] = None  # meters
    angle: Optional[float] = None  # degrees
    confidence: Optional[float] = None
    velocity: Optional[tuple[float, float]] = None


@dataclass
class RobotPoseMessage(BaseMessage):
    """Message containing robot pose estimate.

    Published by: LocalizationAgent
    Subscribed by: NavigationAgent
    """
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    covariance: Optional[np.ndarray] = None  # 3x3 covariance matrix
    linear_velocity: float = 0.0  # m/s
    angular_velocity: float = 0.0  # rad/s


@dataclass
class MotionCommandMessage(BaseMessage):
    """Message containing motion command for robot.

    Published by: NavigationAgent
    Subscribed by: SafetyAgent
    """
    linear_x: float = 0.0  # m/s
    angular_z: float = 0.0  # rad/s
    validated: bool = False  # Set to True after safety validation


@dataclass
class SafetyEventMessage(BaseMessage):
    """Message containing safety event notification.

    Published by: SafetyAgent
    Subscribed by: All agents
    """
    level: str = "info"  # "safe", "warning", "critical", "emergency_stop"
    reason: str = ""
    emergency_stop_active: bool = False


@dataclass
class HealthStatusMessage(BaseMessage):
    """Message containing system health status.

    Published by: SafetyAgent
    Subscribed by: All agents
    """
    cpu_usage: float = 0.0  # percent
    memory_usage: float = 0.0  # percent
    camera_fps: float = 0.0
    battery_level: float = 100.0  # percent
    all_components_healthy: bool = True
    component_status: Dict[str, dict] = field(default_factory=dict)


class MessageBus:
    """Publish-subscribe message bus for inter-agent communication.

    Implements a thread-safe message bus that allows agents to publish
    messages and subscribe to message types with callback functions.
    """

    def __init__(self):
        """Initialize message bus."""
        self._subscribers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._lock = Lock()
        self._sequence_counters: Dict[str, int] = {}
        self._message_history: Dict[MessageType, List[BaseMessage]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._max_history = 100  # Keep last 100 messages per type

        logger.info("MessageBus initialized")

    def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[BaseMessage], None]
    ) -> None:
        """Subscribe to a message type.

        Args:
            message_type: Type of message to subscribe to
            callback: Function to call when message is published
                     Signature: callback(message)
        """
        with self._lock:
            self._subscribers[message_type].append(callback)
            logger.debug(
                f"Subscribed to {message_type.value}, "
                f"total subscribers: {len(self._subscribers[message_type])}"
            )

    def unsubscribe(
        self,
        message_type: MessageType,
        callback: Callable[[BaseMessage], None]
    ) -> None:
        """Unsubscribe from a message type.

        Args:
            message_type: Type of message to unsubscribe from
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self._subscribers[message_type]:
                self._subscribers[message_type].remove(callback)
                logger.debug(f"Unsubscribed from {message_type.value}")

    def publish(
        self,
        message_type: MessageType,
        message: BaseMessage
    ) -> None:
        """Publish a message to all subscribers.

        Args:
            message_type: Type of message being published
            message: Message object to publish
        """
        # Set sequence number
        source = message.source_agent
        with self._lock:
            if source not in self._sequence_counters:
                self._sequence_counters[source] = 0
            self._sequence_counters[source] += 1
            message.sequence_number = self._sequence_counters[source]

            # Store in history
            self._message_history[message_type].append(message)
            if len(self._message_history[message_type]) > self._max_history:
                self._message_history[message_type].pop(0)

            # Get subscribers
            subscribers = self._subscribers[message_type].copy()

        # Call subscribers outside lock to avoid deadlock
        for callback in subscribers:
            try:
                callback(message)
            except Exception as e:
                logger.error(
                    f"Error in subscriber callback for {message_type.value}: {e}"
                )

    def get_latest_message(
        self,
        message_type: MessageType
    ) -> Optional[BaseMessage]:
        """Get the most recent message of a given type.

        Args:
            message_type: Type of message to retrieve

        Returns:
            Latest message or None if no messages published
        """
        with self._lock:
            history = self._message_history[message_type]
            if history:
                return history[-1]
            return None

    def get_message_history(
        self,
        message_type: MessageType,
        count: int = 10
    ) -> List[BaseMessage]:
        """Get recent message history for a message type.

        Args:
            message_type: Type of message to retrieve
            count: Number of recent messages to return

        Returns:
            List of recent messages (newest last)
        """
        with self._lock:
            history = self._message_history[message_type]
            return history[-count:] if history else []

    def clear_history(self, message_type: Optional[MessageType] = None) -> None:
        """Clear message history.

        Args:
            message_type: Specific message type to clear, or None for all
        """
        with self._lock:
            if message_type:
                self._message_history[message_type].clear()
            else:
                for msg_type in MessageType:
                    self._message_history[msg_type].clear()
            logger.debug("Message history cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            stats = {
                "subscriber_counts": {
                    msg_type.value: len(subscribers)
                    for msg_type, subscribers in self._subscribers.items()
                },
                "message_counts": {
                    msg_type.value: len(history)
                    for msg_type, history in self._message_history.items()
                },
                "sequence_counters": self._sequence_counters.copy()
            }
        return stats
