"""Echo Bot — replies to any message with the same content.

Useful for testing LXMF message delivery and propagation.
"""

from .base import BeaconBot


class EchoBot(BeaconBot):
    name = "echo"
    description = "Replies to any message with the same content (testing)"
    version = "0.1.0"

    def on_message(self, message) -> None:
        content = getattr(message, "content", b"")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        self.reply(message, content=content, title="Echo Reply")
