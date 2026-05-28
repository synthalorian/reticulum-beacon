# Reticulum Beacon — Implementation Plan

## Overview

Reticulum Beacon is a personal transport node and service hub that runs as a systemd service on Linux. It bridges the gap between "I installed rns" and "I have a functioning node on the Reticulum network" — one command setup, auto-discovery, LXMF propagation, REST API, and bot framework.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Reticulum Beacon                        │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Transport   │  │    LXMF      │  │   REST API   │  │
│  │    Node      │  │  Propagation │  │  (FastAPI)   │  │
│  │  (rnsd)      │  │    Store     │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│  ┌──────┴─────────────────┴──────────────────┴───────┐  │
│  │              Reticulum Network Stack (RNS)         │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                               │
│  ┌──────────────────────┴────────────────────────────┐  │
│  │              Physical Interfaces                   │  │
│  │  AutoInterface  │  TCPClient  │  RNode (LoRa)     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Bot Engine  │  │   Web UI     │  │  Metrics     │  │
│  │  (plugins)   │  │  (basic mgmt)│  │ (Prometheus) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Node (3-4 days)

### 1.1 CLI & Setup
- `beacon setup` — Initialize Reticulum config, create identity, configure default interfaces
- `beacon start` — Start the daemon (foreground or background via systemd)
- `beacon stop` — Graceful shutdown
- `beacon status` — Show node status, interfaces, peers
- `beacon config` — View/edit Reticulum configuration

### 1.2 Auto-Discovery
- AutoInterface for zero-config local peer discovery (Ethernet/WiFi)
- TCP client to public Reticulum testnet nodes for global connectivity
- Periodic announce of node capabilities

### 1.3 Systemd Integration
- `beacon install` — Install systemd service unit
- `beacon uninstall` — Remove service
- Auto-restart on failure
- Journal logging

### Files
```
src/reticulum_beacon/
├── __init__.py
├── main.py          # CLI entry point (click or typer)
├── node.py          # Transport node management
├── config/
│   ├── __init__.py
│   └── generator.py # Config file generation
└── cli/
    ├── __init__.py
    └── commands.py   # CLI commands
```

---

## Phase 2: LXMF Propagation (2-3 days)

### 2.1 Propagation Node
- Store-and-forward message storage (SQLite backend)
- Auto-announce propagation node on the network
- Message expiry and cleanup (configurable retention)
- Bandwidth-aware delivery (respect per-interface limits)

### 2.2 Identity Management
- Create/manage LXMF identities
- Import/export identity files
- Display name configuration

### Files
```
src/reticulum_beacon/
├── propagation/
│   ├── __init__.py
│   ├── store.py      # SQLite message store
│   └── node.py       # LXMF propagation node
└── identity/
    ├── __init__.py
    └── manager.py     # Identity CRUD
```

---

## Phase 3: REST API (2-3 days)

### 3.1 FastAPI Endpoints
```
GET  /api/v1/status          — Node status, uptime, interface stats
GET  /api/v1/peers           — Discovered peers and link quality
GET  /api/v1/interfaces      — Interface list and status
GET  /api/v1/messages        — LXMF message inbox
POST /api/v1/messages/send   — Send LXMF message
GET  /api/v1/announces       — Recent announce stream
GET  /api/v1/metrics         — Prometheus-format metrics
```

### 3.2 WebSocket
- Real-time event stream (new messages, peer changes, announces)
- Live interface statistics

### Files
```
src/reticulum_beacon/
├── api/
│   ├── __init__.py
│   ├── app.py        # FastAPI app
│   ├── routes/
│   │   ├── status.py
│   │   ├── messages.py
│   │   ├── peers.py
│   │   └── metrics.py
│   └── websocket.py  # Real-time events
```

---

## Phase 4: Bot Engine (2-3 days)

### 4.1 Plugin System
```python
class BeaconBot:
    name = "weather_bot"

    def on_message(self, sender, message):
        """Called when an LXMF message arrives"""
        if "weather" in message.content.lower():
            report = get_weather()
            self.reply(sender, report)

    def on_announce(self, destination_hash, identity, app_data):
        """Called when a node announces"""
        pass

    def scheduled(self):
        """Periodic task (configurable interval)"""
        pass
```

### 4.2 Built-in Bots
- **Echo Bot** — Replies to any message (testing)
- **Ping Bot** — Responds with latency stats
- **Alert Bot** — Sends notifications on network events
- **AI Bot** — Integrates with LLM API for conversational responses

### Files
```
src/reticulum_beacon/
├── bots/
│   ├── __init__.py
│   ├── base.py       # BeaconBot base class
│   ├── loader.py     # Plugin discovery/loading
│   ├── echo.py
│   ├── ping.py
│   └── ai_bot.py
```

---

## Phase 5: Web UI (2-3 days)

### 5.1 Basic Management Interface
- Status dashboard (network health, peer count, uptime)
- Message inbox/composer
- Interface configuration
- Bot management (enable/disable, view logs)
- Node identity display (QR code for sharing)

### 5.2 Tech
- Jinja2 templates + HTMX (keep it simple, no JS build step)
- Served by the same FastAPI instance
- Tailwind CSS via CDN

### Files
```
src/reticulum_beacon/
├── web/
│   ├── __init__.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── messages.html
│   │   └── bots.html
│   └── static/
│       └── style.css
```

---

## Phase 6: Monitoring & Metrics (1-2 days)

### 6.1 Prometheus Metrics
- `beacon_uptime_seconds`
- `beacon_peers_total`
- `beacon_interfaces_active`
- `beacon_messages_received_total`
- `beacon_messages_propagated_total`
- `beacon_bandwidth_bytes_total{direction="in|out"}`
- `beacon_announces_received_total`

### 6.2 Health Checks
- Self-test on startup (interface connectivity, identity validity)
- Periodic path probes to known nodes
- Alert on degraded connectivity

---

## Dependencies

```toml
[project]
name = "reticulum-beacon"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "rns>=1.3.0",
    "lxmf>=0.5.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "typer>=0.12.0",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.20.0",
    "prometheus-client>=0.20.0",
    "jinja2>=3.1.0",
]
```

---

## Total Estimate

| Phase | Days | Cumulative |
|-------|------|-----------|
| Core Node | 3-4 | 3-4 |
| LXMF Propagation | 2-3 | 5-7 |
| REST API | 2-3 | 7-10 |
| Bot Engine | 2-3 | 9-13 |
| Web UI | 2-3 | 11-16 |
| Monitoring | 1-2 | 12-18 |

**MVP (Phase 1-2):** 5-7 days to a functioning propagation node.
**Full feature set:** 12-18 days.
