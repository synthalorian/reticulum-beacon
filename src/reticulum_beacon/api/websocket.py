"""WebSocket event manager for real-time event streaming.

Provides a simple pub/sub mechanism where API workers and the
beacon node can broadcast events to all connected WebSocket clients.
"""

import contextlib
import threading
import time
from collections.abc import Callable


class EventManager:
    """Manages WebSocket event subscriptions and broadcasting."""

    _instance: "EventManager | None" = None
    _singleton_lock = threading.Lock()

    def __init__(self):
        self._subscribers: list[Callable] = []
        self._subscriber_lock = threading.Lock()
        self._event_history: list[dict] = []
        self._max_history = 100

    @classmethod
    def get_instance(cls) -> "EventManager":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def subscribe(self, callback: Callable) -> Callable:
        """Register a subscriber callback.

        The callback receives event dicts. Returns an unsubscribe function.
        """
        with self._subscriber_lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._subscriber_lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, event_type: str, data: dict) -> None:
        """Publish an event to all subscribers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history :]

        with self._subscriber_lock:
            for subscriber in list(self._subscribers):
                with contextlib.suppress(Exception):
                    subscriber(event)

    def get_recent_events(self, limit: int = 50) -> list[dict]:
        """Return recent events for replay on new connections."""
        return self._event_history[-limit:]


# Global singleton
events = EventManager.get_instance()
