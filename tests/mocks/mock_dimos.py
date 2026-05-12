"""Mock dimos message bus for testing."""

from typing import Any, Callable, Dict, List


class MockMessageBus:
    """Mock dimos message bus."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.published_messages: List[tuple[str, Any]] = []

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def publish(self, topic: str, message: Any) -> None:
        """Publish message to topic."""
        self.published_messages.append((topic, message))
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                callback(message)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe from topic."""
        if topic in self.subscribers:
            self.subscribers[topic].remove(callback)

    def clear(self) -> None:
        """Clear all messages."""
        self.published_messages.clear()

    def get_messages(self, topic: str) -> List[Any]:
        """Get all messages published to topic."""
        return [msg for t, msg in self.published_messages if t == topic]


class MockAgent:
    """Mock dimos agent."""

    def __init__(self, name: str):
        self.name = name
        self.running = False
        self.message_bus = MockMessageBus()

    def start(self) -> None:
        """Start agent."""
        self.running = True

    def stop(self) -> None:
        """Stop agent."""
        self.running = False

    def is_running(self) -> bool:
        """Check if agent is running."""
        return self.running
