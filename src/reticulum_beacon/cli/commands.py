"""CLI commands for Reticulum Beacon."""

import os
import subprocess
from pathlib import Path

import RNS
import typer

from .. import __version__
from ..config import generator as cfg
from ..node import BeaconNode

node = BeaconNode.get_instance()


def _is_systemd_installed() -> bool:
    """Check if systemd service unit is installed."""
    service_path = Path("/etc/systemd/system/reticulum-beacon.service")
    return service_path.exists()


def _get_service_unit_path() -> str:
    """Return the local path to the systemd service unit file."""
    pkg_path = Path(__file__).parent.parent.parent.parent / "systemd" / "reticulum-beacon.service"
    if pkg_path.exists():
        return str(pkg_path)
    return str(Path(os.getcwd()) / "systemd" / "reticulum-beacon.service")


def setup(
    force: bool = typer.Option(
        False, "--force", "-f", help="Recreate config and identity if they exist"
    ),
    _no_auto: bool = typer.Option(False, "--no-auto", help="Skip AutoInterface setup"),
) -> None:
    """Initialize Reticulum identity and configuration."""
    typer.echo("🔧 Reticulum Beacon Setup")
    typer.echo("━━━━━━━━━━━━━━━━━━━━━")

    result = node.setup(force=force)

    from ..audit import log_identity, log_system

    log_system(
        "setup",
        {
            "config_created": result.get("config_created"),
            "identity_created": result.get("identity_created"),
        },
    )

    if result["config_created"]:
        typer.echo("  ✅ Reticulum config created")
    else:
        typer.echo("  ✓ Reticulum config already exists (use --force to recreate)")

    if result["identity_created"]:
        typer.echo(f"  ✅ Identity created: {result['identity_hash']}")
        log_identity("create", "default", {"hash": result["identity_hash"]})
    else:
        typer.echo(f"  ✓ Identity loaded: {result['identity_hash']}")

    typer.echo(f"\n  📁 Config dir: {cfg.RNS_CONFIG_DIR}")
    typer.echo(f"  📁 Identity:   {cfg.identity_path()}")


