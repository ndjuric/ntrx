#!/usr/bin/env python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from contextlib import asynccontextmanager
import asyncio
import json
import os
import uvicorn
from redis.asyncio import Redis

from ntrx.vfs.fs import FS
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.models.caster_state import CasterState
from ntrx.models.control import ControlCommand


class FastAPIServer:
    def __init__(self):
        self.fs = FS()
        self.logger = LoggerSetup.get_logger(__name__)
        self.redis: Redis | None = None
        self.app = FastAPI(lifespan=self.lifespan)
        self.setup_routes()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        # ... (keep existing)
        redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
        redis_password = os.getenv("REDIS_PASSWORD", "")
        if redis_password:
            redis_url = f"redis://:{redis_password}@{redis_host}:6379"
        else:
            redis_url = f"redis://{redis_host}:6379"

        try:
            self.redis = Redis.from_url(redis_url, decode_responses=True)
            app.state.redis_client = self.redis
            yield
        finally:
            if self.redis:
                await self.redis.close()

    def setup_routes(self) -> None:
        @self.app.get("/state", response_model=CasterState)
        async def get_state():
            try:
                state_json = await self.app.state.redis_client.get('ntripcaster_state')
                if state_json:
                    # Validate and return object
                    return CasterState.model_validate_json(state_json)
                raise HTTPException(status_code=404, detail="State not available")
            except Exception as e:
                self.logger.error(f"GET /state error: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.post("/api/kill/{username}")
        async def kill_user(username: str):
            try:
                if not self.app.state.redis_client:
                    raise HTTPException(status_code=503, detail="Redis unavailable")
                
                cmd = ControlCommand(action="kill", username=username)
                await self.app.state.redis_client.publish("ntrip:control", cmd.model_dump_json())
                return {"status": "ok", "message": f"Kill signal sent for {username}"}
            except Exception as e:
                self.logger.error(f"Kill API error: {e}")
                raise HTTPException(status_code=500, detail="Internal Error")

# ... (keep debug/routes if useful, but maybe remove print)

    def run(self) -> None:
        try:
            uvicorn.run(self.app, host="0.0.0.0", port=8000)
        except Exception as e:
            self.logger.error(f"Uvicorn run failed: {e}")


if __name__ == "__main__":
    server = FastAPIServer()
    server.run()
