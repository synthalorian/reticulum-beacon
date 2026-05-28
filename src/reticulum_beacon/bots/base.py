"""Base class for Reticulum Beacon bot plugins."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..propagation.node import PropagationNode


class BeaconBot:
    """Base class for all beacon bot plugins.

    Subclass this and override the hooks you need:

    - on_message: Called when an LXMF message arrives
    - on_announce: Called when a node announces on the network
    - scheduled: Called periodically (configurable interval)
    """

    # Metadata — override in subclasses
    name: str = "base_bot"
    description: str = "Base bot plugin"
    version: str = "0.1.0"
    schedule_interval: int = 0  # Seconds between scheduled() calls (0 = disabled)

    def __init__(self, propagation_node: PropagationNode | None = None):
        self.propagation_node = propagation_node
        self.enabled = True
        self._last_scheduled: float = 0.0

    def on_message(self, message) -> None:
        """Called when an LXMF message is received.

        Args:
            message: An LXMF.LXMessage object with .content, .source, etc.
        """
        pass

    def on_announce(
        self,
        destination_hash: bytes,
        identity=None,
        app_data: bytes | None = None,
    ) -> None:
        """Called when a node announces on the network."""
        pass

    def scheduled(self) -> None:
        """Called periodically based on schedule_interval."""
        pass

    def reply(self, message, content: str, title: str = "") -> None:
        """Convenience method to reply to an LXMF message.

        Sends a message back to the original sender.
        """
        if self.propagation_node is None:
            return

        source_hash = message.source_hash if hasattr(message, "source_hash") else None
        if source_hash is None:
            return

        with contextlib.suppress(Exception):
            self.propagation_node.send_message(
                destination_hash=source_hash,
                content=content,
                title=title,
            )
