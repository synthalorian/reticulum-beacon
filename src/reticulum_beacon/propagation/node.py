"""LXMF propagation node management.

Wraps LXMF.LXMRouter to provide lifecycle management for
store-and-forward message propagation, delivery identity
registration, and inbound message handling.
"""

import threading
import time

import RNS
from LXMF import LXMessage, LXMRouter

from ..config import generator as cfg


class PropagationNode:
    """Manages an LXMF propagation node instance.

    Handles router lifecycle, delivery identity registration,
    and incoming message callbacks.
    """

    _instance: "PropagationNode | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self.router: LXMRouter | None = None
        self.identity: RNS.Identity | None = None
        self.delivery_destination: RNS.Destination | None = None
        self._running = False
        self._start_time: float | None = None
        self._delivery_callback = None

    @classmethod
    def get_instance(cls) -> "PropagationNode":
        """Get or create the singleton PropagationNode instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def uptime(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def register_delivery_callback(self, callback):
        """Register a callback for incoming LXMF messages.

        The callback receives an LXMessage object.
        """
        self._delivery_callback = callback
        if self.router is not None:
            self.router.register_delivery_callback(callback)

    def start(
        self,
        identity: RNS.Identity | None = None,
        display_name: str | None = None,
        enable_propagation: bool = True,
        storagepath: str | None = None,
    ) -> None:
        """Start the LXMF propagation router.

        Args:
            identity: Identity to use. Defaults to the beacon node identity.
            display_name: Human-readable name announced with delivery identity.
            enable_propagation: If True, enables store-and-forward propagation node mode.
            storagepath: Path for LXMF state storage. Defaults to ~/.beacon/lxmf.
        """
        if self._running:
            RNS.log("Propagation node is already running", RNS.LOG_WARNING)
            return

        if identity is None:
            raise RuntimeError(
                "Beacon node identity is required. Run 'beacon setup' first "
                "and pass identity=node.identity."
            )

        self.identity = identity

        if storagepath is None:
            storagepath = cfg.BEACON_CONFIG_DIR

        RNS.log("Initialising LXMF router...", RNS.LOG_NOTICE)

        self.router = LXMRouter(
            identity=identity,
            storagepath=storagepath,
            autopeer=True,
        )

        # Register delivery identity so we can receive messages
        self.delivery_destination = self.router.register_delivery_identity(
            identity,
            display_name=display_name,
        )

        if self._delivery_callback is not None:
            self.router.register_delivery_callback(self._delivery_callback)

        RNS.log(
            f"LXMF delivery destination: {RNS.hexrep(self.delivery_destination.hash)}",
            RNS.LOG_NOTICE,
        )

        if enable_propagation:
            RNS.log("Enabling LXMF propagation node...", RNS.LOG_NOTICE)
            self.router.enable_propagation()
            RNS.log("LXMF propagation node is online", RNS.LOG_NOTICE)

        self._running = True
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop the LXMF router and propagation node."""
        if not self._running or self.router is None:
            return

        RNS.log("Shutting down LXMF router...", RNS.LOG_NOTICE)

        try:
            self.router.disable_propagation()
        except Exception as e:
            RNS.log(f"Error disabling propagation: {e}", RNS.LOG_ERROR)

        try:
            self.router.exit_handler()
        except Exception as e:
            RNS.log(f"Error in LXMF exit handler: {e}", RNS.LOG_ERROR)

        self._running = False
        self.router = None
        self.delivery_destination = None

    def send_message(
        self,
        destination_hash: bytes,
        content: str,
        title: str = "",
        desired_method: int = LXMessage.PROPAGATED,
    ) -> bytes | None:
        """Send an LXMF message.

        Args:
            destination_hash: The 16-byte destination hash to send to.
            content: Message body text.
            title: Optional message title/subject.
            desired_method: LXMessage.PROPAGATED or LXMessage.DIRECT.

        Returns:
            The message ID (hash) if sent successfully, or None on failure.
        """
        if self.router is None or not self._running:
            raise RuntimeError("Propagation node is not running")

        # Look up the destination identity from the network
        dest_identity = RNS.Identity.recall(destination_hash)
        if dest_identity is None:
            RNS.log(
                f"No announced identity known for {RNS.hexrep(destination_hash)}",
                RNS.LOG_WARNING,
            )
            # Try requesting the path
            RNS.Transport.request_path(destination_hash)
            time.sleep(2)
            dest_identity = RNS.Identity.recall(destination_hash)
            if dest_identity is None:
                raise RuntimeError(f"Could not resolve destination {RNS.hexrep(destination_hash)}")

        dest = RNS.Destination(
            dest_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            "lxmf",
            "delivery",
        )

        message = LXMessage(
            destination=dest,
            source=self.identity,
            content=content,
            title=title,
            desired_method=desired_method,
        )

        self.router.handle_outbound(message)
        return message.hash

    def get_status(self) -> dict:
        """Return status information about the propagation node."""
        status = {
            "running": self._running,
            "uptime_seconds": self.uptime,
        }

        if self.router is not None:
            status["propagation_node"] = self.router.propagation_node
            status["peers"] = len(self.router.peers) if hasattr(self.router, "peers") else 0
            status["stored_messages"] = (
                len(self.router.propagation_entries)
                if hasattr(self.router, "propagation_entries")
                else 0
            )

        if self.identity:
            status["identity_hash"] = RNS.hexrep(self.identity.hash)

        if self.delivery_destination:
            status["delivery_destination"] = RNS.hexrep(self.delivery_destination.hash)

        return status
