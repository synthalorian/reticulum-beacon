"""Bot plugin discovery, loading, and lifecycle management.

Scans the bots package for BeaconBot subclasses and provides
a registry for enabling/disabling bots.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..propagation.node import PropagationNode
    from .base import BeaconBot


class BotRegistry:
    """Registry for discovering, loading, and managing bot plugins."""

    _instance: BotRegistry | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._bots: dict[str, BeaconBot] = {}
        self._propagation_node: PropagationNode | None = None
        self._schedule_thread: threading.Thread | None = None
        self._schedule_stop = threading.Event()

    @classmethod
    def get_instance(cls) -> BotRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_propagation_node(self, pn: PropagationNode | None) -> None:
        """Set the propagation node for bots to use for replies."""
        self._propagation_node = pn
        for bot in self._bots.values():
            bot.propagation_node = pn

    def discover_bots(self) -> list[dict]:
        """Scan for available bot plugins.

        Returns a list of bot metadata dicts (name, description, version).
        """
        available = []
        import reticulum_beacon.bots as bots_pkg

        bot_dir = os.path.dirname(bots_pkg.__file__)
        for _importer, modname, _ispkg in pkgutil.iter_modules([bot_dir]):
            if modname in ("base", "loader", "__init__"):
                continue
            try:
                module = importlib.import_module(f"reticulum_beacon.bots.{modname}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BeaconBot)
                        and attr is not BeaconBot
                    ):
                        available.append(
                            {
                                "name": getattr(attr, "name", modname),
                                "description": getattr(attr, "description", ""),
                                "version": getattr(attr, "version", "0.1.0"),
                                "class_name": attr_name,
                                "module": modname,
                            }
                        )
            except Exception as e:
                import RNS

                RNS.log(f"Could not load bot module '{modname}': {e}", RNS.LOG_WARNING)

        return available

    def load_bot(self, bot_class_path: str) -> BeaconBot | None:
        """Load a specific bot by its fully qualified class name.

        Args:
            bot_class_path: e.g. "reticulum_beacon.bots.echo.EchoBot"
        """
        try:
            module_path, class_name = bot_class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            bot_class = getattr(module, class_name)
            if (
                isinstance(bot_class, type)
                and issubclass(bot_class, BeaconBot)
                and bot_class is not BeaconBot
            ):
                bot = bot_class(propagation_node=self._propagation_node)
                return bot
        except Exception as e:
            import RNS

            RNS.log(f"Could not load bot '{bot_class_path}': {e}", RNS.LOG_WARNING)
        return None

    def register_bot(self, bot: BeaconBot) -> None:
        """Register a bot instance."""
        self._bots[bot.name] = bot

    def unregister_bot(self, name: str) -> None:
        """Remove a bot from the registry."""
        self._bots.pop(name, None)

    def get_bot(self, name: str) -> BeaconBot | None:
        return self._bots.get(name)

    def list_bots(self) -> list[dict]:
        return [
            {
                "name": bot.name,
                "description": bot.description,
                "enabled": bot.enabled,
                "version": bot.version,
            }
            for bot in self._bots.values()
        ]

    def enable_bot(self, name: str) -> bool:
        bot = self._bots.get(name)
        if bot:
            bot.enabled = True
            return True
        return False

    def disable_bot(self, name: str) -> bool:
        bot = self._bots.get(name)
        if bot:
            bot.enabled = False
            return True
        return False

    def deliver_message(self, message) -> None:
        """Deliver an incoming LXMF message to all enabled bots."""
        for bot in self._bots.values():
            if bot.enabled:
                try:
                    bot.on_message(message)
                except Exception as e:
                    import RNS

                    RNS.log(f"Bot '{bot.name}' error on_message: {e}", RNS.LOG_ERROR)

    def deliver_announce(self, destination_hash: bytes, identity, app_data: bytes | None) -> None:
        """Deliver an announce to all enabled bots."""
        for bot in self._bots.values():
            if bot.enabled:
                try:
                    bot.on_announce(destination_hash, identity, app_data)
                except Exception as e:
                    import RNS

                    RNS.log(f"Bot '{bot.name}' error on_announce: {e}", RNS.LOG_ERROR)

    def start_scheduler(self) -> None:
        """Start the background scheduler for periodic bot tasks."""
        if self._schedule_thread and self._schedule_thread.is_alive():
            return

        self._schedule_stop.clear()
        self._schedule_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="bot-scheduler",
        )
        self._schedule_thread.start()

    def stop_scheduler(self) -> None:
        self._schedule_stop.set()
        if self._schedule_thread and self._schedule_thread.is_alive():
            self._schedule_thread.join(timeout=5)

    def _scheduler_loop(self) -> None:
        """Tick every 30 seconds, running scheduled() on bots that are due."""
        while not self._schedule_stop.is_set():
            now = time.time()
            for bot in self._bots.values():
                if (
                    bot.enabled
                    and bot.schedule_interval > 0
                    and now - bot._last_scheduled >= bot.schedule_interval
                ):
                    try:
                        bot.scheduled()
                        bot._last_scheduled = now
                    except Exception as e:
                        import RNS

                        RNS.log(f"Bot '{bot.name}' error scheduled: {e}", RNS.LOG_ERROR)

            self._schedule_stop.wait(timeout=30)


# For convenience, import BeaconBot here so subclasses can reference it
from .base import BeaconBot  # noqa: E402
