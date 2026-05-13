"""Mock dimos message bus for testing.

This module provides mock implementations of the dimos framework
for testing agent communication without requiring the full dimos system.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
import time
import threading


@dataclass
class Message:
    """Message passed between agents."""
    topic: str
    data: Any
    timestamp: float
    sender: str


class MockMessageBus:
    """Mock dimos message bus for testing."""

    def __init__(self):
        """Initialize mock message bus."""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_history: List[Message] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, data: Any, sender: str = "unknown") -> None:
        """Publish a message to a topic.

        Args:
            topic: Topic name
            data: Message data
            sender: Sender identifier
        """
        message = Message(
            topic=topic,
            data=data,
            timestamp=time.time(),
            sender=sender
        )

        with self._lock:
            self.message_history.append(message)

            # Notify subscribers
            if topic in self.subscribers:
                for callback in self.subscribers[topic]:
                    try:
                        callback(message)
                    except Exception as e:
                        print(f"Error in subscriber callback: {e}")

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic.

        Args:
            topic: Topic name
            callback: Callback function to call when message received
        """
        with self._lock:
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            self.subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe from a topic.

        Args:
            topic: Topic name
            callback: Callback function to remove
        """
        with self._lock:
            if topic in self.subscribers:
                if callback in self.subscribers[topic]:
                    self.subscribers[topic].remove(callback)

    def get_messages(self, topic: Optional[str] = None) -> List[Message]:
        """Get message history.

        Args:
            topic: Optional topic filter

        Returns:
            List of messages
        """
        with self._lock:
            if topic is None:
                return self.message_history.copy()
            return [m for m in self.message_history if m.topic == topic]

    def clear_history(self) -> None:
        """Clear message history."""
        with self._lock:
            self.message_history.clear()

    def get_subscriber_count(self, topic: str) -> int:
        """Get number of subscribers for a topic.

        Args:
            topic: Topic name

        Returns:
            Number of subscribers
        """
        with self._lock:
            return len(self.subscribers.get(topic, []))


class MockAgent:
    """Mock dimos agent for testing."""

    def __init__(self, name: str, message_bus: MockMessageBus):
        """Initialize mock agent.

        Args:
            name: Agent name
            message_bus: Message bus instance
        """
        self.name = name
        self.message_bus = message_bus
        self.running = False
        self.received_messages: List[Message] = []

    def start(self) -> None:
        """Start the agent."""
        self.running = True

    def stop(self) -> None:
        """Stop the agent."""
        self.running = False

    def publish(self, topic: str, data: Any) -> None:
        """Publish a message.

        Args:
            topic: Topic name
            data: Message data
        """
        self.message_bus.publish(topic, data, sender=self.name)

    def subscribe(self, topic: str, callback: Optional[Callable] = None) -> None:
        """Subscribe to a topic.

        Args:
            topic: Topic name
            callback: Optional callback (defaults to storing in received_messages)
        """
        if callback is None:
            callback = self._default_callback

        self.message_bus.subscribe(topic, callback)

    def _default_callback(self, message: Message) -> None:
        """Default callback that stores messages.

        Args:
            message: Received message
        """
        self.received_messages.append(message)

    def get_received_messages(self, topic: Optional[str] = None) -> List[Message]:
        """Get received messages.

        Args:
            topic: Optional topic filter

        Returns:
            List of received messages
        """
        if topic is None:
            return self.received_messages.copy()
        return [m for m in self.received_messages if m.topic == topic]

    def clear_received_messages(self) -> None:
        """Clear received messages."""
        self.received_messages.clear()
