"""Reticulum configuration file generation."""

import os

import RNS

BEACON_CONFIG_DIR = os.path.expanduser("~/.beacon")
RNS_CONFIG_DIR = os.path.join(BEACON_CONFIG_DIR, "reticulum")


# Public testnet nodes for global connectivity
DEFAULT_TESTNET_NODES = [
    ("dismail.de", 4242),
    ("reticulum.chen.lu", 4242),
    ("rns.ath.cx", 4242),
    ("l1.testnet.reticulum.network", 4242),
    ("l2.testnet.reticulum.network", 4242),
    ("l3.testnet.reticulum.network", 4242),
]


def rns_config_path() -> str:
    """Return the path to the Reticulum config file."""
    return os.path.join(RNS_CONFIG_DIR, "config")


def identity_path() -> str:
    """Return the path to the identity file."""
    return os.path.join(BEACON_CONFIG_DIR, "identity")


def ensure_dirs():
    """Create beacon data directories if they don't exist."""
    os.makedirs(RNS_CONFIG_DIR, mode=0o700, exist_ok=True)
    os.makedirs(BEACON_CONFIG_DIR, mode=0o700, exist_ok=True)


def config_exists() -> bool:
    """Check if a Reticulum config already exists."""
    return os.path.exists(rns_config_path())


def identity_exists() -> bool:
    """Check if an identity file exists."""
    return os.path.exists(identity_path())


def create_identity() -> RNS.Identity:
    """Create a new Reticulum identity and save it to disk."""
    ensure_dirs()
    identity = RNS.Identity()
    identity.to_file(identity_path())
    return identity


def load_identity() -> RNS.Identity:
    """Load an existing identity from disk."""
    return RNS.Identity.from_file(identity_path())


def generate_config(
    enable_transport: bool = True,
    testnet_nodes: list[tuple[str, int]] | None = None,
    autointerface: bool = True,
    _append: bool = False,
) -> str:
    """Generate a Reticulum config file as a string.

    Args:
        enable_transport: Whether to enable transport mode.
        testnet_nodes: List of (host, port) tuples for TCP client interfaces.
        autointerface: Whether to enable AutoInterface for local discovery.
        append: If True, append to existing config instead of overwriting.

    Returns:
        The config file contents as a string.
    """
    if testnet_nodes is None:
        testnet_nodes = DEFAULT_TESTNET_NODES

    lines = [
        "[reticulum]",
        f"  enable_transport = {'yes' if enable_transport else 'no'}",
        "  share_instance = no",
        "  panic_on_interface_error = no",
        "",
        "[logging]",
        "  loglevel = 4",  # LOG_INFO
        "",
        "[interfaces]",
    ]

    if autointerface:
        lines.extend(
            [
                "  [[AutoInterface]]",
                "    type = AutoInterface",
                "    enabled = yes",
                "    name = beacon_auto",
                "",
            ]
        )

    for host, port in testnet_nodes:
        name = f"testnet_{host.replace('.', '_')}"
        lines.extend(
            [
                f"  [[{name}]]",
                "    type = TCPClientInterface",
                "    enabled = yes",
                f"    target_host = {host}",
                f"    target_port = {port}",
                "",
            ]
        )

    return "\n".join(lines)


def write_config(
    enable_transport: bool = True,
    testnet_nodes: list[tuple[str, int]] | None = None,
    autointerface: bool = True,
) -> str:
    """Generate and write the Reticulum config file to disk.

    Returns the config content string.
    """
    ensure_dirs()
    config = generate_config(
        enable_transport=enable_transport,
        testnet_nodes=testnet_nodes,
        autointerface=autointerface,
    )
    path = rns_config_path()
    with open(path, "w") as f:
        f.write(config)
    os.chmod(path, 0o600)
    return config


def get_config_path() -> str:
    """Return the path to the Reticulum config directory."""
    return RNS_CONFIG_DIR
