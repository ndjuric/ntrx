# ntrx 🛰️ – RTK Correction Data Dissemination

Welcome to **ntrx**!  
A high-performance, asynchronous, Redis-native NTRIP caster written in Python using FastAPI and `asyncio`.

---

## 🚀 Key Features

- **Redis-Native Architecture**: Uses Redis Pub/Sub for Inter-Process Communication (IPC).
  - **Live Position Streaming**: Client NMEA positions are streamed to Redis (`ntrip:positions`).
  - **Kill Switch**: Admin control via Redis (`ntrip:control`) to actively disconnect users.
- **Modern Python Implementation**:
  - Built with **Python 3.12+**, **FastAPI**, and **AsyncIO**.
  - **Strict Typing**: Uses **Pydantic** models for all data exchange and state management.
  - **Clean Code**: Adheres to SOLID principles, low cyclomatic complexity, and class-based design.
- **Scalable**: Stateless design allows horizontal scaling of API instances.

---

## 🧩 Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and schema information.

- **NTRIP Caster**: Handles source/client connections, parses NMEA, and publishes events to Redis.
- **FastAPI Server**: Provides a REST/WebSocket API for monitoring and control (Kill Switch).
- **Redis**: Central message bus for `positions`, `control` commands, and shared `state`.

---

## ⚡ Quick Start

### 1. Prerequisites

- Python 3.12+
- Redis Server (optional — required for live state, position streaming, and kill switch)

### 2. Installation

```bash
git clone https://github.com/ndjuric/ntrx.git
cd ntrx
python -m venv venv
source venv/bin/activate
pip install -e .  # Install in editable mode
```

### 3. Configuration

Create a `.env` file in the project root:

```env
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=changeme
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
LOG_MAX_SIZE_MB=10
LOG_MAX_BACKUP_COUNT=5
```

Edit `storage/ntripcaster.json` to define your Source and Client credentials.

### 4. Running the System

For full functionality (live state, position streaming, kill switch), run Redis alongside the Caster and API. The Caster and API can also run without Redis in degraded mode — core NTRIP data relay will work normally.

**Option A: Individual Processes**

1. Start Redis: `docker-compose up -d`
2. Start API: `python -m ntrx api`
3. Start Caster: `python -m ntrx ntrip`

**Option B: CLI Helper**

```bash
python -m ntrx --help
```

> **Note**: Redis is **optional**. If Redis is not running, the caster and API will start in **degraded mode** — core NTRIP functionality works, but live state publishing, position streaming, and the control channel (kill switch) will be disabled. The program automatically detects `docker-compose.yml` in the project root and suggests `docker-compose up -d` if Redis is unreachable.

> **TODO – Operational Modes**: Two modes are planned:
> 1. **Standalone** *(current)* – mountpoints and state are kept in-memory; Redis is optional (IPC only).
> 2. **Thin Client** – mountpoints and all state are stored in Redis; the caster becomes stateless, enabling horizontal scaling behind a load balancer.

---

## 📡 API Endpoints

- `GET /state` – Returns the current system state (connected sources/clients).
- `POST /api/kill/{username}` – Disconnects a generic user (Source or Client) immediately.
- `WS /ws` – Real-time state updates via WebSocket.
- `GET /` & `GET /debug/routes` - Debug utilities.

---

## 🧪 Testing & Verification

A robust integration test suite is included to verify the entire pipeline (Socket -> Caster -> Redis -> API).

```bash
# Verify connection, streaming, and kill switch
python src/ntrx/tests/integration_test.py
```

---

## 🤝 Contributing

- Code must use **Pydantic** models for any data structure.
- All IPC must go through **Redis**.
- Cyclomatic complexity of methods must be kept under 10.
- 100% adherence to **Class-Based** structure.

---

## 📄 License

MIT License
