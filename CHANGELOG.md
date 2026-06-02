# Changelog

## [0.1.0] - 2026-06-01

### Features

- **One-Command Setup** — `beacon setup` wizard auto-generates Reticulum identity, configures AutoInterface and TCP peering
- **Transport Node** — Full RNS transport with AutoInterface (local discovery), TCPClient (testnet), and RNode (LoRa) support
- **LXMF Propagation** — Store-and-forward message node with configurable TTL, max size, and delivery tracking
- **REST API** — FastAPI on port 8931 with 17 Prometheus metrics, health checks, and WebSocket event stream
- **Web UI** — HTMX + Tailwind dashboard with live status, message inbox, bot management, and interface viewer
- **Bot Framework** — Plugin system with Echo, Ping, and AI bots; load/enable/disable via CLI or API
- **Security** — Bearer token auth, self-signed TLS, rate limiting (30 req/min), CORS, CSRF protection, audit logging
- **Systemd** — Hardened unit file with 10+ security flags, auto-restart, journal logging
- **Docker** — Multi-stage build, non-root user, persistent volume support
- **CI/CD** — GitHub Actions with ruff, mypy, pytest matrix (Python 3.11/3.12), and Docker build

### Architecture

- 34 Python modules across 10 packages
- 135 tests (91 unit + 44 integration) — all passing
- Structured JSON Lines audit logging with auto-rotation
- Fixed-cardinality Prometheus labels (no identity hash leakage)

### Authorship

Built by **synth** with 🎹🦈
