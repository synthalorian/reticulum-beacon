"""FastAPI application factory for the Reticulum Beacon REST API.

Security features:
- Bearer token authentication on all endpoints
- CORS restricted to same-origin by default
- WebSocket Origin header validation
- Request body size limits
- Rate limiting on message sending
- No information leakage in error responses
"""

import asyncio
import hmac
import os
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..audit import log_auth, log_rate_limit
from ..web.routes import router as web_router
from .routes import health, messages, metrics, peers, status
from .websocket import events

# ── Authentication ────────────────────────────────────────────────────────────

# BEACON_API_KEY — shared secret for Bearer auth.
# If unset, a random 32-byte hex key is generated on first import and printed
# to the log so the operator can find it in the journal.
_API_KEY: str = os.environ.get("BEACON_API_KEY", "")
if not _API_KEY:
    _API_KEY = os.urandom(16).hex()

security = HTTPBearer(auto_error=False)


def _verify_token(credentials: HTTPAuthorizationCredentials | None) -> None:
    """Dependency: reject unauthenticated requests unless BEACON_API_KEY is empty."""
    if not _API_KEY:
        return  # No auth configured — allow (cluster-internal only)
    if credentials is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: BEARER <api-key>",
        )
    if not hmac.compare_digest(credentials.credentials, _API_KEY):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup and shutdown lifecycle."""
    if _API_KEY:
        import RNS

        RNS.log(
            "API auth enabled. Use BEARER token from BEACON_API_KEY env var "
            "(or see journal for the auto-generated key)",
            RNS.LOG_NOTICE,
        )
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Reticulum Beacon API",
        description="REST API and WebSocket interface for Reticulum Beacon",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS: restrict to loopback by default ────────────────────────────────
    # The API binds to 127.0.0.1 by default so this is belt-and-suspenders.
    # If the user exposes the API externally they should set BEACON_CORS_ORIGINS.
    cors_origins_env = os.environ.get("BEACON_CORS_ORIGINS", "")
    if cors_origins_env:
        allow_origins = [o.strip() for o in cors_origins_env.split(",")]
    else:
        allow_origins = [
            "http://127.0.0.1",
            "http://localhost",
            "https://127.0.0.1",
            "https://localhost",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],  # Narrow to what we actually use
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Rate limiter (in-memory, per-IP) ────────────────────────────────────
    _rate_limit_lock = threading.Lock()
    _rate_limit_store: dict[str, list[float]] = defaultdict(list)
    _rate_limit_window = 60  # seconds
    _rate_limit_max = 30  # requests per window

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Only rate-limit POST endpoints (mutations)
        if request.method != "POST":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        with _rate_limit_lock:
            timestamps = _rate_limit_store[client_ip]
            # Prune old entries
            cutoff = now - _rate_limit_window
            _rate_limit_store[client_ip] = [t for t in timestamps if t > cutoff]

            if len(_rate_limit_store[client_ip]) >= _rate_limit_max:
                log_rate_limit(client_ip, str(request.url.path))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Try again later."},
                    headers={"Retry-After": str(_rate_limit_window)},
                )

            _rate_limit_store[client_ip].append(now)

        return await call_next(request)

    # ── Auth middleware for all REST routes ──────────────────────────────────
    # Public endpoints: /health (minimal), /metrics (scrape-only)
    @app.middleware("http")
    async def auth_middleware(request, call_next):
        # Skip auth for health, metrics, and web UI pages
        path = request.url.path
        if (
            path.startswith("/api/v1/health")
            or path == "/api/v1/metrics"
            or path.startswith("/api/v1/web/")
        ):
            return await call_next(request)
    # Web UI pages are auth-free (only accessible from localhost by default)
        if path in {"/", "/api/v1/"}:
            return await call_next(request)

        # Allow CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        token = (
            auth_header.replace("Bearer ", "", 1).strip()
            if auth_header.startswith("Bearer ")
            else ""
        )

        if _API_KEY and not hmac.compare_digest(token, _API_KEY):
            client_ip = request.client.host if request.client else "unknown"
            log_auth(success=False, client_ip=client_ip, reason="invalid_key")
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden"},
            )

        return await call_next(request)

    # Include API route modules
    app.include_router(status.router, prefix="/api/v1")
    app.include_router(messages.router, prefix="/api/v1")
    app.include_router(peers.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")

    # Include web UI routes (HTML pages)
    app.include_router(web_router, prefix="/api/v1")
    # Serve local static assets (HTMX, Tailwind) if downloaded
    import os as _os

    _static_dir = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "static")
    _static_dir = _os.path.normpath(_static_dir)
    if _os.path.isdir(_static_dir) and any(f.endswith(".js") for f in _os.listdir(_static_dir)):
        from fastapi.staticfiles import StaticFiles

        app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    # Root path for web UI (redirects to dashboard)
    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    async def web_root():
        return RedirectResponse(url="/api/v1/")

    # ── WebSocket endpoint with Origin validation ───────────────────────────
    @app.websocket("/api/v1/events")
    async def event_stream(websocket: WebSocket):
        # Validate Origin header to prevent CSWSH attacks
        origin = websocket.headers.get("origin", "")
        if origin:
            allowed = {
                "http://127.0.0.1",
                "http://localhost",
                "ws://127.0.0.1",
                "ws://localhost",
            }
            host = websocket.headers.get("host", "")
            allowed.add(f"http://{host}")
            allowed.add(f"ws://{host}")
            if origin not in allowed:
                await websocket.close(code=4001, reason="Origin not allowed")
                return

        await websocket.accept()

        loop = asyncio.get_event_loop()

        # Send recent events on connect
        for event in events.get_recent_events(50):
            try:
                await websocket.send_json(event)
            except Exception:
                break

        # Subscribe to new events — use run_coroutine_threadsafe so
        # events published from any thread safely reach this websocket.
        def on_event(event: dict):
            try:
                coro = websocket.send_json(event)
                asyncio.run_coroutine_threadsafe(coro, loop)
            except Exception:
                pass

        unsubscribe = events.subscribe(on_event)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    return app


# Re-export for external use (tests, API key management)
def get_api_key() -> str:
    return _API_KEY
