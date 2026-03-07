#!/usr/bin/env python
from __future__ import annotations
import asyncio
from typing import Optional
import time
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.models.agent_data import AgentData


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

    def to_data(self) -> AgentData:
        return AgentData(
            mountpoint=self.mountpoint,
            real_ip=self.real_ip,
            user_agent="Unknown", # Agent class doesn't track this yet, could add
            connected_at=self.last_activity, # Using last_activity as proxy or add connected_time
            bytes_in=self.in_bytes,
            bytes_out=self.out_bytes,
            bps_in=self.in_bps,
            bps_out=self.out_bps,
            username=self.username
        )