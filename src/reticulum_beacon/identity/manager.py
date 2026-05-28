"""Identity management for Reticulum Beacon.

Provides CRUD operations for Reticulum identities used by the
LXMF propagation node and direct messaging.
"""

import glob
import os
import re

import RNS

from ..config import generator as cfg

IDENTITIES_DIR = os.path.join(cfg.BEACON_CONFIG_DIR, "identities")

# Only allow alphanumeric names, hyphens, underscores — no dots, slashes, or path separators
_VALID_IDENTITY_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_identity_name(name: str) -> None:
    """Raise ValueError if the identity name is invalid or could be used for path traversal."""
    if not name:
        raise ValueError("Identity name must not be empty")
    if not _VALID_IDENTITY_NAME_RE.match(name):
        raise ValueError(
            "Identity name must only contain letters, digits, hyphens, and underscores"
        )
    if name.startswith(".") or ".." in name:
        raise ValueError("Identity name cannot start with '.' or contain '..'")


def _resolve_identity_path(name: str) -> str:
    """Return the absolute, resolved filesystem path for a named identity.

    Validates the name, resolves the path, and verifies it stays within
    IDENTITIES_DIR to prevent path traversal attacks.
    """
    _validate_identity_name(name)
    full_path = os.path.realpath(os.path.join(IDENTITIES_DIR, f"{name}.identity"))
    identities_dir_real = os.path.realpath(IDENTITIES_DIR)
    if not full_path.startswith(identities_dir_real + os.sep) and full_path != identities_dir_real:
        raise ValueError(f"Identity path traversal detected for '{name}'")
    return full_path


def ensure_identities_dir():
    os.makedirs(IDENTITIES_DIR, mode=0o700, exist_ok=True)


def identity_path(name: str) -> str:
    """Return the filesystem path for a named identity (validated)."""
    return _resolve_identity_path(name)


def list_identities() -> list[dict]:
    """List all saved identities with metadata."""
    ensure_identities_dir()
    identities = []
    for path in sorted(glob.glob(os.path.join(IDENTITIES_DIR, "*.identity"))):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            identity = RNS.Identity.from_file(path)
            identities.append(
                {
                    "name": name,
                    "hash": RNS.hexrep(identity.hash),
                    "path": path,
                    "size": os.path.getsize(path),
                }
            )
        except Exception as e:
            identities.append(
                {
                    "name": name,
                    "path": path,
                    "error": str(e),
                }
            )
    return identities


def create_identity(name: str) -> RNS.Identity:
    """Create a new identity with the given name."""
    _validate_identity_name(name)

    ensure_identities_dir()
    path = _resolve_identity_path(name)

    if os.path.exists(path):
        raise FileExistsError(f"Identity '{name}' already exists at {path}")

    identity = RNS.Identity()
    identity.to_file(path)
    os.chmod(path, 0o600)
    return identity


def load_identity(name: str) -> RNS.Identity:
    """Load an identity by name."""
    path = _resolve_identity_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Identity '{name}' not found")
    return RNS.Identity.from_file(path)


def delete_identity(name: str) -> None:
    """Delete a saved identity."""
    path = _resolve_identity_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Identity '{name}' not found")
    os.unlink(path)


def import_identity(file_path: str, name: str | None = None) -> RNS.Identity:
    """Import an identity from a file.

    If name is None, the filename (without extension) is used.
    Both the source path and derived name are validated against path traversal.
    """
    # Resolve the source path to prevent traversal during read
    src = os.path.realpath(file_path)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Identity file not found: {file_path}")
    if not os.path.isfile(src):
        raise ValueError(f"Not a regular file: {file_path}")
    # Limit file size to 10 KB (RNS identity files are tiny)
    file_size = os.path.getsize(src)
    if file_size > 10 * 1024:
        raise ValueError(f"File too large for an identity: {file_size} bytes")

    identity = RNS.Identity.from_file(src)
    if identity is None:
        raise ValueError(
            f"File does not contain a valid Reticulum identity: {os.path.basename(file_path)}"
        )

    if name is None:
        name = os.path.splitext(os.path.basename(src))[0]

    _validate_identity_name(name)

    ensure_identities_dir()
    dest = _resolve_identity_path(name)
    if os.path.exists(dest):
        raise FileExistsError(f"Identity '{name}' already exists")

    identity.to_file(dest)
    os.chmod(dest, 0o600)
    return identity


def export_identity(name: str, dest_path: str) -> str:
    """Export an identity to a file.

    Dest path is resolved and checked to stay within the user's home
    or current working directory to prevent overwriting system files.
    Returns the resolved destination path.
    """
    identity = load_identity(name)

    # Resolve destination and ensure it's in a reasonable location
    dest = os.path.realpath(dest_path)
    home = os.path.realpath(os.path.expanduser("~"))
    cwd = os.path.realpath(os.getcwd())
    if not (dest in (home, cwd) or dest.startswith(home + os.sep) or dest.startswith(cwd + os.sep)):
        raise ValueError(
            "Export destination must be within your home directory or current working directory"
        )

    # Warn before overwriting
    if os.path.exists(dest):
        raise FileExistsError(f"Destination already exists: {dest_path}")

    identity.to_file(dest)
    os.chmod(dest, 0o600)
    return dest
