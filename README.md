# 🔴 Reticulum Beacon

> Personal Reticulum transport node and service hub — one command to join the mesh

[![CI](https://github.com/synthalorian/reticulum-beacon/actions/workflows/ci.yml/badge.svg)](https://github.com/synthalorian/reticulum-beacon/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

```
    ╔═════════════════════════════════════════════════════════════════════╗
    ║                  R E T I C U L U M   B E A C O N                   ║
    ║                                                                     ║
    ║   $ beacon setup   $ beacon start   $ beacon api start             ║
    ║                                                                     ║
    ║   ┌─────────────────────────────────────────────────────────────┐  ║
    ║   │                    Beacon Service                           │  ║
    ║   │                                                             │  ║
    ║   │  ┌───────────────────────────────────────────────────────┐  │  ║
    ║   │  │             RNS Transport Node                        │  │  ║
    ║   │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │  │  ║
    ║   │  │  │AutoIntf  │ │TCP Peer  │ │ Serial   │             │  │  ║
    ║   │  │  │(local)   │ │(testnet) │ │ (RNode)  │             │  │  ║
    ║   │  │  └──────────┘ └──────────┘ └──────────┘             │  │  ║
    ║   │  └───────────────────────────────────────────────────────┘  │  ║
    ║   │                                                             │  ║
    ║   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │  ║
    ║   │  │ LXMF         │  │ REST API     │  │ Bot Framework  │  │  ║
    ║   │  │ Propagation  │  │ (FastAPI)    │  │                │  │  ║
    ║   │  │ Node         │  │              │  │ ┌────────────┐ │  │  ║
    ║   │  │              │  │ /status      │  │ │ Echo Bot   │ │  │  ║
    ║   │  │ Store+Fwd    │  │ /peers       │  │ │ Ping Bot   │ │  │  ║
    ║   │  │ Delivery     │  │ /messages    │  │ │ AI Bot     │ │  │  ║
    ║   │  │ Tracking     │  │ /health      │  │ │ Custom...  │ │  │  ║
    ║   │  └──────────────┘  │ /metrics     │  │ └────────────┘ │  │  ║
    ║   │                    └──────────────┘  └────────────────┘  │  ║
    ║   │  ┌──────────────┐  ┌──────────────┐                      │  ║
    ║   │  │ Web UI       │  │ Prometheus   │                      │  ║
    ║   │  │ (HTMX +      │  │ Metrics      │                      │  ║
    ║   │  │  Tailwind)   │  │ + Health     │                      │  ║
    ║   │  └──────────────┘  └──────────────┘                      │  ║
    ║   └─────────────────────────────────────────────────────────────┘  ║
    ║                                                                     ║
    ║   ┌──────────┐  ┌──────────┐  ┌──────────┐                       ║
    ║   │ systemd  │  │ Audit    │  │ Config   │                       ║
    ║   │ Service  │  │ Logging  │  │ ~/.beacon│                       ║
    ║   └──────────┘  └──────────┘  └──────────┘                       ║
    ╚═════════════════════════════════════════════════════════════════════╝
```

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Web UI](#web-ui)
- [Bot Framework](#bot-framework)
- [API Reference](#api-reference)
- [Docker](#docker)
- [Monitoring](#monitoring)
- [Project Structure](#project-structure)
- [Security](#security)
- [Development](#development)
- [License](#license)

---

## Features

### ⚡ One-Command Setup
```bash
beacon setup    # Interactive setup wizard
beacon start    # Start the node
beacon api start  # Launch REST API + Web UI
```

- Auto-generates Reticulum identity
- Configures AutoInterface for local peer discovery
- Connects to public TCP testnet peers out of the box
- Optional systemd service for auto-start on boot

### 📡 Transport Node
- **Auto-discovery** — finds local peers via AutoInterface
- **TCP peering** — connect to public Reticulum testnet nodes
- **Transport mode** — route and forward packets for other nodes
- **Announce** — broadcast your node's presence

> Additional interface types supported by RNS (RNode/LoRa, serial, I2P, …)
> can be added by editing the generated Reticulum config by hand; the
> `beacon` config generator currently emits AutoInterface + TCP client
> interfaces only.

### 📨 LXMF Propagation
- **Store-and-forward** — cache messages for offline peers
- **Peer sync** — exchange propagation data with other nodes (`autopeer`)
- **Delivery identity** — receive LXMF messages addressed to your node

### 🌐 REST API + Web UI
- FastAPI-powered REST API on port **8931** by default
- Web UI dashboard at `http://localhost:8931/`
- HTMX-driven live updates (no page reloads)
- Dark theme with Tailwind CSS
- WebSocket event stream at `/api/v1/events`
- Prometheus metrics at `/api/v1/metrics`

### 🤖 Bot Framework
Create LXMF bots with minimal code. Built-in bots:

| Bot | Description |
|-----|------------|
| **Echo** | Echoes received messages back to sender |
| **Ping** | Responds with latency measurement |
| **AI** | Chat with an AI over the mesh (requires API key) |

### 📊 Monitoring
- **Prometheus metrics** — bandwidth, messages, peers, uptime, bots, API status (17 metrics)
- **Health checks** — aggregate + per-component self-tests with history tracking
- **Structured audit logging** — JSON Lines, auto-rotated at 10 MB
- **Rate limiting** — 30 req/min per IP on POST endpoints

---

## Quick Start

### From Source

> A PyPI package is planned but not yet published — install from source
> for now (see `scripts/publish-test-pypi.sh` for the packaging WIP).

```bash
git clone https://github.com/synthalorian/reticulum-beacon.git
cd reticulum-beacon
pip install -e .
```

### From Docker

> Images are not published to a registry yet — build locally.

```bash
docker build -t reticulum-beacon .
docker run -d --name beacon -p 8931:8931 reticulum-beacon
```

### First Run
```bash
# 1. Setup identity and config
beacon setup

# 2. Start the Reticulum node
beacon start

# 3. In another terminal, start the API + Web UI
beacon api start

# 4. Open http://localhost:8931/ in your browser
#    Or use the CLI to check status:
beacon status
```

### Optional: LXMF Propagation
```bash
beacon propagation start
beacon propagation status
```

### Optional: Load Bots
```bash
beacon bot list            # See available plugins
beacon bot load reticulum_beacon.bots.echo.EchoBot
beacon bot enable echo
```

---

## CLI Reference

```
beacon [COMMAND]

Setup & Management:
  setup        Initialize identity and configuration
  start        Start the Reticulum node
  stop         Stop the node
  status       Show node status and statistics
  config       View or edit configuration
  install      Install systemd service (requires root)
  uninstall    Remove systemd service (requires root)
  version      Show version

Propagation:
  propagation start   Start LXMF store-and-forward node
  propagation stop    Stop propagation node
  propagation status  Show propagation node status
  propagation send    Send an LXMF message

Identity Management:
  identity list       List saved identities
  identity create     Create a new identity
  identity show       Show identity details
  identity delete     Delete an identity
  identity import     Import identity from file
  identity export     Export identity to file

API Server:
  api start           Start REST API + WebSocket + Web UI
  api stop            Stop API server
  api status          Show API server status

Bots:
  bot list            List registered bots and available plugins
  bot enable          Enable a registered bot
  bot disable         Disable a registered bot
  bot load            Load a bot plugin by class path
```

---

## Web UI

The Web UI is served at `http://localhost:8931/` when the API is running.

### Pages
| Route | Description |
|-------|------------|
| `/api/v1/` | Dashboard — live node stats, propagation, API, bots |

The dashboard is a single-page HTMX app: its panels (messages, bots,
interfaces, peers) are live fragments served under `/api/v1/web/*`.

> **Known limitation:** the web router also defines full-page routes at
> `/api/v1/messages`, `/api/v1/bots`, and `/api/v1/interfaces`, but those
> paths are shared with the REST API, which is registered first and takes
> precedence (they return JSON, auth required). Use the dashboard and its
> HTMX fragments instead.

All pages use **HTMX** for live updates without page reloads. The status bar in the sidebar refreshes every 15 seconds.

### Offline Assets
Download HTMX and Tailwind CSS for local serving (no CDN dependency):

```bash
python -m reticulum_beacon.static.download
```

After downloading, the app automatically serves static files from `/static/` instead of CDN.

---

## Bot Framework

Create custom bots by subclassing `BeaconBot`:

```python
from reticulum_beacon.bots.base import BeaconBot

class WeatherBot(BeaconBot):
    name = "weather"
    description = "Get weather forecasts via LXMF"

    def on_message(self, message):
        # message.content contains the incoming LXMF message
        reply = f"Weather forecast for today: sunny"
        self.reply(message, reply)
```

Built-in bots:
- `reticulum_beacon.bots.echo.EchoBot` — message echo
- `reticulum_beacon.bots.ping.PingBot` — latency response
- `reticulum_beacon.bots.ai_bot.AIBot` — AI chat (set `AI_API_KEY` env var)

---

## API Reference

### Status & Health

```
GET /api/v1/status                    → Node status (identity, uptime, interfaces)
GET /api/v1/health                    → Aggregate health (ok/warning/degraded/stopped)
GET /api/v1/health/self-test          → Detailed component probes
GET /api/v1/health/history            → Trend analysis of recent self-tests
GET /api/v1/health/diagnostics        → Safe diagnostic summary
```

### Messages

```
GET  /api/v1/messages                 → List stored messages
POST /api/v1/messages/send            → Send an LXMF message
```

### Peers & Interfaces

```
GET /api/v1/peers                     → Discovered peers
GET /api/v1/interfaces                → Active interfaces
```

### Monitoring

```
GET /api/v1/metrics                   → Prometheus metrics
```

### WebSocket

```
ws://localhost:8931/api/v1/events     → Real-time event stream
```

### Authentication

API endpoints require a Bearer token. The auto-generated key is logged on startup.

```bash
# With API key
curl -H "Authorization: Bearer <key>" http://localhost:8931/api/v1/status

# Health and metrics are public (no auth required)
curl http://localhost:8931/api/v1/health
curl http://localhost:8931/api/v1/metrics
```

Set via environment variable:

```bash
export BEACON_API_KEY="your-strong-secret-key"
beacon api start
```

---

## Docker

### Build
```bash
git clone https://github.com/synthalorian/reticulum-beacon.git
cd reticulum-beacon
docker build -t reticulum-beacon .
```

### Run
```bash
# With persistent data volume
docker volume create beacon-data

docker run -d \
  --name beacon \
  --restart unless-stopped \
  -p 8931:8931 \
  -e BEACON_API_KEY="your-secret-key" \
  -v beacon-data:/etc/reticulum-beacon \
  reticulum-beacon

# Check logs
docker logs -f beacon
```

### Docker Compose
```yaml
services:
  beacon:
    build: .
    container_name: reticulum-beacon
    restart: unless-stopped
    ports:
      - "8931:8931"
    environment:
      - BEACON_API_KEY=${BEACON_API_KEY}
    volumes:
      - beacon-data:/etc/reticulum-beacon

volumes:
  beacon-data:
```

### Security
- Runs as non-root `beacon` user
- Multi-stage build for minimal image size
- `VOLUME` for configuration persistence
- Only `openssl` and `ca-certificates` as runtime system deps

---

## Monitoring

### Prometheus Metrics (17 metrics)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `beacon_uptime_seconds` | Gauge | — | Node uptime in seconds |
| `beacon_running` | Gauge | — | 1 if node is running |
| `beacon_transport_enabled` | Gauge | — | 1 if transport mode is enabled |
| `beacon_interfaces_active` | Gauge | — | Active interface count |
| `beacon_interfaces_online` | Gauge | — | Interfaces marked online |
| `beacon_bandwidth_bytes_total` | Counter | `direction` | Bytes in/out |
| `beacon_peers_total` | Gauge | — | Connected peer count |
| `beacon_messages_stored` | Gauge | — | Messages in store |
| `beacon_messages_received_total` | Counter | — | Messages received |
| `beacon_messages_sent_total` | Counter | — | Messages sent |
| `beacon_announces_received_total` | Counter | — | Announces received |
| `beacon_bots_active` | Gauge | — | Active bot count |
| `beacon_bots_total` | Gauge | — | Total registered bots |
| `beacon_api_running` | Gauge | — | API server status |
| `beacon_api_tls_enabled` | Gauge | — | TLS status |
| `beacon_health_status` | Gauge | — | 0=stopped, 1=degraded, 2=warning, 3=ok |
| `beacon_connectivity` | Gauge | — | 1 if any interface is online |

All metrics use **fixed-cardinality labels only** — no identity hashes, IPs, or paths.

### Grafana
```yaml
scrape_configs:
  - job_name: 'beacon'
    static_configs:
      - targets: ['localhost:8931']
    metrics_path: '/api/v1/metrics'
```

---

## Project Structure

```
reticulum-beacon/
├── .github/workflows/ci.yml     # CI/CD: ruff, mypy, pytest, Docker build
├── Dockerfile                    # Multi-stage production container
├── .dockerignore                 # Exclude tests, git, venv from image
├── LICENSE                       # Apache 2.0
├── pyproject.toml                # Package metadata, deps, tooling config
├── README.md
├── src/reticulum_beacon/
│   ├── __init__.py               # Version
│   ├── main.py                   # Typer CLI entry point
│   ├── node.py                   # BeaconNode — RNS transport node
│   ├── audit.py                  # Structured JSON audit logging
│   ├── config/
│   │   └── generator.py          # Reticulum config file generation
│   ├── identity/
│   │   └── manager.py            # Identity CRUD with security validation
│   ├── propagation/
│   │   └── node.py               # LXMF store-and-forward propagation
│   ├── crypto/
│   │   └── certs.py              # Self-signed TLS certificate generation
│   ├── api/
│   │   ├── app.py                # FastAPI app factory + middleware
│   │   ├── manager.py            # API server lifecycle
│   │   ├── websocket.py          # EventManager pub/sub
│   │   └── routes/
│   │       ├── status.py         # Node status endpoint
│   │       ├── messages.py       # Message send/list endpoints
│   │       ├── peers.py          # Peer discovery endpoints
│   │       ├── metrics.py        # Prometheus metrics (17 metrics)
│   │       └── health.py         # Structured health checks
│   ├── web/
│   │   ├── routes.py             # Web UI route handlers (HTMX)
│   │   └── templates/
│   │       ├── base.html         # Layout with sidebar + dark theme
│   │       ├── dashboard.html    # Live node stats dashboard
│   │       ├── messages.html     # Inbox + send form
│   │       ├── bots.html         # Bot management
│   │       ├── interfaces.html   # Interfaces + peers
│   │       └── fragments/        # HTMX partial templates
│   ├── bots/
│   │   ├── base.py               # BeaconBot base class
│   │   ├── loader.py             # BotRegistry — register, load, discover
│   │   ├── echo.py               # EchoBot
│   │   ├── ping.py               # PingBot
│   │   └── ai_bot.py             # AIBot (requires API key)
│   ├── cli/
│   │   └── commands.py           # All CLI command implementations
│   └── static/
│       ├── __init__.py           # has_local_assets(), get_local_urls()
│       └── download.py           # Download HTMX + Tailwind locally
└── tests/
    ├── test_basic.py             # 91 unit tests (all modules)
    └── test_integration.py       # 44 integration tests (infrastructure)
```

---

## Security

Reticulum Beacon is designed with **defense-in-depth** across every layer.

### API Authentication

| Setting | Mechanism |
|---------|-----------|
| Default | Bearer token via `BEACON_API_KEY` env var (auto-generated 32-char hex key on first run) |
| Verification | Constant-time HMAC comparison to prevent timing attacks |
| Public endpoints | `/api/v1/health`, `/api/v1/metrics`, and all `/api/v1/web/` paths |
| Key rotation | Restart the API server after changing `BEACON_API_KEY` |

### Transport Layer Security (TLS)

| Setting | Detail |
|---------|--------|
| Auto-generated | ECDSA P-256 self-signed cert via `cryptography` on first use |
| Storage | `~/.beacon/certs/` — private key at `0o600`, cert at `0o644` |
| Custom certs | `beacon api start --cert /path/to/cert.pem --key /path/to/key.pem` |
| SAN | `DNS:localhost, IP:127.0.0.1` |
| WebSocket | `wss://` when TLS is enabled, Origin header validated server-side |

### Rate Limiting

- **Scope:** POST endpoints only (mutations)
- **Window:** 60 seconds per client IP
- **Limit:** 30 requests per window
- **Response:** HTTP 429 with `Retry-After` header
- **Logging:** Rate-limit violations recorded in audit log

### CORS

```
Default: http://127.0.0.1, http://localhost
Override: BEACON_CORS_ORIGINS env var (comma-separated)
```

Methods restricted to `GET` and `POST`. Headers restricted to `Authorization` and `Content-Type`.

### Request Validation

- **Body size:** Capped at 1 MB by uvicorn
- **Identity names:** Regex `^[a-zA-Z0-9_\-]+$` — no dots, slashes, or special chars
- **Path traversal:** All file operations use `os.path.realpath()` with prefix checks
- **Import validation:** Identity files capped at 10 KB, must be valid RNS identity
- **Export safety:** Destinations restricted to `$HOME` and `$CWD`

### Audit Logging

Every security-relevant event is recorded to `~/.beacon/audit.log`:

| Event | Details |
|-------|---------|
| `auth.failure` | Client IP, reason (invalid_key, missing) |
| `identity.*` | Create, delete, import, export with name and hash |
| `bot.*` | Bot load, enable, disable actions |
| `system.*` | Node start/stop, API start/stop |
| `rate_limit.exceeded` | Client IP and endpoint |
| `message.*` | Sender and destination hashes (not content) |

Format: JSON Lines (newline-delimited JSON). Auto-rotated at 10 MB to `audit.log.old`.

### Bot Framework Security

- Bots receive messages via controlled callbacks — no direct filesystem access
- AI bot API keys are redacted from all error responses
- Bot class paths are validated before loading
- Scheduler runs in a daemon thread that exits with the main process

### Web UI Security

- CSRF protection via `HX-Request` header check on all POST endpoints
- Content-Security-Policy header restricts scripts to `'self'` and trusted CDNs
- Identity hashes truncated to 16 characters in UI
- Input length limits on all form fields
- HTMX loaded with SRI integrity hashes (when using CDN)

### Systemd Hardening

> **Planned, not yet shipped.** The hardened `systemd/reticulum-beacon.service`
> unit file referenced by `beacon install` is not included in the repository
> yet; `beacon install` will report "Service unit not found" until it is added.
> The unit is intended to apply 10+ security flags:
```
CapabilityBoundingSet=~CAP_NET_RAW
ProtectKernelLogs=yes
ProtectKernelModules=yes
ProtectClock=yes
ProtectHostname=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
MemoryDenyWriteExecute=yes
SystemCallFilter=@system-service
RestrictNamespaces=yes
RemoveIPC=yes
```

### Best Practices

1. **Bind to localhost** — The API defaults to `127.0.0.1`. Use a reverse proxy (nginx/Caddy) if external access is needed.
2. **Set BEACON_API_KEY** — Override the auto-generated key with a strong secret in production.
3. **Use TLS** — Even on localhost, `--tls` prevents local network sniffing.
4. **Audit your logs** — Check `~/.beacon/audit.log` regularly for auth failures.
5. **Rotate API keys** — Periodically change `BEACON_API_KEY` and restart the API.

---

## Development

### Setup
```bash
git clone https://github.com/synthalorian/reticulum-beacon.git
cd reticulum-beacon

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Run Tests
```bash
# All 136 tests
python -m pytest tests/ -v

# Run specific test class
python -m pytest tests/ -v -k TestWebUI

# Run integration tests only
python -m pytest tests/test_integration.py -v
```

### Code Quality
```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/ --check
ruff format src/ tests/

# Type check
mypy src/reticulum_beacon/
```

### Pre-commit Checklist
```bash
ruff check src/ tests/
ruff format src/ tests/ --check
mypy src/reticulum_beacon/
python -m pytest tests/ -v --tb=short
```

### Build Wheel
```bash
pip install build
python -m build --wheel
# Output: dist/reticulum_beacon-*.whl
```

### Download Offline Assets
```bash
python -m reticulum_beacon.static.download
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Reticulum | RNS library |
| Messaging | LXMF |
| Web Framework | FastAPI + Uvicorn |
| Web UI | Jinja2 + HTMX + Tailwind CSS |
| CLI | Typer |
| Security | cryptography (TLS) |
| Metrics | prometheus-client |
| Testing | pytest + unittest |
| Linting | ruff |
| Type Checking | mypy |
| Container | Docker (multi-stage) |
| CI | GitHub Actions |
| Service | systemd |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

---

## Credits

Built by **synthalorian 🎹🤺** ([@synthalorian](https://github.com/synthalorian)).

---

## ☕ Support the Developer

If this project saved you time, solved a problem, or just made your day a little more neon, you can fuel the next one:

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/synthalorian)
