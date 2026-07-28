# Changelog

## [1.0.0] - 2026-07-28

### Fixed

- **Test suite modernized for FastAPI 0.140+** — included routers are mounted
  lazily (`_IncludedRouter`), so tests that introspected `app.routes` could no
  longer see routes. 13 failing tests (plus 3 vacuously-passing ones) now use
  `fastapi.testclient.TestClient` and assert on real HTTP responses/status
  codes; route enumeration uses the OpenAPI schema (`/openapi.json`).
  Full suite green: 135 passed (91 unit + 44 integration).
- **Static assets path** — `STATIC_DIR` now points at the package's own
  `reticulum_beacon/static/` directory instead of a repo-root-relative
  `../../../static` path that broke outside editable checkouts; the `/static`
  mount in `api/app.py` uses the same constant.

### Changed

- **README truth pass** — removed or annotated claims that did not match the
  code: PyPI package and ghcr.io image (not yet published), Serial/RNode
  config generation, LXMF priority queuing / configurable TTL, the unshipped
  hardened systemd unit file, and the web page routes shadowed by the REST
  API (`/api/v1/messages`, `/bots`, `/interfaces` serve JSON — documented as
  a known limitation).
- `docs/ANALYSIS_REPORT.md` — moved the AI codebase-analysis artifact out of
  the repo root.

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
