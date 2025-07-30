# ntrx 🛰️ – RTK Correction Data Dissemination

Welcome to **ntrx**!  
A modern, Python-powered NTRIP caster with a built-in API and WebSocket server for real-time GNSS correction data sharing.

---

## 🚀 What is ntrx?

**ntrx** is a next-generation NTRIP caster written in Python.  
It streams GNSS correction data to clients and shares the latest state via a FastAPI-powered HTTP/WebSocket API.  
**Redis** is used as a fast, in-memory message bus to synchronize state between the NTRIP caster and the API server.

---

## 🧩 How does it work?

- **NTRIP Caster**: Accepts connections from GNSS base stations (sources) and clients, relaying correction data.
- **Redis**: Used to store and publish the current state (sources, clients, stats) in real time.
- **API Server**: FastAPI app exposes `/state` (HTTP) and `/ws` (WebSocket) endpoints for monitoring, integration and even support.
- **Clients**: Can connect via NTRIP, HTTP, or WebSocket to receive data or monitor the system.

> **Note:**  
> Redis is currently required for state sharing between the caster and API.  
> _(TODO: Make Redis optional in a future release!)_

---

## 🛠️ Features

- 🌍 **Modern Python** (asyncio, FastAPI, Typer CLI)
- 🔄 **Real-time state sharing** via Redis
- 🛰️ **NTRIP Caster**: Handles multiple sources and clients
- 📡 **API & WebSocket**: Live monitoring and integration
- 📝 **Configurable** via `.env` and JSON config
- 🪵 **Rotating, gzipped logs**
- 🧪 **Test clients** for HTTP and WebSocket endpoints

---

## ⚡ Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/ndjuric/ntrx.git
cd ntrx
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure your environment

Copy and edit the `.env` file in the project root:

```env
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=your_redis_password
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
```

Edit `storage/ntripcaster.json` to set up your sources, tokens, etc.

### 4. Start Redis

You can use Docker or your system package manager:

```bash
docker-compose up
```

### 5. Run the NTRIP caster or API server

#### Using the CLI:

```bash
python -m ntrx ntrip   # Start the NTRIP caster server
python -m ntrx api     # Start the FastAPI WebSocket API server
```

#### Or with the interactive CLI:

```bash
python -m ntrx
```

---

## 🧑‍💻 CLI Usage

```bash
python -m ntrx --help
```

**Available ntrx subcommands:**

- `ntrip` – Run the NTRIP caster server
- `api` – Run the FastAPI WebSocket API server

---

## 📡 API Endpoints

- `GET /state` – Get the current caster state (sources, clients, stats)
- `WS /ws` – Live state updates via WebSocket

---

## 🧪 Test Clients

- `src/ntrx/test_http_api_endpoint.py` – Test the HTTP `/state` endpoint
- `src/ntrx/test_ws_streaming.py` – Test the WebSocket `/ws` endpoint

---

## 📝 TODO

- [ ] Make Redis optional (allow direct API/caster communication)
- [ ] Add more authentication options - look at more ntrip clients
- [ ] Docker Compose setup for entire project (not just redis)
- [ ] More test coverage

---

## 🤝 Contributing

PRs and issues are welcome!  
Please open an issue or submit a pull request if you have suggestions or improvements.

---

## 📄 License

MIT License

---

**Happy streaming! 🛰️**
