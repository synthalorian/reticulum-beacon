"""Transport node management for Reticulum Beacon."""

import contextlib
import signal
import threading
import time

import RNS

from .config import generator as cfg

# How often to announce the beacon node on the network (seconds)
ANNOUNCE_INTERVAL = 600  # 10 minutes


class BeaconNode:
    """Manages a Reticulum transport node instance.

    Handles RNS initialization, identity, interfaces, announce loop,
    and graceful shutdown. Can optionally manage LXMF propagation,
    HTTP API server, and bot registry.
    """

    _instance: "BeaconNode | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self.reticulum: RNS.Reticulum | None = None
        self.identity: RNS.Identity | None = None
        self._running = False
        self._start_time: float | None = None
        self._stop_event = threading.Event()
        self._announce_thread: threading.Thread | None = None
        self._announce_stop = threading.Event()
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_stop = threading.Event()
        self._beacon_destination: RNS.Destination | None = None
        self._propagation_node = None  # Set externally by cli/commands
        self._api_server = None  # Set externally by cli/commands
        self._bot_registry = None  # Set externally by cli/commands

    @classmethod
    def get_instance(cls) -> "BeaconNode":
        """Get or create the singleton BeaconNode instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def uptime(self) -> float:
        """Seconds since the node started."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @property
    def is_running(self) -> bool:
        return self._running

    def setup(self, force: bool = False) -> dict:
        """Run initial setup: create config + identity if missing.

        Returns a summary dict.
        """
        cfg.ensure_dirs()
        result = {"config_created": False, "identity_created": False}

        if not cfg.config_exists() or force:
            cfg.write_config()
            result["config_created"] = True

        if not cfg.identity_exists() or force:
            self.identity = cfg.create_identity()
            result["identity_created"] = True
            result["identity_hash"] = RNS.hexrep(self.identity.hash)
        else:
            self.identity = cfg.load_identity()
            result["identity_hash"] = RNS.hexrep(self.identity.hash)

        return result

    def start(self, foreground: bool = True) -> None:
        """Initialize Reticulum and start the node.

        Begins periodic network announces so other nodes can discover
        this beacon automatically.
        """
        if self._running:
            RNS.log("Beacon node is already running", RNS.LOG_WARNING)
            return

        # Ensure setup is done
        if not cfg.config_exists() or not cfg.identity_exists():
            self.setup()

        # Load identity before initializing RNS
        self.identity = cfg.load_identity()

        RNS.loglevel = RNS.LOG_NOTICE

        from .audit import log_system

        log_system("start", {"identity": RNS.hexrep(self.identity.hash)})

        RNS.log(
            f"Starting Reticulum Beacon node with identity {RNS.hexrep(self.identity.hash)}",
            RNS.LOG_NOTICE,
        )

        self.reticulum = RNS.Reticulum(
            configdir=cfg.RNS_CONFIG_DIR,
            loglevel=RNS.LOG_NOTICE,
        )

        # Create a beacon destination and announce it periodically
        self._beacon_destination = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "beacon",
            "node",
        )

        self._running = True
        self._start_time = time.time()

        # Start periodic announce thread
        self._announce_stop.clear()
        self._announce_thread = threading.Thread(
            target=self._announce_loop,
            daemon=True,
            name="beacon-announce",
        )
        self._announce_thread.start()

        RNS.log("Beacon node is online — announcing on the network", RNS.LOG_NOTICE)

        if foreground:
            self._wait_for_stop()
        else:
            # In background mode, keep a non-daemon heartbeat thread alive
            # so the process doesn't exit when the main thread returns.
            if self._keepalive_thread is not None and self._keepalive_thread.is_alive():
                return
            self._keepalive_stop = threading.Event()
            self._keepalive_thread = threading.Thread(
                target=self._keepalive_loop,
                daemon=False,
                name="beacon-keepalive",
            )
            self._keepalive_thread.start()

    def _keepalive_loop(self) -> None:
        """Keep the process alive in background mode."""
        while not self._keepalive_stop.is_set() and self._running:
            self._keepalive_stop.wait(timeout=1.0)

    def request_stop(self) -> None:
        """Signal the keepalive loop to exit (for background mode)."""
        if hasattr(self, '_keepalive_stop'):
            self._keepalive_stop.set()
        self.stop()

    def stop(self) -> None:
        """Gracefully shut down all subsystems."""
        if not self._running:
            return

        # Signal keepalive thread to exit first
        if hasattr(self, '_keepalive_stop'):
            self._keepalive_stop.set()
        if hasattr(self, '_keepalive_thread') and self._keepalive_thread and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=2)

        from .audit import log_system

        log_system("stop", {"uptime": round(self.uptime, 1)})

        RNS.log("Shutting down Beacon node...", RNS.LOG_NOTICE)

        # Stop API server first (incoming HTTP requests)
        if self._api_server is not None:
            try:
                self._api_server.stop()
            except Exception as e:
                RNS.log(f"Error stopping API server: {e}", RNS.LOG_ERROR)

        # Stop bot scheduler
        if self._bot_registry is not None:
            try:
                self._bot_registry.stop_scheduler()
            except Exception as e:
                RNS.log(f"Error stopping bot scheduler: {e}", RNS.LOG_ERROR)

        # Stop propagation node
        if self._propagation_node is not None:
            try:
                self._propagation_node.stop()
            except Exception as e:
                RNS.log(f"Error stopping propagation node: {e}", RNS.LOG_ERROR)

        # Stop announce loop
        self._announce_stop.set()
        if self._announce_thread and self._announce_thread.is_alive():
            self._announce_thread.join(timeout=5)

        self._running = False
        self._stop_event.set()

        # Give RNS a moment to clean up
        time.sleep(0.5)

    def _announce_loop(self) -> None:
        """Periodically announce the beacon node on the network.

        Announces immediately on start, then repeats at intervals.
        """
        consecutive_errors = 0
        while not self._announce_stop.is_set():
            if self._beacon_destination and self._running:
                try:
                    self._beacon_destination.announce()
                    consecutive_errors = 0
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 5:
                        RNS.log(
                            f"Announce failed: {e}",
                            RNS.LOG_ERROR,
                        )
                    elif consecutive_errors == 6:
                        RNS.log(
                            "Announce errors suppressed after 5 consecutive failures",
                            RNS.LOG_ERROR,
                        )

            # Wait for the next announce interval, or stop signal
            self._announce_stop.wait(timeout=ANNOUNCE_INTERVAL)

    def _deliver_message_to_bots(self, message) -> None:
        """Deliver an incoming LXMF message to all enabled bots."""
        if self._bot_registry is not None:
            with contextlib.suppress(Exception):
                self._bot_registry.deliver_message(message)

    def _deliver_announce_to_bots(
        self,
        destination_hash: bytes,
        identity,
        app_data: bytes | None,
    ) -> None:
        """Deliver a network announce to all enabled bots."""
        if self._bot_registry is not None:
            with contextlib.suppress(Exception):
                self._bot_registry.deliver_announce(destination_hash, identity, app_data)

    def _wait_for_stop(self) -> None:
        """Block until stop is requested (handles signals too)."""

        def signal_handler(signum, _frame):
            RNS.log(f"Received signal {signum}, shutting down...", RNS.LOG_NOTICE)
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self._running:
                self._stop_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            self.stop()

    def get_status(self) -> dict:
        """Return a dict with current node status information.

        Includes transport status, interface count, propagation,
        API server, and bot status if available.
        """
        status = {
            "running": self._running,
            "uptime_seconds": self.uptime,
            "identity": None,
        }

        if self.identity:
            status["identity"] = RNS.hexrep(self.identity.hash)

        if self.reticulum and self._running:
            try:
                transport_enabled = self.reticulum.transport_enabled
                if callable(transport_enabled):
                    status["transport_enabled"] = transport_enabled()
                else:
                    status["transport_enabled"] = bool(transport_enabled)

                from RNS import Transport

                if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
                    status["interfaces"] = len(Transport.interfaces)
                else:
                    status["interfaces"] = 0
            except Exception:
                status["transport_enabled"] = False
                status["interfaces"] = 0

        # Include propagation node status if running
        if self._propagation_node is not None:
            try:
                pn_status = self._propagation_node.get_status()
                status["propagation"] = {
                    "running": pn_status.get("running", False),
                    "peers": pn_status.get("peers", 0),
                    "stored_messages": pn_status.get("stored_messages", 0),
                }
            except Exception:
                status["propagation"] = {"running": False}

        # Include API server status
        if self._api_server is not None:
            with contextlib.suppress(Exception):
                status["api"] = {
                    "running": self._api_server.is_running,
                    "url": self._api_server.url,
                    "tls": "https" in self._api_server.url,
                }

        # Include bot status
        if self._bot_registry is not None:
            try:
                bots = self._bot_registry.list_bots()
                status["bots"] = {
                    "count": len(bots),
                    "active": sum(1 for b in bots if b.get("enabled")),
                    "list": bots,
                }
            except Exception:
                pass

        return status
