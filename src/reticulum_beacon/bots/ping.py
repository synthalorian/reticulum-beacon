"""Ping Bot — responds to /ping with network latency stats."""

import time

from .base import BeaconBot


class PingBot(BeaconBot):
    name = "ping"
    description = "Responds to /ping with network latency stats"
    version = "0.1.0"

    def on_message(self, message) -> None:
        content = getattr(message, "content", b"")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        content_stripped = content.strip().lower()

        if content_stripped in {"/ping", "ping"}:
            # Calculate approximate round-trip time based on message timestamps
            msg_time = getattr(message, "timestamp", None)
            if msg_time is None:
                msg_time = getattr(message, "received_at", time.time())

            rtt = time.time() - msg_time if isinstance(msg_time, (int, float)) else 0.0

            import RNS

            response = (
                f"🏓 Pong!\n"
                f"   RTT:      {rtt * 1000:.1f}ms\n"
                f"   RSSI:     {getattr(message, 'rssi', 'N/A')}\n"
                f"   SNR:      {getattr(message, 'snr', 'N/A')}\n"
                f"   Identity: {RNS.hexrep(message.source_hash) if hasattr(message, 'source_hash') else 'N/A'}"
            )
            self.reply(message, content=response, title="Pong Reply")
