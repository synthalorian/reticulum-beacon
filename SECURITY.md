# 🔒 Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take the security of Reticulum Beacon seriously. If you believe you have found a
security vulnerability, please **do not** open a public issue.

### Disclosure Process

1. **Report** — Send details to **[synthalorian@gmail.com](mailto:synthalorian@gmail.com)**
   with the subject prefix `[BEACON-SEC]`. Include:
   - Description of the vulnerability
   - Steps to reproduce (PoC preferred)
   - Affected versions
   - Potential impact

2. **Acknowledgment** — You will receive a response within **72 hours**.

3. **Investigation** — We will investigate and may follow up for additional details.
   Expect a status update every **7 days** until resolution.

4. **Fix & Release** — A patch will be prepared and released as a new version. The
   vulnerability will be disclosed **after** the fix is published.

### Scope

In-scope:
- The `reticulum-beacon` Python package (source code, dependencies, configuration)
- The REST API and Web UI served by the beacon
- Authentication, authorization, and audit mechanisms
- TLS certificate handling and transport security

Out-of-scope:
- The Reticulum protocol stack itself (report to [Reticulum](https://github.com/markqvist/Reticulum))
- The LXMF protocol (report to [LXMF](https://github.com/markqvist/LXMF))
- Third-party dependencies (report to the respective maintainers)

## Security Posture

Reticulum Beacon is designed with **defense-in-depth** across every layer:

| Layer | Measures |
|-------|----------|
| **API** | Bearer token auth (constant-time HMAC), rate limiting, CORS, body size limits |
| **TLS** | Auto-generated ECDSA P-256 certs, custom cert support, `wss://` for WebSocket |
| **Storage** | Config dir `0o700`, identity files `0o600`, cert private key `0o600` |
| **Input** | Path traversal prevention, regex name validation, import size caps |
| **Audit** | JSON Lines audit log, 10 MB auto-rotation, all security events recorded |
| **Systemd** | 10+ hardening flags: `ProtectKernelLogs`, `RestrictAddressFamilies`, `MemoryDenyWriteExecute` |
| **Web UI** | CSRF via `HX-Request` header, CSP headers, truncated hash display, input length limits |

See the [Security section of the README](README.md#security) for full details.

## Encryption Standards

| Component | Algorithm | Key Size |
|-----------|-----------|----------|
| TLS certificate | ECDSA (P-256) | 256-bit |
| API key | Random hex string | 256-bit |
| Config file permissions | POSIX | `0o600` |
| Audit log rotation | None (plain JSON, local fs) | — |

## Thanks

We appreciate responsible disclosure. Contributors who report valid vulnerabilities
will be acknowledged in release notes (unless anonymity is requested).
