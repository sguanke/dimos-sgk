"""Message handler for inter-agent communication in dimos framework.

This module defines message types and handles publish-subscribe communication
between agents in the person following system.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any
from enum import Enum
import time
import threading
import logging
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages exchanged between agents."""
    PERSON_DETECTION = "person_detection"
    ROBOT_POSE = "robot_pose"
    MOTION_COMMAND = "motion_command"
    SAFETY_EVENT = "safety_event"
    HEALTH_STATUS = "health_status"
    HEARTBEAT = "heartbeat"


@dataclass
class PersonDetectionMessage:
    """Message containing detected person information."""
    target_id: int
    x: float  # meters in robot frame
    y: float  # meters in robot frame
    distance: float  # meters from robot
    angle: float  # radians relative to robot heading
    confidence: float  # detection confidence (0.0 to 1.0)
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


@dataclass
class RobotPoseMessage:
    """Message containing robot pose estimate."""
    x: float  # meters in world frame
    y: float  # meters in world frame
    theta: float  # radians
    covariance: List[float]  # flattened 3x3 covariance matrix
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


@dataclass
class MotionCommandMessage:
    """Message containing motion command for robot."""
    linear_x: float  # m/s
    angular_z: float  # rad/s
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    validated: bool = False  # Set to True after safety validation


@dataclass
class SafetyEventMessage:
    """Message containing safety event information."""
    level: str  # "normal", "warning", "critical", "emergency"
    event_type: str
    description: str
    emergency_stop_active: bool = False
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


@dataclass
class HealthStatusMessage:
    """Message containing system health status."""
    cpu_usage: float  # percent
    memory_usage: float  # percent
    camera_fps: float
    battery_level: float  # percent
    network_latency: float  # milliseconds
    warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


@dataclass
class HeartbeatMessage:
    """Heartbeat message from agents."""
    agent_name: str
    status: str  # "running", "idle", "error"
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


class MessageHandler:
    """Handles publish-subscribe messaging between agents.

    This class implements a simple message bus for inter-agent communication
    using a publish-subscribe pattern with topic-based routing.
    """

    def __init__(self):
        """Initialize message handler."""
        self._subscribers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._message_queues: Dict[MessageType, Queue] = {
            msg_type: Queue(maxsize=100) for msg_type in MessageType
        }
        self._sequence_numbers: Dict[MessageType, int] = {
            msg_type: 0 for msg_type in MessageType
        }
        self._lock = threading.Lock()
        self._running = False
        self._dispatch_thread: Optional[threading.Thread] = None

        # Statistics
        self._published_count: Dict[MessageType, int] = {
            msg_type: 0 for msg_type in MessageType
        }
        self._delivered_count: Dict[MessageType, int] = {
            msg_type: 0 for msg_type in MessageType
        }

        logger.info("MessageHandler initialized")

    def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[Any], None]
    ) -> None:
        """Subscribe to a message type.

        Args:
            message_type: Type of message to subscribe to
            callback: Function to call when message is received
        """
        with self._lock:
            if callback not in self._subscribers[message_type]:
                self._subscribers[message_type].append(callback)
                logger.info(
                    f"Subscribed to {message_type.value}: "
                    f"{callback.__name__}"
                )

    def unsubscribe(
        self,
        message_type: MessageType,
        callback: Callable[[Any], None]
    ) -> None:
        """Unsubscribe from a message type.

        Args:
            message_type: Type of message to unsubscribe from
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self._subscribers[message_type]:
                self._subscribers[message_type].remove(callback)
                logger.info(
                    f"Unsubscribed from {message_type.value}: "
                    f"{callback.__name__}"
                )

    def publish(self, message_type: MessageType, message: Any) -> None:
        """Publish a message to all subscribers.

        Args:
            message_type: Type of message being published
            message: Message data (should be a dataclass instance)
        """
        with self._lock:
            # Assign sequence number
            message.sequence = self._sequence_numbers[message_type]
            self._sequence_numbers[message_type] += 1

            # Add to queue
            try:
                self._message_queues[message_type].put_nowait(message)
                self._published_count[message_type] += 1
            except Exception as e:
                logger.warning(
                    f"Failed to queue message {message_type.value}: {e}"
                )

    def _dispatch_messages(self) -> None:
        """Dispatch messages from queues to subscribers (runs in thread)."""
        while self._running:
            for message_type in MessageType:
                try:
                    # Non-blocking get with timeout
                    message = self._message_queues[message_type].get(
                        timeout=0.01
                    )

                    # Deliver to all subscribers
                    with self._lock:
                        subscribers = self._subscribers[message_type].copy()

                    for callback in subscribers:
                        try:
                            callback(message)
                            self._delivered_count[message_type] += 1
                        except Exception as e:
                            logger.error(
                                f"Error in subscriber callback "
                                f"{callback.__name__}: {e}"
                            )

                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error dispatching messages: {e}")

    def start(self) -> None:
        """Start message dispatch thread."""
        if self._running:
            logger.warning("MessageHandler already running")
            return

        self._running = True
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_messages,
            daemon=True
        )
        self._dispatch_thread.start()
        logger.info("MessageHandler started")

    def stop(self) -> None:
        """Stop message dispatch thread."""
        if not self._running:
            return

        self._running = False
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=2.0)
        logger.info("MessageHandler stopped")

    def get_statistics(self) -> Dict[str, Any]:
        """Get message handler statistics.

        Returns:
            Dictionary with statistics per message type
        """
        with self._lock:
            stats = {}
            for msg_type in MessageType:
                stats[msg_type.value] = {
                    'published': self._published_count[msg_type],
                    'delivered': self._delivered_count[msg_type],
                    'queue_size': self._message_queues[msg_type].qsize(),
                    'subscribers': len(self._subscribers[msg_type])
                }
            return stats

    def clear_queues(self) -> None:
        """Clear all message queues."""
        with self._lock:
            for queue in self._message_queues.values():
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except Empty:
                        break
            logger.info("All message queues cleared")
