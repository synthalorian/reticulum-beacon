"""TLS certificate management for HTTPS API support.

Auto-generates self-signed certificates on first use so the REST API
can serve HTTPS out of the box. Certificates are stored in
~/.beacon/certs/ with secure file permissions.

Security notes:
- Self-signed certs provide encryption but not identity verification.
  For production use, replace with a CA-signed cert.
- Private key is stored with 0o600 permissions.
- Certificate is valid for 10 years (3650 days).
"""

from __future__ import annotations

import ipaddress
import os
import subprocess
import threading

from ..config import generator as cfg

CERTS_DIR = os.path.join(cfg.BEACON_CONFIG_DIR, "certs")
CERT_PATH = os.path.join(CERTS_DIR, "beacon.pem")
KEY_PATH = os.path.join(CERTS_DIR, "beacon-key.pem")

_generation_lock = threading.Lock()


def cert_paths() -> tuple[str, str]:
    """Return (cert_path, key_path) for the beacon's TLS certificate.

    Auto-generates a self-signed certificate if none exists.
    """
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        with _generation_lock:
            # Double-check after acquiring lock
            if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
                _generate_self_signed()
    return CERT_PATH, KEY_PATH


def _generate_self_signed() -> None:
    """Generate a self-signed ECDSA certificate.

    Tries 'openssl' first (fast, universally available on Linux).
    Falls back to the 'cryptography' Python library.
    """
    os.makedirs(CERTS_DIR, mode=0o700, exist_ok=True)

    # Try openssl CLI (most common)
    if _generate_via_openssl():
        _lockdown_permissions()
        return

    # Fallback to cryptography library
    if _generate_via_cryptography():
        _lockdown_permissions()
        return

    raise RuntimeError(
        "Could not generate TLS certificate. "
        "Install the 'cryptography' Python package or ensure 'openssl' "
        "is available on this system."
    )


def _generate_via_openssl() -> bool:
    """Generate cert via openssl subprocess. Returns True on success."""
    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "ec",
                "-pkeyopt",
                "ec_paramgen_curve:prime256v1",
                "-keyout",
                KEY_PATH,
                "-out",
                CERT_PATH,
                "-days",
                "3650",
                "-nodes",
                "-subj",
                "/CN=reticulum-beacon/O=ReticulumBeacon",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _generate_via_cryptography() -> bool:
    """Generate cert via the cryptography library. Returns True on success."""
    try:
        import datetime

        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        # Generate ECDSA key pair (P-256)
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

        # Build self-signed certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "reticulum-beacon"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ReticulumBeacon"),
            ]
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )

        # Write private key
        with open(KEY_PATH, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write certificate
        with open(CERT_PATH, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return True
    except ImportError:
        return False
    except Exception:
        # Clean up partial files on failure
        for p in (CERT_PATH, KEY_PATH):
            if os.path.exists(p):
                os.unlink(p)
        return False


def _lockdown_permissions() -> None:
    """Ensure private key is only readable by the owner."""
    if os.path.exists(KEY_PATH):
        os.chmod(KEY_PATH, 0o600)
    if os.path.exists(CERT_PATH):
        os.chmod(CERT_PATH, 0o644)
