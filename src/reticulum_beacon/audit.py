"""Structured audit logging for Reticulum Beacon.

Logs security-relevant events to a structured JSON log file at
~/.beacon/audit.log with automatic rotation at 10 MB.

Event categories:
- system: node start/stop, API server start/stop
- auth: API authentication successes and failures
- identity: create, delete, import, export
- config: configuration file edits
- message: LXMF message sends (sender hash only, not content)
- bot: bot load, enable, disable
- rate_limit: API rate limit exceeded

Thread-safe and designed to never raise exceptions — audit failures
are silently dropped to avoid disrupting normal operation.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import generator as cfg

AUDIT_LOG_PATH = os.path.join(cfg.BEACON_CONFIG_DIR, "audit.log")
_MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB

_log_lock = threading.Lock()
_rotated = False


def _ensure_audit_log() -> None:
    """Create the audit log directory and rotate if necessary."""
    # ruff: noqa: PLW0603
    global _rotated

    path = Path(AUDIT_LOG_PATH)
    parent = path.parent

    try:
        if not parent.exists():
            parent.mkdir(mode=0o700, parents=True)

        # Rotate once if over max size
        if not _rotated and path.exists() and path.stat().st_size > _MAX_LOG_BYTES:
            old_path = path.with_suffix(".log.old")
            if old_path.exists():
                old_path.unlink(missing_ok=True)
            path.rename(old_path)
            _rotated = True
    except Exception:
        pass  # Never let audit logging failures propagate


def _audit_entry(event_type: str, severity: str, details: dict) -> dict:
    """Build a structured audit log entry dict."""
    return {
        "ts": time.time(),
        "iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S."),
        "event": event_type,
        "sev": severity,
        "details": details,
    }


def log_event(event_type: str, severity: str, details: dict) -> None:
    """Write a structured audit log entry.

    Args:
        event_type: Dot-separated identifier like ``identity.create``.
        severity: One of ``INFO``, ``WARNING``, ``ALERT``.
        details: Dict with event-specific key-value pairs.

    This function is thread-safe and will never raise.
    """
    try:
        _ensure_audit_log()

        entry = _audit_entry(event_type, severity, details)

        with _log_lock, open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass  # Audit must never crash the caller


# ── Convenience helpers ──────────────────────────────────────────────────────


def log_system(event: str, details: dict | None = None) -> None:
    """Log a system-level event (start, stop, etc.)."""
    log_event(f"system.{event}", "INFO", details or {})


def log_auth(success: bool, client_ip: str = "", reason: str = "") -> None:
    """Log an API authentication event."""
    log_event(
        "auth" if success else "auth.failure",
        "INFO" if success else "WARNING",
        {"client_ip": client_ip, "reason": reason},
    )


def log_identity(action: str, name: str, details: dict | None = None) -> None:
    """Log an identity management event."""
    log_event(
        f"identity.{action}",
        "INFO",
        {"name": name, **(details or {})},
    )


def log_config(action: str, details: dict | None = None) -> None:
    """Log a configuration event."""
    log_event(
        f"config.{action}",
        "INFO",
        details or {},
    )


def log_bot(action: str, name: str, details: dict | None = None) -> None:
    """Log a bot lifecycle event."""
    log_event(
        f"bot.{action}",
        "INFO",
        {"name": name, **(details or {})},
    )


def log_rate_limit(client_ip: str, endpoint: str) -> None:
    """Log a rate-limit exceeded event."""
    log_event(
        "rate_limit.exceeded",
        "WARNING",
        {"client_ip": client_ip, "endpoint": endpoint},
    )


def log_message(action: str, sender_hash: str = "", destination: str = "") -> None:
    """Log an LXMF message event (no content)."""
    log_event(
        f"message.{action}",
        "INFO",
        {"sender": sender_hash, "destination": destination},
    )
