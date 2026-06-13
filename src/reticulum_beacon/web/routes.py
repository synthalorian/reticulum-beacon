"""Web UI route handlers for the Reticulum Beacon management interface.

Serves server-rendered HTML pages with HTMX for dynamic updates.
All routes use Jinja2 templates and return HTML fragments or full pages.

Security:
- CSRF protection via custom header check (HX-Request for HTMX mutations)
- Input validation and length limits on all form submissions
- No sensitive data leakage (identity hashes truncated in UI)
- Rate limiting via existing API middleware
- Auth is enforced by the middleware in api/app.py
"""

from __future__ import annotations

import os
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..audit import log_bot, log_message
from ..node import BeaconNode
from ..static import get_local_urls

# Templates are resolved relative to this file's directory
_templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates"),
)

router = APIRouter()

node = BeaconNode.get_instance()

# Detect local static assets at startup
_LOCAL_ASSETS = get_local_urls()

# Make local_assets available to all templates without passing to every route
_templates.env.globals["local_assets"] = _LOCAL_ASSETS if _LOCAL_ASSETS else {}


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_status() -> dict:
    """Get sanitized status without exposing full internal state."""
    try:
        return node.get_status()
    except Exception:
        return {"running": False, "uptime_seconds": 0, "identity": None}


def _status_badge(running: bool) -> str:
    return "badge-online" if running else "badge-offline"


def _status_text(running: bool) -> str:
    return "Online" if running else "Offline"


def _truncate_hash(h: str | None, length: int = 16) -> str:
    """Truncate a hex hash for display (avoids leaking full identity hash to UI)."""
    if not h:
        return "—"
    return h[:length] + "..." if len(h) > length else h


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    """Full dashboard page."""
    return _templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"request": request, "active_page": "dashboard"},
    )


