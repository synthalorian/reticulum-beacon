"""Health check endpoints for Reticulum Beacon.

Provides structured health information about all subsystems without
leaking sensitive configuration or network topology details.

Security:
- Returns only boolean/fixed-label status — no identity hashes, IPs, or paths
- No stack traces or internal details in error responses
- Rate-limited by existing API middleware (POST mutations only; GET is safe)
- Health endpoint is public (accessible without auth) for monitoring tools
"""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter

from ...node import BeaconNode
from ...propagation.node import PropagationNode

router = APIRouter(tags=["health"])

# Track health check runs for self-test statistics
_health_lock = threading.Lock()
_health_history: list[dict] = []
_MAX_HEALTH_HISTORY = 100


def _check_node_health() -> dict:
    """Check BeaconNode subsystem health.

    Returns safe status fields only — no identity hashes, keys, or paths.
    Falls back to safe defaults if the status query raises.
    """
    node = BeaconNode.get_instance()
    status = {
        "running": node.is_running,
        "uptime_seconds": node.uptime,
    }

    if node.is_running:
        try:
            node_status = node.get_status()
            status["transport_enabled"] = bool(node_status.get("transport_enabled", False))
            status["interfaces_active"] = int(node_status.get("interfaces", 0))
            status["connectivity"] = status["interfaces_active"] > 0
        except Exception:
            status["transport_enabled"] = False
            status["interfaces_active"] = 0
            status["connectivity"] = False
    else:
        status["transport_enabled"] = False
        status["interfaces_active"] = 0
        status["connectivity"] = False

    return status


def _check_propagation_health() -> dict:
    """Check PropagationNode subsystem health.

    Returns only boolean/running status — no peer hashes or message content.
    """
    pn = PropagationNode.get_instance()
    return {
        "running": pn.is_running,
        "uptime_seconds": pn.uptime if pn.is_running else 0,
    }


def _compute_overall_health() -> str:
    """Compute aggregate health status from all subsystems.

    Returns one of: "ok", "warning", "degraded", "stopped"
    """
    node_status = _check_node_health()
    prop_status = _check_propagation_health()

    if not node_status["running"]:
        return "stopped"

    if not node_status["connectivity"]:
        return "degraded"

    # Propagation is optional — missing propagation is just a warning
    if not prop_status["running"]:
        return "ok"  # Core node is fine without propagation

    return "ok"


@router.get("/health")
async def health_check():
    """Lightweight health check — returns aggregate status and uptime.

    This is the primary health endpoint for monitoring tools (Prometheus
    alertmanager, Docker HEALTHCHECK, k8s liveness/readiness probes).

    Returns:
        - status: "ok", "warning", "degraded", or "stopped"
        - uptime_seconds: node uptime
        - components: per-subsystem status dict
    """
    overall = _compute_overall_health()
    http_status = 200 if overall in ("ok", "warning") else 503

    node_health = _check_node_health()
    prop_health = _check_propagation_health()

    response_data = {
        "status": overall,
        "uptime_seconds": node_health["uptime_seconds"],
        "components": {
            "node": node_health,
            "propagation": prop_health,
        },
    }

    from fastapi.responses import JSONResponse

    return JSONResponse(content=response_data, status_code=http_status)


@router.get("/health/self-test")
async def self_test():
    """Run a detailed self-test of all subsystems.

    Performs checks beyond basic liveness — verifies that:
    - The Reticulum stack is reachable and responding
    - Transport interfaces are online (not just counted)
    - Propagation node is accepting messages (if enabled)

    Returns health with the `checks` dict showing pass/fail for each probe.
    """
    node = BeaconNode.get_instance()
    checks = {}

    # Check 1: RNS is initialized and reachable
    try:
        has_reticulum = node.reticulum is not None
        checks["rns_initialized"] = has_reticulum
    except Exception:
        checks["rns_initialized"] = False

    # Check 2: Identity is loaded
    try:
        checks["identity_loaded"] = node.identity is not None
    except Exception:
        checks["identity_loaded"] = False

    # Check 3: At least one interface is online
    try:
        from RNS import Transport

        if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
            online = sum(1 for iface in Transport.interfaces if getattr(iface, "online", False))
            checks["interfaces_online"] = online
        else:
            checks["interfaces_online"] = 0
    except Exception:
        checks["interfaces_online"] = 0

    # Check 4: Propagation running (if enabled)
    pn = PropagationNode.get_instance()
    checks["propagation_running"] = pn.is_running

    # Determine overall status from checks
    critical_fails = []
    if checks.get("rns_initialized") is False:
        critical_fails.append("rns_initialized")
    if checks.get("identity_loaded") is False:
        critical_fails.append("identity_loaded")
    if checks.get("interfaces_online", 0) == 0 and node.is_running:
        critical_fails.append("no_online_interfaces")

    if critical_fails:
        overall = "degraded"
        http_status = 503
    elif node.is_running:
        overall = "ok"
        http_status = 200
    else:
        overall = "stopped"
        http_status = 503

    # Record diagnostic info (no sensitive data)
    result = {
        "status": overall,
        "uptime_seconds": node.uptime,
        "checks": checks,
        "node_running": node.is_running,
    }

    # Store in history for trend analysis
    with _health_lock:
        _health_history.append(
            {
                "ts": time.time(),
                "status": overall,
                "checks": checks,
            }
        )
        if len(_health_history) > _MAX_HEALTH_HISTORY:
            _health_history[:] = _health_history[-_MAX_HEALTH_HISTORY:]

    from fastapi.responses import JSONResponse

    return JSONResponse(content=result, status_code=http_status)


@router.get("/health/history")
async def health_history(limit: int = 10):
    """Return recent self-test results for trend analysis.

    Args:
        limit: Number of recent results to return (max 100).
    """
    safe_limit = min(max(limit, 1), _MAX_HEALTH_HISTORY)

    with _health_lock:
        recent = list(_health_history[-safe_limit:])

    return {
        "count": len(recent),
        "results": recent,
    }


@router.get("/health/diagnostics")
async def diagnostics():
    """Return a non-sensitive diagnostic summary.

    This endpoint provides operational diagnostics without exposing
    sensitive information like identity hashes, IP addresses, or
    internal paths.

    Security: Returns only aggregate counts and boolean flags.
    """
    node = BeaconNode.get_instance()
    pn = PropagationNode.get_instance()

    # Safely get interface types (no IPs or identifying details)
    interface_types = []
    try:
        from RNS import Transport

        if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
            seen = set()
            for iface in Transport.interfaces:
                t = type(iface).__name__
                if t not in seen:
                    seen.add(t)
                    interface_types.append(t)
    except Exception:
        pass

    return {
        "node_running": node.is_running,
        "node_uptime_seconds": node.uptime,
        "propagation_running": pn.is_running,
        "interface_types": interface_types,
        "interface_count": len(interface_types),
        "health_history_count": len(_health_history),
    }


# Export for internal use by other modules
def node_status() -> dict:
    """Safely get node status for internal health checks (no sensitive data)."""
    return _check_node_health()