def start(
    foreground: bool = typer.Option(True, "--foreground", "-f", help="Run in foreground"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as daemon (fork to background)"),
    with_propagation: bool = typer.Option(
        False, "--with-propagation", "-p", help="Also start LXMF propagation node"
    ),
) -> None:
    """Start the Reticulum Beacon node."""
    if node.is_running:
        typer.echo("⚠️  Beacon node is already running")
        raise typer.Exit(1)

    if daemon:
        foreground = False
        typer.echo("Daemon mode selected. Use systemd for production daemonization.")

    typer.echo("📡 Starting Reticulum Beacon...")
    try:
        node.start(foreground=False)

        pn = None
        if with_propagation:
            from ..propagation.node import PropagationNode

            pn = PropagationNode.get_instance()
            pn.start(
                identity=node.identity,
                display_name="Reticulum Beacon",
            )
            node._propagation_node = pn

            # Wire up bot delivery if bot registry exists
            from ..bots.loader import BotRegistry

            reg = BotRegistry.get_instance()
            node._bot_registry = reg
            reg.set_propagation_node(pn)
            pn.register_delivery_callback(node._deliver_message_to_bots)
            typer.echo("  ✅ LXMF propagation node enabled")

        if foreground:
            # Block until signal
            import signal as sigmod
            import threading

            stop_event = threading.Event()

            def handler(_signum, _frame):
                typer.echo("\n🛑 Shutting down...")
                node.stop()
                if pn is not None and pn.is_running:
                    pn.stop()
                stop_event.set()

            sigmod.signal(sigmod.SIGINT, handler)
            sigmod.signal(sigmod.SIGTERM, handler)

            try:
                stop_event.wait()
            except KeyboardInterrupt:
                node.stop()
                if pn is not None and pn.is_running:
                    pn.stop()
                typer.echo("👋 Beacon node stopped")
    except KeyboardInterrupt:
        node.stop()
        typer.echo("\n👋 Beacon node stopped")


def stop() -> None:
    """Stop the Reticulum Beacon node."""
    if not node.is_running:
        typer.echo("⚠️  Beacon node is not running")
        raise typer.Exit(1)

    # Also stop propagation if running
    from ..propagation.node import PropagationNode

    pn = PropagationNode.get_instance()
    if pn.is_running:
        typer.echo("🛑 Stopping LXMF propagation node...")
        pn.stop()
        typer.echo("  ✅ Propagation node stopped")

    typer.echo("🛑 Stopping Beacon node...")
    node.request_stop()
    typer.echo("👋 Beacon node stopped")

def status() -> None:
    """Show current node status and statistics."""
    from ..propagation.node import PropagationNode

    s = node.get_status()
    uptime_str = f"{s['uptime_seconds']:.0f}s"

    typer.echo("📊 Reticulum Beacon Status")
    typer.echo("━━━━━━━━━━━━━━━━━━━━━━━")

    if s["running"]:
        typer.echo("  Status:     ✅ Online")
        typer.echo(f"  Uptime:     {uptime_str}")
    else:
        typer.echo("  Status:     ⏸️  Offline")

    if s["identity"]:
        typer.echo(f"  Identity:   {s['identity']}")

    if s.get("transport_enabled") is not None:
        typer.echo(f"  Transport:  {'✅ Enabled' if s['transport_enabled'] else '❌ Disabled'}")

    if s.get("interfaces") is not None:
        typer.echo(f"  Interfaces: {s['interfaces']}")

    # Propagation node status
    pn = PropagationNode.get_instance()
    if pn.is_running:
        pn_status = pn.get_status()
        typer.echo("  Propagation:✅ Online")
        typer.echo(f"    Peers:     {pn_status.get('peers', 0)}")
        typer.echo(f"    Stored:    {pn_status.get('stored_messages', 0)} messages")
        if pn_status.get("delivery_destination"):
            typer.echo(f"    Dest:      {pn_status['delivery_destination']}")

    # API server status
    if s.get("api"):
        api_data = s["api"]
        typer.echo(f"  API:        {'✅ Running' if api_data.get('running') else '⏸️  Stopped'}")
        if api_data.get("running") and api_data.get("url"):
            typer.echo(f"    URL:      {api_data['url']}")
        if api_data.get("tls"):
            typer.echo("    TLS:      ✅ Enabled")

    # Bot status
    if s.get("bots"):
        typer.echo(f"  Bots:       {s['bots'].get('active', 0)}/{s['bots'].get('count', 0)} active")


def config(
    show: bool = typer.Option(False, "--show", help="Display the current config"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
) -> None:
    """View or edit the Reticulum configuration."""
    if not cfg.config_exists():
        typer.echo("⚠️  No config found. Run 'beacon setup' first.")
        raise typer.Exit(1)

    cfg_path = cfg.rns_config_path()

    if show:
        with open(cfg_path, encoding="utf-8") as f:
            typer.echo(f.read())
    elif edit:
        editor = os.environ.get("EDITOR", "nano")
        # Only allow known-safe editor binaries to prevent shell injection
        # via the EDITOR environment variable.
        _safe_editors = {
            "vi",
            "vim",
            "nvim",
            "nano",
            "micro",
            "emacs",
            "code",
            "gedit",
            "kate",
            "mousepad",
        }
        editor_basename = os.path.basename(editor)
        if editor_basename not in _safe_editors:
            typer.echo(f"⚠️  Editor '{editor}' not in safe list. Falling back to nano.")
            editor_basename = "nano"
            editor = "/usr/bin/nano"
        from ..audit import log_config

        log_config("edit", {"path": cfg_path, "editor": editor_basename})
        subprocess.call([editor, cfg_path])
    else:
        typer.echo(f"Config path: {cfg_path}")
        typer.echo("Use --show to display or --edit to edit.")


def install() -> None:
    """Install the systemd service unit for auto-start on boot."""
    if os.geteuid() != 0:
        typer.echo("⚠️  Installing systemd service requires root. Try: sudo beacon install")
        raise typer.Exit(1)

    service_path = _get_service_unit_path()

    if not os.path.exists(service_path):
        typer.echo(f"❌ Service unit not found at {service_path}")
        raise typer.Exit(1)

    target = "/etc/systemd/system/reticulum-beacon.service"
    subprocess.run(["cp", service_path, target], check=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    typer.echo("✅ Systemd service installed: reticulum-beacon.service")
    typer.echo("   Run 'sudo systemctl enable reticulum-beacon' to enable on boot")
    typer.echo("   Run 'sudo systemctl start reticulum-beacon' to start now")


def uninstall() -> None:
    """Remove the systemd service unit."""
    if os.geteuid() != 0:
        typer.echo("⚠️  Uninstalling systemd service requires root. Try: sudo beacon uninstall")
        raise typer.Exit(1)

    target = "/etc/systemd/system/reticulum-beacon.service"
    if os.path.exists(target):
        subprocess.run(["systemctl", "stop", "reticulum-beacon"], check=False)
        subprocess.run(["systemctl", "disable", "reticulum-beacon"], check=False)
        os.unlink(target)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        typer.echo("✅ Systemd service removed")
    else:
        typer.echo("⚠️  Systemd service is not installed")


def version() -> None:
    """Show the version."""
    typer.echo(f"Reticulum Beacon v{__version__}")


# --------------------------------------------------------------------------- #
# Propagation sub-commands
# --------------------------------------------------------------------------- #

propagation_app = typer.Typer(help="Manage the LXMF propagation node")


@propagation_app.command("start")
def propagation_start(
    display_name: str = typer.Option(
        "Reticulum Beacon", "--name", "-n", help="Display name for the delivery identity"
    ),
) -> None:
    """Start the LXMF propagation node for store-and-forward messaging."""
    if not node.is_running:
        typer.echo("⚠️  Beacon node must be running first. Run 'beacon start'")
        raise typer.Exit(1)

    from ..propagation.node import PropagationNode

    pn = PropagationNode.get_instance()
    if pn.is_running:
        typer.echo("⚠️  Propagation node is already running")
        raise typer.Exit(1)

    typer.echo("📨 Starting LXMF propagation node...")
    pn.start(identity=node.identity, display_name=display_name)
    node._propagation_node = pn

    # Wire up bot delivery
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()
    node._bot_registry = reg
    reg.set_propagation_node(pn)
    pn.register_delivery_callback(node._deliver_message_to_bots)

    typer.echo("  ✅ LXMF propagation node enabled")
    typer.echo(f"  📁 Storage: {cfg.BEACON_CONFIG_DIR}/lxmf")


@propagation_app.command("stop")
def propagation_stop() -> None:
    """Stop the LXMF propagation node."""
    from ..propagation.node import PropagationNode

    pn = PropagationNode.get_instance()
    if not pn.is_running:
        typer.echo("⚠️  Propagation node is not running")
        raise typer.Exit(1)

    typer.echo("🛑 Stopping LXMF propagation node...")
    pn.stop()
    typer.echo("✅ LXMF propagation node stopped")


@propagation_app.command("status")
def propagation_status() -> None:
    """Show LXMF propagation node status."""
    from ..propagation.node import PropagationNode

    pn = PropagationNode.get_instance()
    s = pn.get_status()

    typer.echo("📨 LXMF Propagation Node")
    typer.echo("━━━━━━━━━━━━━━━━━━━━━━")

    if s["running"]:
        typer.echo("  Status:    ✅ Online")
        typer.echo(f"  Uptime:    {s['uptime_seconds']:.0f}s")
        typer.echo(f"  Peers:     {s.get('peers', 0)}")
        typer.echo(f"  Stored:    {s.get('stored_messages', 0)} messages")
        if s.get("delivery_destination"):
            typer.echo(f"  Dest:      {s['delivery_destination']}")
        if s.get("propagation_node"):
            typer.echo(f"  Propagation mode: {'✅ On' if s['propagation_node'] else '❌ Off'}")
    else:
        typer.echo("  Status: ⏸️  Offline")


@propagation_app.command("send")
def propagation_send(
    destination: str = typer.Argument(help="Destination identity hash (hex)"),
    message: str = typer.Argument(help="Message content"),
) -> None:
    """Send an LXMF message via the propagation node."""
    from ..propagation.node import PropagationNode

    pn = PropagationNode.get_instance()
    if not pn.is_running:
        typer.echo("⚠️  Propagation node is not running")
        raise typer.Exit(1)

    # Parse hex destination hash
    try:
        dest_hash = bytes.fromhex(destination)
    except ValueError:
        typer.echo(f"❌ Invalid hex destination: {destination}")
        raise typer.Exit(1) from None

    typer.echo("📤 Sending message...")
    try:
        msg_id = pn.send_message(dest_hash, message)
        if msg_id:
            typer.echo(f"  ✅ Message sent (ID: {msg_id.hex()[:16]}...)")
        else:
            typer.echo("  ❌ Failed to send message")
    except Exception as e:
        typer.echo(f"  ❌ Error: {e}")
        raise typer.Exit(1) from None


# --------------------------------------------------------------------------- #
# Identity sub-commands
# --------------------------------------------------------------------------- #

identity_app = typer.Typer(help="Manage Reticulum identities")


@identity_app.command("list")
def identity_list() -> None:
    """List all saved identities."""
    from ..identity import manager as id_mgr

    identities = id_mgr.list_identities()

    if not identities:
        typer.echo("No saved identities found.")
        typer.echo(f"  📁 {id_mgr.IDENTITIES_DIR}")
        return

    typer.echo(f"🔑 Identities ({len(identities)})")
    typer.echo("━━━━━━━━━━━━━━━━━━━")
    for entry in identities:
        if "error" in entry:
            typer.echo(f"  ⚠️  {entry['name']} — error: {entry['error']}")
        else:
            typer.echo(f"  {entry['name']:20s} {entry['hash']}")


@identity_app.command("create")
def identity_create(
    name: str = typer.Argument(help="Name for the new identity"),
) -> None:
    """Create a new Reticulum identity."""
    from ..audit import log_identity
    from ..identity import manager as id_mgr

    try:
        identity = id_mgr.create_identity(name)
        log_identity("create", name, {"hash": RNS.hexrep(identity.hash)})
        typer.echo(f"✅ Identity '{name}' created")
        typer.echo(f"   Hash: {RNS.hexrep(identity.hash)}")
    except FileExistsError:
        typer.echo(f"⚠️  Identity '{name}' already exists")
        raise typer.Exit(1) from None
    except ValueError as e:
        typer.echo(f"❌ {e}")
        raise typer.Exit(1) from e


@identity_app.command("show")
def identity_show(
    name: str = typer.Argument(help="Identity name"),
) -> None:
    """Show identity details."""
    from ..identity import manager as id_mgr

    try:
        identity = id_mgr.load_identity(name)
        path = id_mgr.identity_path(name)
        typer.echo(f"🔑 Identity: {name}")
        typer.echo(f"   Hash:   {RNS.hexrep(identity.hash)}")
        typer.echo(f"   File:   {path}")
        typer.echo(f"   Size:   {os.path.getsize(path)} bytes")

        if hasattr(identity, "get_public_key") and identity.get_public_key():
            typer.echo(f"   Pubkey: {identity.get_public_key().hex()[:32]}...")
    except FileNotFoundError:
        typer.echo(f"⚠️  Identity '{name}' not found")
        raise typer.Exit(1) from None


@identity_app.command("delete")
def identity_delete(
    name: str = typer.Argument(help="Identity name to delete"),
) -> None:
    """Delete a saved identity."""
    from ..audit import log_identity
    from ..identity import manager as id_mgr

    try:
        id_mgr.delete_identity(name)
        log_identity("delete", name)
        typer.echo(f"✅ Identity '{name}' deleted")
    except FileNotFoundError:
        typer.echo(f"⚠️  Identity '{name}' not found")
        raise typer.Exit(1) from None


@identity_app.command("import")
def identity_import(
    file_path: str = typer.Argument(help="Path to identity file"),
    name: str | None = typer.Option(None, "--name", "-n", help="Name for the imported identity"),
) -> None:
    """Import an identity from a file."""
    from ..audit import log_identity
    from ..identity import manager as id_mgr

    try:
        identity = id_mgr.import_identity(file_path, name)
        if name is None:
            name = os.path.splitext(os.path.basename(file_path))[0]
        log_identity("import", name, {"source": os.path.basename(file_path)})
        typer.echo(f"✅ Identity imported as '{name}'")
        typer.echo(f"   Hash: {RNS.hexrep(identity.hash)}")
    except (FileNotFoundError, FileExistsError) as e:
        typer.echo(f"❌ {e}")
        raise typer.Exit(1) from e


@identity_app.command("export")
def identity_export(
    name: str = typer.Argument(help="Identity name to export"),
    dest: str = typer.Argument(help="Destination file path"),
) -> None:
    """Export an identity to a file."""
    from ..audit import log_identity
    from ..identity import manager as id_mgr

    try:
        exported = id_mgr.export_identity(name, dest)
        log_identity("export", name, {"destination": dest})
        typer.echo(f"✅ Identity '{name}' exported to {exported}")
    except FileNotFoundError:
        typer.echo(f"⚠️  Identity '{name}' not found")
        raise typer.Exit(1) from None


# --------------------------------------------------------------------------- #
# API sub-commands
# --------------------------------------------------------------------------- #

api_app = typer.Typer(help="Manage the REST API server")


@api_app.command("start")
def api_start(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8931, "--port", "-p", help="Listen port"),
    tls: bool = typer.Option(
        False, "--tls", "-t", help="Enable HTTPS with auto-generated self-signed cert"
    ),
    cert: str | None = typer.Option(
        None, "--cert", "-c", help="Path to TLS certificate file (PEM)"
    ),
    key: str | None = typer.Option(None, "--key", "-k", help="Path to TLS private key file (PEM)"),
) -> None:
    """Start the REST API + WebSocket server.

    Use --tls to enable HTTPS with an auto-generated self-signed certificate,
    or provide --cert and --key for a CA-signed certificate.
    """
    if not node.is_running:
        typer.echo("⚠️  Beacon node must be running first. Run 'beacon start'")
        raise typer.Exit(1)

    if cert and not key:
        typer.echo("❌ --cert requires --key also be provided")
        raise typer.Exit(1)
    if key and not cert:
        typer.echo("❌ --key requires --cert also be provided")
        raise typer.Exit(1)
    if tls and (cert or key):
        typer.echo("⚠️  --tls is ignored when --cert and --key are provided")

    from ..api.manager import APIServer

    api_srv = APIServer.get_instance()
    if api_srv.is_running:
        typer.echo(f"⚠️  API server already running on {api_srv.url}")
        raise typer.Exit(1)

    typer.echo(f"🌐 Starting API server on {host}:{port}...")
    api_srv.start(host=host, port=port, tls=tls, cert_path=cert, key_path=key)
    node._api_server = api_srv

    scheme = "https" if tls else "http"
    ws_scheme = "wss" if tls else "ws"
    typer.echo(f"  ✅ API server started ({'HTTPS' if scheme == 'https' else 'HTTP'})")
    typer.echo(f"  📡 REST API:  {scheme}://{host}:{port}/api/v1/")
    typer.echo(f"  🔌 WebSocket: {ws_scheme}://{host}:{port}/api/v1/events")
    typer.echo(f"  📊 Metrics:   {scheme}://{host}:{port}/api/v1/metrics")
    if tls and not cert:
        typer.echo("  🔐 Using auto-generated self-signed certificate")


@api_app.command("stop")
def api_stop() -> None:
    """Stop the REST API server."""
    from ..api.manager import APIServer

    api_srv = APIServer.get_instance()
    if not api_srv.is_running:
        typer.echo("⚠️  API server is not running")
        raise typer.Exit(1)

    typer.echo("🛑 Stopping API server...")
    api_srv.stop()
    typer.echo("✅ API server stopped")


@api_app.command("status")
def api_status() -> None:
    """Show API server status."""
    from ..api.manager import APIServer

    api_srv = APIServer.get_instance()

    typer.echo("🌐 API Server")
    typer.echo("━━━━━━━━━━━━")
    if api_srv.is_running:
        typer.echo("  Status: ✅ Running")
        typer.echo(f"  URL:    {api_srv.url}")
        typer.echo("  Endpoints:")
        typer.echo(f"    {api_srv.url}/api/v1/status")
        typer.echo(f"    {api_srv.url}/api/v1/health")
        typer.echo(f"    {api_srv.url}/api/v1/peers")
        typer.echo(f"    {api_srv.url}/api/v1/interfaces")
        typer.echo(f"    {api_srv.url}/api/v1/messages")
        typer.echo(f"    {api_srv.url}/api/v1/metrics")
        host_part = api_srv.url.split("://")[1]
        ws_scheme = "wss" if api_srv.url.startswith("https://") else "ws"
        typer.echo(f"    {ws_scheme}://{host_part}/api/v1/events")
    else:
        typer.echo("  Status: ⏸️  Offline")


# --------------------------------------------------------------------------- #
# Bot sub-commands
# --------------------------------------------------------------------------- #

bot_app = typer.Typer(help="Manage bot plugins")


@bot_app.command("list")
def bot_list() -> None:
    """List available bots and their status."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()

    typer.echo("🤖 Beacon Bots")
    typer.echo("━━━━━━━━━━━━━")

    # Show installed/registered bots
    registered = reg.list_bots()
    if registered:
        typer.echo(f"\nActive ({len(registered)}):")
        for bot in registered:
            status = "✅" if bot.get("enabled") else "⏸️"
            typer.echo(f"  {status} {bot['name']:15s} {bot.get('description', '')}")
    else:
        typer.echo("\nNo bots registered.")

    # Show discoverable bot plugins
    typer.echo("\nAvailable plugins:")
    available = reg.discover_bots()
    if available:
        for bot in available:
            typer.echo(f"  📦 {bot['name']:15s} {bot.get('description', '')}")
            typer.echo(f"      {bot['module']}.{bot['class_name']}")
    else:
        typer.echo("  (none discovered)")


@bot_app.command("enable")
def bot_enable(
    name: str = typer.Argument(help="Bot name to enable"),
) -> None:
    """Enable a registered bot."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()

    if reg.enable_bot(name):
        from ..audit import log_bot

        log_bot("enable", name)
        typer.echo(f"✅ Bot '{name}' enabled")
    else:
        typer.echo(f"⚠️  Bot '{name}' not found")
        raise typer.Exit(1)


@bot_app.command("disable")
def bot_disable(
    name: str = typer.Argument(help="Bot name to disable"),
) -> None:
    """Disable a registered bot."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()

    if reg.disable_bot(name):
        from ..audit import log_bot

        log_bot("disable", name)
        typer.echo(f"⏸️  Bot '{name}' disabled")
    else:
        typer.echo(f"⚠️  Bot '{name}' not found")
        raise typer.Exit(1)


@bot_app.command("load")
def bot_load(
    class_path: str = typer.Argument(
        help="Fully-qualified class name, e.g. reticulum_beacon.bots.echo.EchoBot"
    ),
) -> None:
    """Load a bot plugin by class path and register it."""
    from ..bots.loader import BotRegistry

    reg = BotRegistry.get_instance()

    bot = reg.load_bot(class_path)
    if bot is None:
        typer.echo(f"❌ Could not load bot '{class_path}'")
        raise typer.Exit(1)

    from ..audit import log_bot

    reg.register_bot(bot)
    log_bot("load", bot.name)
    typer.echo(f"✅ Bot '{bot.name}' loaded and registered")

    # Start scheduler if not already running
    reg.start_scheduler()
