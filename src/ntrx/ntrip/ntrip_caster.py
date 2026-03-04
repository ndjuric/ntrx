#!/usr/bin/env python
from __future__ import annotations
import os
import sys
import time
import json
import base64
import signal
import asyncio
import traceback
from collections import defaultdict
from typing import Optional
from redis.asyncio import Redis

from ntrx.vfs.fs import FS
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.ntrip.agent import Agent
from ntrx.models.position import ClientPosition
from ntrx.models.control import ControlCommand
from ntrx.models.caster_state import CasterState
from ntrx.models.agent_data import AgentData


class NtripCaster:
    def __init__(self, config_file: str):
        self.fs = FS()
        self.logger = LoggerSetup.get_logger(__name__)
        self.config = self._load_config(config_file)
        self.sources: dict[str, Agent] = {}
        self.clients: defaultdict[str, list[Agent]] = defaultdict(list)
        self.redis: Optional[Redis] = None

    def _load_config(self, config_file: str) -> dict:
        with open(config_file, "r") as f:
            return json.load(f)

    def authenticate_source(self, username: str, mountpoint: str) -> bool:
        allowed = self.config["tokens_source"].get(username)
        return allowed == "*" or allowed == mountpoint

    def authenticate_client(self, auth_header: str, mountpoint: str) -> bool:
        try:
            if not auth_header.startswith("Basic "):
                return False
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            if ":" not in decoded:
                return False
            username, password = decoded.split(":", 1)
            key = f"{username}:{password}"
            allowed = self.config["tokens_client"].get(key)
            return allowed == "*" or allowed == mountpoint
        except Exception as e:
            self.logger.error(f"Client authentication error: {e}")
            return False

    async def publish_state(self) -> None:
        if self.redis:
            try:
                state = self.get_state()
                await self.redis.set('ntripcaster_state', state.model_dump_json())
            except Exception as e:
                self.logger.error(f"Failed to publish state to Redis: {e}")

    def get_state(self) -> CasterState:
        source_data = {m: a.to_data() for m, a in self.sources.items()}
        client_data = {m: [a.to_data() for a in lst] for m, lst in self.clients.items()}
        return CasterState(sources=source_data, clients=client_data)

    async def handle_source(self, agent: Agent) -> None:
        agent.set_caster(self)
        self.logger.info(f"source connected: {agent.mountpoint} from {agent.real_ip}")

        try:
            await agent.update_activity()
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
                        await client.update_activity()
                    except Exception as e:
                        self.logger.error(f"Sending to client failed: {e}")
                        to_remove.append(client)
                for client in to_remove:
                    self.clients[agent.mountpoint].remove(client)
        except Exception as e:
            self.logger.error(f"Source loop error: {e}")
        finally:
            self.logger.info(f"source closed: {agent.mountpoint}")
            if agent.mountpoint in self.sources:
                del self.sources[agent.mountpoint]
            agent.writer.close()
            await agent.writer.wait_closed()
            await self.publish_state()

    def get_source_table_data(self) -> bytes:
        """Generates the NTRIP source table based on connected sources."""
        # Header
        # Format: STR;Mountpoint;Identifier;Format;Format-Details;Carrier;Nav-System;Network;Country;Latitude;Longitude;NMEA;Solution;Generator;Compr-Encr;Authentication;Fee;Bitrate;Misc
        # We will use a simplified format matching standard casters or the C implementation logic
        # Default C implementation: STR;mountpoint;mountpoint;RTCM3X;1005(10),1074-1084-1124(1);2;GNSS;NET;CHN;0.00;0.00;1;1;None;None;B;N;0;
        
        lines = []
        for mount, agent in self.sources.items():
            # For parity with C implementation which often hardcodes these values or derives minimal info
            # We will try to use real data if available, but default to C-like string for compatibility
            line = (f"STR;{mount};{mount};RTCM 3.X;1005(10),1074-1084-1124(1);2;GNSS;NET;UNK;"
                    f"0.00;0.00;1;1;NtripCaster;None;B;N;{agent.in_bps};")
            lines.append(line)
        
        body = "\r\n".join(lines) + "\r\nENDSOURCETABLE\r\n"
        return body.encode("utf-8")

    async def start_control_listener(self) -> None:
        """
        Listens to Redis 'ntrip:control' channel for administrative commands.
        Example: {"action": "kill", "username": "user1"}
        """
        if not self.redis:
            self.logger.warning("Redis is not connected, control listener cannot start.")
            return

        pubsub = self.redis.pubsub()
        await pubsub.subscribe("ntrip:control")
        self.logger.info("Subscribed to Redis channel 'ntrip:control'")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                
                try:
                    # Validate headers/structure with Pydantic
                    # Redis pubsub message['data'] is str/bytes
                    payload = message["data"]
                    if isinstance(payload, bytes):
                        payload = payload.decode()
                    
                    data = json.loads(payload)
                    command = ControlCommand(**data) # Validate
                    
                    if command.action == "kill":
                         self.logger.info(f"Received kill command for user: {command.username}")
                         await self._kill_user(command.username)

                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON in control message: {message['data']}")
                except Exception as e:
                    self.logger.error(f"Error processing control message: {e}")
        except Exception as e:
            self.logger.error(f"Control listener error: {e}")
        finally:
            await pubsub.close()

    async def _kill_user(self, username: str) -> None:
        """Disconnects all clients with the specified username."""
        killed_count = 0
        for mountpoint, agents in list(self.clients.items()):
            for agent in list(agents):
                if getattr(agent, "username", "") == username:
                    self.logger.warning(f"Force closing agent {username} on {mountpoint}")
                    try:
                        agent.writer.close()
                    except Exception as e:
                        self.logger.error(f"Error closing socket for {username}: {e}")
                    killed_count += 1
        
        if killed_count == 0:
            self.logger.debug(f"No active clients found for user {username} to kill.")

    async def _publish_client_position(self, username: str, line: bytes) -> None:
        """Publishes the client's GPGGA position to Redis for real-time tracking."""
        if not self.redis:
            return

        try:
            pos = ClientPosition(
                username=username,
                nmea=line.decode("utf-8", errors="replace"),
                timestamp=time.time()
            )
            await self.redis.publish("ntrip:positions", pos.model_dump_json())
        except Exception as e:
            self.logger.error(f"Failed to publish position for {username}: {e}")

    async def handle_client_conn(self, agent: Agent) -> None:
        agent.set_caster(self)
        self.logger.info(f"client connected: {agent.mountpoint} from {agent.real_ip}")

        try:
            while True:
                data = await agent.reader.read(1024)
                if not data:
                    break
                
                # NMEA Parsing for Map/Tracking
                # C implementation checks for $GPGGA or $GNGGA
                if b"$GPGGA" in data or b"$GNGGA" in data:
                    # We assume the data chunk contains the line. 
                    # For a robust implementation, we should buffer lines, but for C-parity:
                    lines = data.split(b'\n')
                    for line in lines:
                        if b"$GPGGA" in line or b"$GNGGA" in line:
                            # Extract user from agent (we need to pass username to Agent or store it)
                            if hasattr(agent, "username") and agent.username:
                                await self._publish_client_position(agent.username, line.strip())

                agent.in_bytes += len(data)
                agent.in_bps = len(data) * 8
                await agent.update_activity()
                if agent.mountpoint in self.sources:
                    source = self.sources[agent.mountpoint]
                    try:
                        source.writer.write(data)
                        await source.writer.drain()
                    except Exception:
                         # Source might be dead
                         pass
        except Exception as e:
            self.logger.error(f"Client loop error: {e}")
        finally:
            self.logger.info(f"client disconnected: {agent.mountpoint}")
            if agent.mountpoint in self.clients and agent in self.clients[agent.mountpoint]:
                self.clients[agent.mountpoint].remove(agent)
            
            agent.writer.close()
            await agent.writer.wait_closed()
            await self.publish_state()

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        real_ip = peer[0]
        try:
            first_line = await reader.readline()
            if not first_line:
                writer.close()
                return

            first_line_str = first_line.decode("utf-8", errors="replace").strip()
            self.logger.info(f"handshake from {real_ip}: {first_line_str}")

            if first_line_str.upper().startswith("SOURCE"):
                await self._handle_source_handshake(reader, writer, first_line_str, real_ip)
            elif first_line_str.upper().startswith("GET"):
                await self._handle_http_request(reader, writer, first_line_str, real_ip)
            else:
                writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
        except Exception as e:
            self.logger.error(f"connection error from {real_ip}: {e}")
            writer.close()

    async def _handle_source_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                     first_line: str, real_ip: str) -> None:
        parts = first_line.split()
        if len(parts) < 3:
            await self._send_error(writer, b"HTTP/1.0 400 Bad Request\r\n\r\n")
            return

        _, password_val, mountpoint_val = parts[:3]
        if not self.authenticate_source(password_val, mountpoint_val):
            self.logger.warning(f"source auth failed: {real_ip} mountpoint={mountpoint_val}")
            await self._send_error(writer, b"HTTP/1.0 403 Forbidden\r\n\r\n")
            return

        agent = Agent(reader, writer, mountpoint_val, "source", real_ip)
        agent.set_caster(self)
        self.sources[mountpoint_val] = agent
        
        writer.write(b"HTTP/1.0 200 OK\r\n\r\n")
        await writer.drain()
        await self.handle_source(agent)

    async def _handle_http_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                 first_line: str, real_ip: str) -> None:
        parts = first_line.split()
        if len(parts) < 2:
             await self._send_error(writer, b"HTTP/1.0 400 Bad Request\r\n\r\n")
             return
        
        request_path = parts[1]
        
        if request_path == "/" or request_path == "":
            await self._serve_source_table(writer)
            return

        mountpoint = request_path.lstrip("/")
        headers = await self._parse_headers(reader)
        
        await self._authenticate_and_connect_client(reader, writer, mountpoint, headers, real_ip)

    async def _serve_source_table(self, writer: asyncio.StreamWriter) -> None:
        source_table = self.get_source_table_data()
        now_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        header = (f"SOURCETABLE 200 OK\r\n"
                  f"Server: NtripCaster/Py/0.1\r\n"
                  f"Date: {now_str}\r\n"
                  f"Content-Type: text/plain\r\n"
                  f"Content-Length: {len(source_table)}\r\n"
                  f"Connection: close\r\n\r\n")
        
        writer.write(header.encode("utf-8") + source_table)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _parse_headers(self, reader: asyncio.StreamReader) -> dict[str, str]:
        headers = {}
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            line_str = line.decode("utf-8", errors="replace").strip()
            if ":" in line_str:
                key, val = line_str.split(":", 1)
                headers[key.lower()] = val.strip()
        return headers

    async def _authenticate_and_connect_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                             mountpoint: str, headers: dict[str, str], real_ip: str) -> None:
        username = ""
        auth_header = headers.get("authorization", "")
        
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                if ":" in decoded:
                    username, _ = decoded.split(":", 1)
            except Exception:
                pass # Username remains empty
                
        if not auth_header or not self.authenticate_client(auth_header, mountpoint):
            self.logger.warning(f"client auth failed: {real_ip} mountpoint={mountpoint}")
            await self._send_error(writer, b'HTTP/1.0 401 Unauthorized\r\nWWW-Authenticate: Basic realm="NTRIP"\r\n\r\n')
            return

        agent = Agent(reader, writer, mountpoint, "client", real_ip, username=username)
        agent.set_caster(self)
        self.clients[mountpoint].append(agent)
        
        writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\n\r\n")
        await writer.drain()
        await self.handle_client_conn(agent)

    async def _send_error(self, writer: asyncio.StreamWriter, message: bytes) -> None:
        writer.write(message)
        await writer.drain()
        writer.close()

    async def start_server(self) -> None:
        try:
            redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
            redis_password = os.getenv("REDIS_PASSWORD", "")
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:6379"
            else:
                redis_url = f"redis://{redis_host}:6379"

            try:
                self.redis = Redis.from_url(redis_url, decode_responses=True)
                await self.redis.ping()
                self.logger.info(f"Connected to Redis at {redis_host}:6379")
            except Exception as e:
                tb = traceback.format_exc()
                for handler in self.logger.handlers + self.logger.parent.handlers:
                    if hasattr(handler, 'baseFilename'):
                        handler.emit(self.logger.makeRecord(
                            self.logger.name, 40, __file__, 0,
                            f"Failed to connect to Redis at {redis_host}:6379: {e}\n{tb}",
                            (), None,
                        ))
                        break
                print(f"\n[ntrx] Redis server not found at {redis_host}:6379")
                print("[ntrx] The caster will run in degraded mode (no live state, no control channel).")
                if os.path.exists(self.fs.docker_compose_file):
                    print("[ntrx] docker-compose.yml detected — try: docker-compose up -d")
                else:
                    print("[ntrx] Install and start Redis, or provide a docker-compose.yml in the project root.")
                print()
                self.redis = None

            listen_addr = self.config.get("listen_addr", "0.0.0.0")
            listen_port = self.config.get("listen_port", 2101)

            server = await asyncio.start_server(self.handle_connection, listen_addr, listen_port)
            addr = server.sockets[0].getsockname()
            self.logger.info(f"NTRIP caster listening on {addr}")

            # Start Redis Control Listener
            asyncio.create_task(self.start_control_listener())

            await self.publish_state()
            async with server:
                await server.serve_forever()
        except Exception as e:
            self.logger.error(f"server error: {e}")
            raise
        finally:
            if self.redis:
                await self.redis.close()