@router.get("/web/dashboard-data", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_data(request: Request):
    """Dashboard stats — called via HTMX every 10s."""
    s = _get_status()

    uptime_str = f"{s.get('uptime_seconds', 0):.0f}s"
    if s.get("uptime_seconds", 0) > 3600:
        uptime_str = f"{s['uptime_seconds'] / 3600:.1f}h"
    elif s.get("uptime_seconds", 0) > 60:
        uptime_str = f"{s['uptime_seconds'] / 60:.0f}m"

    running = s.get("running", False)
    identity = s.get("identity")
    transport = s.get("transport_enabled", False)
    interfaces = s.get("interfaces", 0)

    # Propagation stats
    prop = s.get("propagation", {})
    peers = prop.get("peers", 0) if prop else 0
    stored = prop.get("stored_messages", 0) if prop else 0

    # API status
    api = s.get("api", {})
    api_url = api.get("url", "") if api else ""
    tls_enabled = api.get("tls", False) if api else False

    # Bots
    bots = s.get("bots", {})
    bot_active = bots.get("active", 0) if bots else 0
    bot_count = bots.get("count", 0) if bots else 0

    return _templates.TemplateResponse(
        request=request,
        name="fragments/dashboard_data.html",
        context={
            "request": request,
            "running": running,
            "status_badge": _status_badge(running),
            "status_text": _status_text(running),
            "uptime": uptime_str,
            "identity": _truncate_hash(identity),
            "transport": transport,
            "interfaces": interfaces,
            "propagation_running": prop.get("running", False) if prop else False,
            "peers": peers,
            "stored_messages": stored,
            "api_running": api.get("running", False) if api else False,
            "api_url": api_url,
            "tls_enabled": tls_enabled,
            "bot_active": bot_active,
            "bot_total": bot_count,
        },
    )


# ── Status bar (sidebar) ────────────────────────────────────────────────────


@router.get("/web/status-bar", response_class=HTMLResponse, include_in_schema=False)
async def status_bar(_request: Request):
    """Compact status for the sidebar — called via HTMX every 15s."""
    s = _get_status()
    running = s.get("running", False)
    dot_class = "bg-green-500" if running else "bg-red-500"
    text = "Online" if running else "Offline"

    # Show identity and transport mode in tooltip
    identity = _truncate_hash(s.get("identity"))
    transport = s.get("transport_enabled", False)
    detail = f"Transport: {'ON' if transport else 'OFF'} | {identity}" if identity else ""

    return HTMLResponse(
        f'<div class="flex items-center gap-2 text-xs text-slate-400">'
        f'<span class="inline-block w-2 h-2 rounded-full {dot_class}" id="status-dot"></span>'
        f'<span id="status-text" title="{detail}">{text}</span>'
        f"</div>"
    )


# ── Messages ─────────────────────────────────────────────────────────────────


@router.get("/messages", response_class=HTMLResponse, include_in_schema=False)
async def messages_page(request: Request):
    """Full messages page."""
    return _templates.TemplateResponse(
        request=request,
        name="messages.html",
        context={"request": request, "active_page": "messages"},
    )


@router.get("/web/messages/inbox", response_class=HTMLResponse, include_in_schema=False)
async def inbox_fragment(_request: Request):
    """Inbox contents — called via HTMX every 15s."""
    if not node._propagation_node:
        return HTMLResponse(
            '<div class="text-center py-8 text-slate-500">Propagation node not running. Start it with <code class="text-sky-400">beacon propagation start</code></div>'
        )

    try:
        pn = node._propagation_node
        # Try to get propagation entries from LXMRouter
        router = getattr(pn, "router", None)
        entries = []
        if router and hasattr(router, "propagation_entries"):
            raw_entries = list(router.propagation_entries)
            # Show last 50
            for entry in raw_entries[-50:]:
                entries.append(
                    {
                        "hash": _truncate_hash(
                            entry.get("hash", "").hex()
                            if isinstance(entry.get("hash"), bytes)
                            else str(entry.get("hash", ""))
                        ),
                        "sender": _truncate_hash(
                            entry.get("sender", "").hex()
                            if isinstance(entry.get("sender"), bytes)
                            else str(entry.get("sender", ""))
                        ),
                        "size": entry.get("size", 0),
                        "age": f"{time.time() - entry.get('timestamp', time.time()):.0f}s ago"
                        if entry.get("timestamp")
                        else "—",
                    }
                )
    except Exception:
        entries = []

    if not entries:
        return HTMLResponse('<div class="text-center py-8 text-slate-500">No messages stored</div>')

    html_parts = ['<div class="space-y-2">']
    for e in entries:
        html_parts.append(
            f'<div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f'<div class="flex justify-between text-xs">'
            f'<span class="font-mono text-sky-400">{e["sender"]}</span>'
            f'<span class="text-slate-500">{e["age"]}</span>'
            f"</div>"
            f'<div class="text-xs text-slate-400 mt-1">hash: {e["hash"]}</div>'
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.post("/web/messages/send", response_class=HTMLResponse, include_in_schema=False)
async def send_message(
    _request: Request,
    destination: str = Form(..., min_length=2, max_length=128),
    content: str = Form(..., min_length=1, max_length=10000),
):
    """Send an LXMF message via the propagation node."""

    # Validate HX-Request header to prevent CSRF via direct POST
    hx_request = _request.headers.get("HX-Request", "")
    if not hx_request:
        return HTMLResponse('<div class="text-red-400 text-sm mt-2">⚠️ Invalid request</div>')

    if not node._propagation_node:
        return HTMLResponse(
            '<div class="text-red-400 text-sm mt-2">⚠️ Propagation node not running</div>'
        )

    try:
        dest_bytes = bytes.fromhex(destination)
    except ValueError:
        return HTMLResponse(
            '<div class="text-red-400 text-sm mt-2">⚠️ Invalid hex destination</div>'
        )

    try:
        msg_id = node._propagation_node.send_message(dest_bytes, content)
        if msg_id:
            log_message("send", destination=_truncate_hash(destination))
            return HTMLResponse(
                f'<div class="text-green-400 text-sm mt-2">✅ Sent (ID: {msg_id.hex()[:12]}...)</div>'
            )
        else:
            return HTMLResponse('<div class="text-red-400 text-sm mt-2">⚠️ Send failed</div>')
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-400 text-sm mt-2">⚠️ Error: {type(e).__name__}</div>'
        )


# ── Bots ──────────────────────────────────────────────────────────────────────


@router.get("/bots", response_class=HTMLResponse, include_in_schema=False)
async def bots_page(request: Request):
    """Full bots management page."""
    return _templates.TemplateResponse(
        request=request,
        name="bots.html",
        context={"request": request, "active_page": "bots"},
    )


@router.get("/web/bots/list", response_class=HTMLResponse, include_in_schema=False)
async def bot_list_fragment(_request: Request):
    """Registered bots list — called via HTMX every 10s."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()
    bots = reg.list_bots()

    if not bots:
        return HTMLResponse('<div class="text-center py-6 text-slate-500">No bots registered</div>')

    html_parts = ['<div class="space-y-2">']
    for bot in bots:
        enabled = bot.get("enabled", False)
        status = "✅" if enabled else "⏸️"
        toggle_action = "disable" if enabled else "enable"
        toggle_label = "Disable" if enabled else "Enable"
        html_parts.append(
            f'<div class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f"<div>"
            f'<div class="flex items-center gap-2"><span>{status}</span><span class="font-medium text-slate-200">{bot["name"]}</span></div>'
            f'<div class="text-xs text-slate-400 mt-0.5">{bot.get("description", "")}</div>'
            f"</div>"
            f'<button class="btn btn-ghost text-xs" '
            f'hx-post="/api/v1/web/bots/{toggle_action}/{bot["name"]}" '
            f'hx-target="closest div" hx-swap="outerHTML">'
            f"{toggle_label}"
            f"</button>"
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.get("/web/bots/available", response_class=HTMLResponse, include_in_schema=False)
async def bot_available_fragment(_request: Request):
    """Available bot plugins."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()
    available = reg.discover_bots()

    if not available:
        return HTMLResponse(
            '<div class="text-center py-4 text-slate-500">No additional plugins discovered</div>'
        )

    html_parts = ['<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">']
    for bot in available:
        html_parts.append(
            f'<div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f'<div class="font-medium text-sm text-slate-200">{bot["name"]}</div>'
            f'<div class="text-xs text-slate-400">{bot.get("description", "")}</div>'
            f'<div class="text-xs font-mono text-slate-500 mt-1">{bot["module"]}.{bot["class_name"]}</div>'
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.post("/web/bots/enable/{name}", response_class=HTMLResponse, include_in_schema=False)
async def bot_enable(request: Request, name: str):
    """Enable a bot."""
    hx_request = request.headers.get("HX-Request", "")
    if not hx_request:
        return HTMLResponse('<span class="text-red-400 text-xs">Invalid request</span>')

    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()
    if reg.enable_bot(name):
        log_bot("enable", name)
        return HTMLResponse(
            f'<div class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f'<div><div class="flex items-center gap-2"><span>✅</span><span class="font-medium text-slate-200">{name}</span></div>'
            f'<div class="text-xs text-slate-400">Enabled</div></div>'
            f'<button class="btn btn-ghost text-xs" hx-post="/api/v1/web/bots/disable/{name}" hx-target="closest div" hx-swap="outerHTML">Disable</button>'
            f"</div>"
        )
    return HTMLResponse(f'<span class="text-red-400 text-xs">Bot "{name}" not found</span>')


@router.post("/web/bots/disable/{name}", response_class=HTMLResponse, include_in_schema=False)
async def bot_disable(request: Request, name: str):
    """Disable a bot."""
    hx_request = request.headers.get("HX-Request", "")
    if not hx_request:
        return HTMLResponse('<span class="text-red-400 text-xs">Invalid request</span>')

    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()
    if reg.disable_bot(name):
        log_bot("disable", name)
        return HTMLResponse(
            f'<div class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f'<div><div class="flex items-center gap-2"><span>⏸️</span><span class="font-medium text-slate-200">{name}</span></div>'
            f'<div class="text-xs text-slate-400">Disabled</div></div>'
            f'<button class="btn btn-ghost text-xs" hx-post="/api/v1/web/bots/enable/{name}" hx-target="closest div" hx-swap="outerHTML">Enable</button>'
            f"</div>"
        )
    return HTMLResponse(f'<span class="text-red-400 text-xs">Bot "{name}" not found</span>')


@router.post("/web/bots/load", response_class=HTMLResponse, include_in_schema=False)
async def bot_load(
    request: Request,
    class_path: str = Form(..., min_length=5, max_length=256),
):
    """Load a bot plugin by class path."""
    hx_request = request.headers.get("HX-Request", "")
    if not hx_request:
        return HTMLResponse('<div class="text-red-400 text-sm mt-2">Invalid request</div>')

    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()

    bot = reg.load_bot(class_path)
    if bot is None:
        return HTMLResponse(
            f'<div class="text-red-400 text-sm mt-2">⚠️ Could not load "{class_path}"</div>'
        )

    reg.register_bot(bot)
    log_bot("load", bot.name)
    reg.start_scheduler()

    return HTMLResponse(
        f'<div class="text-green-400 text-sm mt-2">✅ Bot "{bot.name}" loaded</div>'
    )


# ── Interfaces & Peers ───────────────────────────────────────────────────────


@router.get("/interfaces", response_class=HTMLResponse, include_in_schema=False)
async def interfaces_page(request: Request):
    """Full interfaces page."""
    return _templates.TemplateResponse(
        request=request,
        name="interfaces.html",
        context={"request": request, "active_page": "interfaces"},
    )


@router.get("/web/interfaces", response_class=HTMLResponse, include_in_schema=False)
async def interfaces_fragment(_request: Request):
    """Interface list — called via HTMX every 10s."""
    s = _get_status()
    interface_count = s.get("interfaces", 0)

    # Try to get interface details from RNS.Transport
    from RNS import Transport

    interfaces = []
    try:
        if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
            for iface in Transport.interfaces:
                name = getattr(iface, "name", "unknown")
                mode = getattr(iface, "mode", 0)
                mode_str = {1: "Full", 2: "Access Point", 3: "Gateway", 4: "Client"}.get(
                    mode, f"Mode {mode}"
                )
                online = getattr(iface, "online", False)
                iface_type = type(iface).__name__
                interfaces.append(
                    {
                        "name": name,
                        "type": iface_type,
                        "mode": mode_str,
                        "online": online,
                    }
                )
    except Exception:
        pass

    if not interfaces:
        return HTMLResponse(
            f'<div class="text-center py-6 text-slate-500">{interface_count} interface(s) available</div>'
        )

    html_parts = ['<div class="space-y-2">']
    for iface in interfaces:
        dot = "bg-green-500" if iface["online"] else "bg-red-500"
        html_parts.append(
            f'<div class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f'<div class="flex items-center gap-3">'
            f'<span class="inline-block w-2 h-2 rounded-full {dot}"></span>'
            f"<div>"
            f'<div class="font-medium text-sm text-slate-200">{iface["name"]}</div>'
            f'<div class="text-xs text-slate-400">{iface["type"]} · {iface["mode"]}</div>'
            f"</div>"
            f"</div>"
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.get("/web/peers", response_class=HTMLResponse, include_in_schema=False)
async def peers_fragment(_request: Request):
    """Peer list — called via HTMX every 15s."""
    peer_list = []

    if node._propagation_node:
        try:
            pn = node._propagation_node
            pn_status = pn.get_status()
            peer_count = pn_status.get("peers", 0)
            # Add propagation peer count as summary
            if peer_count > 0:
                peer_list.append(
                    {
                        "name": "Propagation peers",
                        "identity": f"{peer_count} connected",
                        "type": "LXMF",
                    }
                )
        except Exception:
            pass

    if not peer_list:
        return HTMLResponse(
            '<div class="text-center py-6 text-slate-500">No peers discovered yet</div>'
        )

    html_parts = ['<div class="space-y-2">']
    for peer in peer_list:
        html_parts.append(
            f'<div class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">'
            f"<div>"
            f'<div class="font-medium text-sm text-slate-200">{peer["name"]}</div>'
            f'<div class="text-xs font-mono text-slate-400">{peer["identity"]}</div>'
            f"</div>"
            f'<span class="badge badge-online text-xs">{peer["type"]}</span>'
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))
