# 🔴 Reticulum Beacon

> Personal Reticulum transport node and service hub — one command to join the mesh

```
    ╔═════════════════════════════════════════════════════════════════════╗
    ║                  R E T I C U L U M   B E A C O N                   ║
    ║                                                                     ║
    ║   $ beacon setup                                                    ║
    ║   $ beacon start                                                    ║
    ║                                                                     ║
    ║   ┌─────────────────────────────────────────────────────────────┐  ║
    ║   │                   Beacon Service                            │  ║
    ║   │                                                             │  ║
    ║   │  ┌───────────────────────────────────────────────────────┐  │  ║
    ║   │  │              RNS Transport Node                       │  │  ║
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
    ║   │  │              │  │ GET /status  │  │ │ Weather Bot│ │  │  ║
    ║   │  │ Store+Fwd    │  │ GET /peers   │  │ │ Alert Bot  │ │  │  ║
    ║   │  │ Delivery     │  │ POST /msg    │  │ │ AI Bot     │ │  │  ║
    ║   │  │ Tracking     │  │ GET /metrics │  │ │ Custom...  │ │  │  ║
    ║   │  └──────────────┘  └──────────────┘  │ └────────────┘ │  │  ║
    ║   │                                      └────────────────┘  │  ║
    ║   │  ┌──────────────┐  ┌──────────────┐                      │  ║
    ║   │  │ Health Mon   │  │ Web UI       │                      │  ║
    ║   │  │ (Prometheus) │  │ (basic mgmt) │                      │  ║
    ║   │  └──────────────┘  └──────────────┘                      │  ║
    ║   └─────────────────────────────────────────────────────────────┘  ║
    ║                                                                     ║
    ║   ┌──────────┐  ┌──────────┐  ┌──────────┐                       ║
    ║   │ systemd  │  │ SQLite   │  │ Config   │                       ║
    ║   │ Service  │  │ Storage  │  │ ~/.beacon│                       ║
    ║   └──────────┘  └──────────┘  └──────────┘                       ║
    ╚═════════════════════════════════════════════════════════════════════╝
```

## Overview

Reticulum Beacon is a personal Reticulum transport node and service hub that turns your Linux machine into a full mesh network participant. **One command to set up** — auto-discovers local peers, connects to the testnet, starts propagating messages, and exposes a REST API for integrations.

Runs as a **systemd service** for 24/7 unattended operation. Includes a bot framework for creating LXMF-powered bots.

## Features

### ⚡ One-Command Setup
```bash
beacon setup    # Interactive setup wizard
beacon start    # Start the node (foreground or systemd)
```
- Auto-generates Reticulum identity
- Configures AutoInterface for local peer discovery
- Optionally connects to public TCP testnet peers
- Sets up systemd service for auto-start on boot

### 📡 Transport Node
- **Auto-discovery** — finds local peers via AutoInterface (mDNS)
- **TCP peering** — connect to public Reticulum testnet nodes
- **Serial/RNode** — LoRa radio interface support
- **Transport mode** — route and forward packets for other nodes
- **Announce** — broadcast your node's presence and available services

### 📨 LXMF Propagation
- **Store-and-forward** — cache messages for offline peers
- **Priority queuing** — urgent messages get fast-path delivery
- **Configurable storage** — TTL, max size, max messages
- **Delivery tracking** — know when your messages were propagated
- **Peer sync** — exchange propagation data with other propagation nodes

### 🌐 REST API
FastAPI-powered REST API for webhooks and third-party integrations:

```bash
# Node status
GET /api/v1/status

# Peer management
GET /api/v1/peers
GET /api/v1/peers/{identity}

# Messaging
POST /api/v1/messages/send
GET /api/v1/messages
GET /api/v1/messages/{id}

# Interface management
GET /api/v1/interfaces
POST /api/v1/interfaces/{name}/enable
POST /api/v1/interfaces/{name}/disable

# Metrics
GET /metrics    # Prometheus format
```

### 🤖 Bot Framework
Create LXMF bots with minimal code:

```python
from reticulum_beacon.bots import Bot, MessageHandler

class WeatherBot(Bot):
    name = "Weather Bot"
    description = "Get weather forecasts via LXMF"

    @MessageHandler.match("weather *")
    async def handle_weather(self, message, location):
        forecast = await self.get_weather(location)
        await self.reply(message, forecast)

if __name__ == "__main__":
    WeatherBot().run()
```

Built-in bot examples:
- **Weather Bot** — get forecasts for any location
- **Alert Bot** — network alerts and notifications
- **AI Assistant Bot** — chat with an AI over the mesh
- **Ping Bot** — respond with latency measurements

### 📊 Monitoring
- **Prometheus metrics** — `/metrics` endpoint for Grafana dashboards
- **Health checks** — `/api/v1/health` for load balancers
- **Logging** — structured JSON logs with configurable levels
- **Web UI** — basic management dashboard at `http://localhost:8080`

## Tech Stack

| Component     | Technology                     |
|--------------|-------------------------------|
| Language      | Python 3.11+                  |
| Reticulum     | RNS library (pip)             |
| Web Framework | FastAPI + Uvicorn              |
| Database      | SQLite (via aiosqlite)         |
| Service       | systemd unit                   |
| CLI           | Click / Typer                  |
| Monitoring    | Prometheus client              |
| Testing       | pytest + pytest-asyncio        |

## Quick Start

### Install

```bash
# From PyPI (eventually)
pip install reticulum-beacon

# From source
git clone https://github.com/synthalorian/reticulum-beacon.git
cd reticulum-beacon
pip install -e .
```

### Setup & Run

```bash
# Interactive setup (first time)
beacon setup

# Start in foreground
beacon start

# Start as systemd service (background, auto-restart)
beacon install    # Install systemd service
beacon start --service

# Check status
beacon status
```

### Using the API

```bash
# Check node status
curl http://localhost:8080/api/v1/status

# Send an LXMF message
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"destination": "abc123...", "content": "Hello mesh!"}'

# List discovered peers
curl http://localhost:8080/api/v1/peers

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Project Structure

```
reticulum-beacon/
├── src/reticulum_beacon/
│   ├── __init__.py
│   ├── main.py          # CLI entry point
│   ├── node.py          # Transport node logic
│   ├── propagation.py   # LXMF propagation engine
│   ├── api/             # FastAPI routes
│   ├── bots/            # Bot framework + examples
│   ├── cli/             # Click/Typer CLI commands
│   └── config/          # Config management
├── systemd/             # systemd unit file
├── tests/               # pytest tests
├── pyproject.toml
└── README.md
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Credits

Built by **synth** (synthalorian) with **synthshark**.
