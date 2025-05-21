#!/usr/bin/env python
from __future__ import annotations
import os
import sys
import time
import json
import base64
import signal
import asyncio
from collections import defaultdict
from typing import Optional
from redis.asyncio import Redis

from ntrx.vfs.fs import FS
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.ntrip.agent import Agent


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
                await self.redis.set('ntripcaster_state', json.dumps(state))
            except Exception as e:
                self.logger.error(f"Failed to publish state to Redis: {e}")

    def get_state(self) -> dict:
        return {
            "sources": {m: a.to_dict() for m, a in self.sources.items()},
            "clients": {m: [a.to_dict() for a in lst] for m, lst in self.clients.items()}
        }

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

    async def handle_client_conn(self, agent: Agent) -> None:
        agent.set_caster(self)
        self.logger.info(f"client connected: {agent.mountpoint} from {agent.real_ip}")

        try:
            while True:
                data = await agent.reader.read(1024)
                if not data:
                    break
                agent.in_bytes += len(data)
                agent.in_bps = len(data) * 8
                await agent.update_activity()
                if agent.mountpoint in self.sources:
                    source = self.sources[agent.mountpoint]
                    source.writer.write(data)
                    await source.writer.drain()
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
                    self.logger.warning(f"source auth failed: {real_ip} mountpoint={mountpoint}")
                    return
                agent = Agent(reader, writer, mountpoint, "source", real_ip)
                agent.set_caster(self)
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
                    writer.write(b'HTTP/1.0 401 Unauthorized\r\nWWW-Authenticate: Basic realm="NTRIP"\r\n\r\n')
                    await writer.drain()
                    writer.close()
                    self.logger.warning(f"client auth failed: {real_ip} mountpoint={mountpoint}")
                    return
                agent = Agent(reader, writer, mountpoint, "client", real_ip)
                agent.set_caster(self)
                self.clients[mountpoint].append(agent)
                writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\n\r\n")
                await writer.drain()
                await self.handle_client_conn(agent)
            else:
                writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
        except Exception as e:
            self.logger.error(f"connection error from {real_ip}: {e}")
            writer.close()

    async def start_server(self) -> None:
        try:
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
            self.logger.info(f"NTRIP caster listening on {addr}")

            await self.publish_state()
            async with server:
                await server.serve_forever()
        except Exception as e:
            self.logger.error(f"server error: {e}")
            raise
        finally:
            if self.redis:
                await self.redis.close()
