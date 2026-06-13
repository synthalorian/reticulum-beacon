"""Prometheus metrics endpoint for the Reticulum Beacon API.

Exposes operational metrics for Prometheus scraping. All metric labels
are carefully chosen to avoid leaking sensitive information — no identity
hashes, IP addresses, or internal paths are exposed as labels.

Security:
- Labels use only safe, fixed-cardinality values (interface type, direction)
- No identity hashes, IPs, keys, or user data in metric labels
- Endpoint is public (no auth required) for Prometheus scrapers
- Rate-limited by existing API middleware (GET is safe, no mutations)
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from ...node import BeaconNode
from ...propagation.node import PropagationNode

router = APIRouter(tags=["metrics"])

# ── Core Node Metrics ─────────────────────────────────────────────────────────

_uptime_gauge = Gauge(
    "beacon_uptime_seconds",
    "Node uptime in seconds",
)
_running_gauge = Gauge(
    "beacon_running",
    "Whether the node is running (1=yes, 0=no)",
)
_transport_gauge = Gauge(
    "beacon_transport_enabled",
    "Whether transport mode is enabled (1=yes, 0=no)",
)

# ── Interface Metrics ─────────────────────────────────────────────────────────

_ifaces_active = Gauge(
    "beacon_interfaces_active",
    "Number of active interfaces",
)
_ifaces_online = Gauge(
    "beacon_interfaces_online",
    "Number of interfaces currently online",
)
_bandwidth_bytes = Counter(
    "beacon_bandwidth_bytes_total",
    "Total bytes transferred via interfaces",
    ["direction"],  # "in" or "out"
)

# ── Peer & Propagation Metrics ────────────────────────────────────────────────

_peers_total = Gauge(
    "beacon_peers_total",
    "Number of peered propagation nodes",
)
_messages_stored = Gauge(
    "beacon_messages_stored_total",
    "Number of messages in the propagation store",
)
_messages_received = Counter(
    "beacon_messages_received_total",
    "Total number of LXMF messages received",
)
_messages_sent = Counter(
    "beacon_messages_sent_total",
    "Total number of LXMF messages sent",
)

# ── Network Activity Metrics ──────────────────────────────────────────────────

_announces_received = Counter(
    "beacon_announces_received_total",
    "Total number of announces received from the network",
)

# ── Bot Metrics ───────────────────────────────────────────────────────────────

_bots_active = Gauge(
    "beacon_bots_active",
    "Number of active (enabled) bots",
)
_bots_total = Gauge(
    "beacon_bots_total",
    "Total number of registered bots",
)

# ── API Metrics ───────────────────────────────────────────────────────────────

_api_running = Gauge(
    "beacon_api_running",
    "Whether the API server is running (1=yes, 0=no)",
)
_api_tls_enabled = Gauge(
    "beacon_api_tls_enabled",
    "Whether HTTPS/TLS is enabled for the API (1=yes, 0=no)",
)

# ── Health Metrics ────────────────────────────────────────────────────────────

_health_status = Gauge(
    "beacon_health_status",
    "Overall health status (1=ok, 2=warning, 3=degraded, 0=stopped)",
)
_connectivity_gauge = Gauge(
    "beacon_connectivity",
    "Whether the node has network connectivity (1=yes, 0=no)",
)

# Internal counters for tracking deltas
_last_bandwidth_in = 0
_last_bandwidth_out = 0
_lock = threading.Lock()


def _update_bandwidth() -> None:
    """Update bandwidth counters from interface byte counters.

    Computes the delta since the last scrape to avoid double-counting
    when Prometheus accumulates the total.
    """
    # ruff: noqa: PLW0603
    global _last_bandwidth_in, _last_bandwidth_out

    node = BeaconNode.get_instance()
    total_in = 0
    total_out = 0

    if node.is_running:
        try:
            from RNS import Transport

            if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
                for iface in Transport.interfaces:
                    total_in += getattr(iface, "bytes_in", 0) or 0
                    total_out += getattr(iface, "bytes_out", 0) or 0
        except Exception:
            pass

    # Compute delta since last scrape — Prometheus Counter handles accumulation
    with _lock:
        delta_in = total_in - _last_bandwidth_in
        delta_out = total_out - _last_bandwidth_out
        _last_bandwidth_in = total_in
        _last_bandwidth_out = total_out

        if delta_in > 0:
            _bandwidth_bytes.labels(direction="in").inc(delta_in)
        if delta_out > 0:
            _bandwidth_bytes.labels(direction="out").inc(delta_out)


def _collect_core_metrics(running: bool) -> None:
    """Update core node metrics (uptime, transport, interfaces, connectivity, health)."""
    node = BeaconNode.get_instance()

    if running:
        node_status = node.get_status()
        _transport_gauge.set(1 if node_status.get("transport_enabled") else 0)
        _ifaces_active.set(node_status.get("interfaces", 0))

        online = 0
        try:
            from RNS import Transport

            if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
                online = sum(1 for iface in Transport.interfaces if getattr(iface, "online", False))
        except Exception:
            pass
        _ifaces_online.set(online)
        _connectivity_gauge.set(1 if online > 0 else 0)
        health_status = 1
        if online == 0:
            health_status = 3
        _health_status.set(health_status)
    else:
        _transport_gauge.set(0)
        _ifaces_active.set(0)
        _ifaces_online.set(0)
        _connectivity_gauge.set(0)
        _health_status.set(0)  # stopped


def _collect_propagation_metrics() -> None:
    """Update propagation node metrics (peers, stored messages)."""
    pn = PropagationNode.get_instance()

    if pn.is_running:
        try:
            pn_status = pn.get_status()
            _peers_total.set(pn_status.get("peers", 0))
            _messages_stored.set(pn_status.get("stored_messages", 0))
        except Exception:
            pass
    else:
        _peers_total.set(0)
        _messages_stored.set(0)


def _collect_api_metrics() -> None:
    """Update API server metrics (running, TLS)."""
    try:
        node = BeaconNode.get_instance()
        if node.is_running:
            s = node.get_status()
            api_data = s.get("api", {}) or {}
            _api_running.set(1 if api_data.get("running") else 0)
            _api_tls_enabled.set(1 if api_data.get("tls") else 0)
        else:
            _api_running.set(0)
            _api_tls_enabled.set(0)
    except Exception:
        _api_running.set(0)
        _api_tls_enabled.set(0)


def _collect_bot_metrics() -> None:
    """Update bot metrics (total, active count)."""
    try:
        from ...bots.loader import BotRegistry

        reg = BotRegistry.get_instance()
        bots = reg.list_bots()
        _bots_total.set(len(bots))
        _bots_active.set(sum(1 for b in bots if b.get("enabled")))
    except Exception:
        _bots_total.set(0)
        _bots_active.set(0)


def _collect_metrics() -> None:
    """Update all Prometheus metric values with current node state.

    Called synchronously on each /metrics scrape. No sensitive data
    is used as metric labels.
    """
    node = BeaconNode.get_instance()

    _uptime_gauge.set(node.uptime)
    running = node.is_running
    _running_gauge.set(1 if running else 0)

    _collect_core_metrics(running)
    _collect_propagation_metrics()
    _update_bandwidth()
    _collect_api_metrics()
    _collect_bot_metrics()


@router.get("/metrics")
async def get_metrics():
    """Return Prometheus-formatted metrics.

    This endpoint is intentionally unauthenticated so Prometheus
    scrapers can collect metrics without carrying API tokens.
    No sensitive data is exposed in metric labels or values.
    """
    _collect_metrics()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Convenience functions for internal use ────────────────────────────────────


def record_message_received(count: int = 1) -> None:
    """Increment the messages received counter (called from propagation node)."""
    _messages_received.inc(count)


def record_message_sent(count: int = 1) -> None:
    """Increment the messages sent counter (called from propagation node)."""
    _messages_sent.inc(count)


def record_announce() -> None:
    """Increment the announces received counter."""
    _announces_received.inc()
