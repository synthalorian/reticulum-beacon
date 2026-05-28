"""API server lifecycle management.

Wraps uvicorn in a background thread so the FastAPI REST API and
WebSocket event stream run alongside the RNS/LXMF node without
blocking the main thread.
"""

from __future__ import annotations

import os
import re
import threading

import RNS
import uvicorn

from .app import create_app

# Only allow alphanumeric hostnames, IPs, and wildcards for cert path validation
_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9\.\-\*]+$")


class APIServer:
    """Manages the uvicorn HTTP/WebSocket server lifecycle."""

    _instance: APIServer | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._server_thread: threading.Thread | None = None
        self._running = False
        self._host = "127.0.0.1"
        self._port = 8931
        self._server: uvicorn.Server | None = None

    @classmethod
    def get_instance(cls) -> APIServer:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def url(self) -> str:
        scheme = "https" if getattr(self, "_tls", False) else "http"
        return f"{scheme}://{self._host}:{self._port}"

    def start(
        self,
        host: str = "127.0.0.1",
        port: int = 8931,
        tls: bool = False,
        cert_path: str | None = None,
        key_path: str | None = None,
    ) -> None:
        """Start the API server in a background thread.

        Args:
            host: Bind address.
            port: Listen port.
            tls: If True and no cert/key provided, auto-generate self-signed certs.
            cert_path: Path to TLS certificate file (PEM).
            key_path: Path to TLS private key file (PEM).
        """
        if self._running:
            RNS.log("API server is already running", RNS.LOG_WARNING)
            return

        # Validate cert paths against basic injection patterns
        if cert_path is not None:
            _validate_cert_path(cert_path)
        if key_path is not None:
            _validate_cert_path(key_path)

        self._host = host
        self._port = port
        self._tls = tls
        self._cert_path = cert_path
        self._key_path = key_path
        self._running = True

        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="api-server",
        )
        self._server_thread.start()
        RNS.log(f"API server starting on {self.url}", RNS.LOG_NOTICE)

    def stop(self) -> None:
        """Signal the API server to shut down gracefully."""
        if not self._running:
            return

        RNS.log("Shutting down API server...", RNS.LOG_NOTICE)
        from ..audit import log_system

        log_system("api.stop", {"url": self.url})

        self._running = False

        # Tell uvicorn to exit — Server.should_exit is checked in the
        # event loop and triggers a clean shutdown.
        if self._server is not None:
            self._server.should_exit = True

    def _resolve_tls(self) -> tuple[str | None, str | None]:
        """Resolve TLS certificate and key paths.

        Returns (cert_path, key_path) or (None, None) if TLS is disabled.
        Auto-generates self-signed certs if tls=True and no paths given.
        """
        if not self._tls and not self._cert_path:
            return None, None

        if self._cert_path and self._key_path:
            return self._cert_path, self._key_path

        # Auto-generate self-signed certs
        try:
            from ..crypto.certs import cert_paths

            return cert_paths()
        except Exception as e:
            RNS.log(f"Could not generate TLS certificate: {e}", RNS.LOG_ERROR)
            return None, None

    def _run_server(self) -> None:
        """Run uvicorn in a sub-thread with a stop-compatible config."""
        try:
            import uvicorn

            app = create_app()

            ssl_certfile, ssl_keyfile = self._resolve_tls()

            config = uvicorn.Config(
                app=app,
                host=self._host,
                port=self._port,
                log_level="info",
                access_log=False,
                # Limit request body size to 1 MB
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
            )
            server = uvicorn.Server(config)
            self._server = server

            if ssl_certfile:
                RNS.log(f"API server using TLS (cert: {ssl_certfile})", RNS.LOG_NOTICE)
            from ..audit import log_system

            log_system("api.start", {"url": self.url, "tls": ssl_certfile is not None})

            # uvicorn.Server.run() will check server.should_exit on
            # each iteration of its event loop, so setting it from
            # another thread triggers a clean shutdown.
            server.run()
        except Exception as e:
            RNS.log(f"API server error: {e}", RNS.LOG_ERROR)
        finally:
            self._server = None
            self._running = False


def _validate_cert_path(path: str) -> None:
    """Validate a certificate or key path for injection attacks.

    Raises ValueError if the path contains shell metacharacters or
    other suspicious patterns.
    """
    if not path or not isinstance(path, str):
        raise ValueError("Certificate path must be a non-empty string")
    # Block path traversal
    resolved = os.path.realpath(path)
    if ".." in path.split(os.sep):
        raise ValueError(f"Path traversal detected in cert path: {path}")
    # Only allow alphanumeric, dots, hyphens, underscores, and separators
    basename = os.path.basename(resolved)
    if not _SAFE_HOST_RE.match(
        basename.replace(".pem", "").replace(".crt", "").replace(".key", "")
    ):
        raise ValueError(f"Suspicious characters in cert path: {path}")
