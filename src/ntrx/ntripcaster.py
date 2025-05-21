#!/usr/bin/env python
import os
import sys
import time
import json
import logging
import base64
import signal
import asyncio
from collections import defaultdict
from redis.asyncio import Redis
from config import *

class Agent:
    """Class to represent an agent (either client or source)."""
    def __init__(self, reader: asyncio.StreamReader, 
                 writer: asyncio.StreamWriter, 
                 mountpoint: str, 
                 agent_type: str, 
                 real_ip: str = None):
        self.reader = reader
        self.writer = writer
        self.mountpoint = mountpoint
        self.agent_type = agent_type
        self.in_bytes = 0
        self.out_bytes = 0
        self.in_bps = 0
        self.out_bps = 0
        self.last_activity = time.time()
        self.peer = writer.get_extra_info("peername")
        self.real_ip = real_ip or self.peer[0]
        self._caster = None 

    def set_caster(self, caster: 'NtripCaster') -> None:
        """Set reference to NtripCaster instance for state updates"""
        self._caster = caster
        
    async def update_activity(self) -> None:
        """Update the last activity timestamp and publish state"""
        self.last_activity = time.time()
        if self._caster:
            try:
                await self._caster.publish_state()
            except Exception as e:
                logging.error(f"Failed to publish state update: {e}")
        
    def to_dict(self) -> dict:
        """Convert agent to dictionary for JSON serialization"""
        current_time = time.time()
        return {
            'mountpoint': self.mountpoint,
            'agent_type': self.agent_type,
            'in_bytes': self.in_bytes,
            'out_bytes': self.out_bytes,
            'in_bps': self.in_bps,
            'out_bps': self.out_bps,
            'last_activity': self.last_activity,
            'peer': self.peer,
            'real_ip': self.real_ip,
            'seconds_since_last_activity': round(current_time - self.last_activity, 2)
        }

