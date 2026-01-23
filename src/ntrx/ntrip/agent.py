#!/usr/bin/env python
from __future__ import annotations
import asyncio
from typing import Optional
import time
from ntrx.logger.logger_setup import LoggerSetup


class Agent:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 mountpoint: str, agent_type: str, real_ip: Optional[str] = None, username: Optional[str] = None):
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
        self.username = username
        self._caster = None
        self.logger = LoggerSetup.get_logger(__name__)

    def set_caster(self, caster: 'NtripCaster') -> None: # type: ignore[name-defined]
        self._caster = caster

    async def update_activity(self) -> None:
        self.last_activity = time.time()
        if self._caster:
            try:
                await self._caster.publish_state()
            except Exception as e:
                self.logger.error(f"Failed to publish state update: {e}")

    def to_dict(self) -> dict:
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