class NtripCaster:
    def __init__(self, config_file: str):
        self.config = self.load_config(config_file)
        self.sources: dict[str, Agent] = {}  # mountpoint -> Agent
        self.clients: defaultdict[str, list[Agent]] = defaultdict(list)  # mountpoint -> list of Agents
        self.redis: Redis | None = None  # Will be initialized in start_server

    def load_config(self, config_file: str) -> dict:
        """Load configuration from a JSON file."""
        with open(config_file, "r") as f:
            return json.load(f)

    def authenticate_source(self, username: str, mountpoint: str) -> bool:
        """Check if source (base station) is allowed."""
        allowed = self.config["tokens_source"].get(username)
        return allowed == "*" or allowed == mountpoint

    def authenticate_client(self, auth_header: str, mountpoint: str) -> bool:
        """Authenticate client using HTTP Basic authentication."""
        try:
            if not auth_header.startswith("Basic "):
                return False
            b64_encoded = auth_header[6:]
            decoded = base64.b64decode(b64_encoded).decode("utf-8")
            if ":" not in decoded:
                return False
            username, password = decoded.split(":", 1)
            key = f"{username}:{password}"
            allowed = self.config["tokens_client"].get(key)
            return allowed == "*" or allowed == mountpoint
        except Exception as e:
            logging.error(f"error: client authentication: {e}")
            return False

    async def publish_state(self) -> None:
        """Publish the current state to Redis."""
        if self.redis:
            try:
                state = self.get_state()
                logging.debug("Publishing state update to Redis")
                await self.redis.set('ntripcaster_state', json.dumps(state))
            except Exception as e:
                logging.error(f"Failed to publish state to Redis: {e}")

    async def handle_source(self, agent: Agent) -> None:
        """Continuously poll for binary data from source and forward to all clients."""
        agent.set_caster(self)
        peer = agent.peer
        logging.info(f"processing source for mountpoint '{agent.mountpoint}' from {agent.real_ip} (peer: {peer})")

        try:
            await agent.update_activity()  # Initial state update
            while True:
                data = await agent.reader.read(1024)
                if not data:
                    break
                agent.in_bytes += len(data)
                agent.in_bps = len(data) * 8
                await agent.update_activity()
                if agent.mountpoint not in self.clients:
                    continue
                to_remove = []
                for client in self.clients[agent.mountpoint]:
                    try:
                        client.writer.write(data)
                        await client.writer.drain()
                        client.out_bytes += len(data)
                        client.out_bps = len(data) * 8
                        await client.update_activity()  # Fixed: added await
                    except Exception as e:
                        logging.error(f"error: sending data to client: {e}")
                        to_remove.append(client)
                for client in to_remove:
                    self.clients[agent.mountpoint].remove(client)
        except Exception as e:
            logging.error(f"error: processing source for mountpoint '{agent.mountpoint}': {e}")
        finally:
            logging.info(f"source for mountpoint '{agent.mountpoint}' closed by {peer}")
            if agent.mountpoint in self.sources:
                del self.sources[agent.mountpoint]
            agent.writer.close()
            await agent.writer.wait_closed()
            await self.publish_state()  # Final state update

    async def handle_client_conn(self, agent: Agent) -> None:
        """Maintain connection with client... clients usually do not send data except NMEA GGAs."""
        agent.set_caster(self)
        peer = agent.peer
        logging.info(f"handling client for mountpoint '{agent.mountpoint}' from {agent.real_ip} (peer: {peer})")

        try:
            while True:
                data = await agent.reader.read(1024)
                if not data:
                    break
                logging.debug(f"received data from client for mountpoint '{agent.mountpoint}' from {peer}")
                agent.in_bytes += len(data)
                agent.in_bps = len(data) * 8
                await agent.update_activity()
                if agent.mountpoint in self.sources:
                    source = self.sources[agent.mountpoint]
                    source.writer.write(data)
                    await source.writer.drain()
        except Exception as e:
            logging.error(f"error: processing client for mountpoint '{agent.mountpoint}': {e}")
        finally:
            logging.info(f"client for mountpoint '{agent.mountpoint}' disconnected by {peer}")
            if agent.mountpoint in self.clients and agent in self.clients[agent.mountpoint]:
                self.clients[agent.mountpoint].remove(agent)
            agent.writer.close()
            await agent.writer.wait_closed()
            await self.publish_state()  # Final state update

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming TCP connection and determine if it is a source or client."""
        peer = writer.get_extra_info("peername")
        real_ip = peer[0]
        try:
            first_line = await reader.readline()
            if not first_line:
                writer.close()
                return

            first_line_str = first_line.decode("utf-8", errors="replace").strip()
            logging.info(f"received handshake from {real_ip} (peer: {peer}): {first_line_str}")

            if first_line_str.upper().startswith("SOURCE"):
                parts = first_line_str.split()
                if len(parts) < 3:
                    writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    return
                _, mountpoint, password = parts[:3]
                if not self.authenticate_source(password, mountpoint):
                    writer.write(b"HTTP/1.0 403 Forbidden\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    logging.warning(f"source authentication failed from {real_ip} for mountpoint '{mountpoint}'")
                    return
                agent = Agent(reader, writer, mountpoint, "source", real_ip)
                agent.set_caster(self)  # Set caster before adding to sources
                self.sources[mountpoint] = agent
                writer.write(b"HTTP/1.0 200 OK\r\n\r\n")
                await writer.drain()
                await self.handle_source(agent)

            elif first_line_str.upper().startswith("GET"):
                parts = first_line_str.split()
                if len(parts) < 2:
                    writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    return
                mountpoint = parts[1].lstrip("/")
                headers = {}
                while True:
                    line = await reader.readline()
                    if not line or line == b"\r\n":
                        break
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if ":" in line_str:
                        key, val = line_str.split(":", 1)
                        headers[key.lower()] = val.strip()
                if "authorization" not in headers or not self.authenticate_client(headers["authorization"], mountpoint):
                    response = b'HTTP/1.0 401 Unauthorized\r\nWWW-Authenticate: Basic realm="NTRIP"\r\n\r\n'
                    writer.write(response)
                    await writer.drain()
                    writer.close()
                    logging.warning(f"client authentication failed from {real_ip} for mountpoint '{mountpoint}'")
                    return
                agent = Agent(reader, writer, mountpoint, "client", real_ip)
                agent.set_caster(self)  # Set caster before adding to clients
                response = b"HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\n\r\n"
                writer.write(response)
                await writer.drain()
                self.clients[mountpoint].append(agent)
                await self.handle_client_conn(agent)
            else:
                writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
        except Exception as e:
            logging.error(f"error: handling connection from {real_ip}: {e}")
            writer.close()

    async def start_server(self) -> None:
        """Start the server and listen for connections."""
        try:
            """Start the server and listen for connections."""
            redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
            redis_password = os.getenv("REDIS_PASSWORD", "")
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:6379"
            else:
                redis_url = f"redis://{redis_host}:6379"
            self.redis = Redis.from_url(redis_url, decode_responses=True)
            
            listen_addr = self.config.get("listen_addr", "0.0.0.0")
            listen_port = self.config.get("listen_port", 2101)
            server = await asyncio.start_server(self.handle_connection, listen_addr, listen_port)
            addr = server.sockets[0].getsockname()
            logging.info(f"server started on {addr}")
            await self.publish_state()  # Initial state
            
            async with server:
                await server.serve_forever()
        except Exception as e:
            logging.error(f"Server error: {e}")
            raise
        finally:
            if self.redis:
                await self.redis.close()

    def get_state(self) -> dict:
        """Get the current state of the NTRIP caster."""
        state = {
            "sources": {
                mountpoint: agent.to_dict() 
                for mountpoint, agent in self.sources.items()
            },
            "clients": {
                mountpoint: [agent.to_dict() for agent in agents]
                for mountpoint, agents in self.clients.items()
            }
        }
        return state

def setup_logging(log_file: str, enable_stdout: bool) -> None:
    """Configure logging based on verbosity levels."""
    log_level = logging.INFO

    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if enable_stdout:
        console = logging.StreamHandler()
        console.setLevel(log_level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        console.setFormatter(formatter)
        logging.getLogger().addHandler(console)

def main() -> None:
    fs = FS()
    fs.ensure_storage_folder()

    enable_stdout = "-v" in sys.argv

    setup_logging(fs.ntripcaster_log_file, enable_stdout)
    logging.info(f"using config file '{fs.ntripcaster_config_file}'")

    caster = NtripCaster(fs.ntripcaster_config_file)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown() -> None:
        logging.info("shutting down server...")
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(caster.start_server())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.close()
        logging.info("server shut down successfully.")

if __name__ == "__main__":
    main()