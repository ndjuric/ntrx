#!/usr/bin/env python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import asyncio
import json
import os
import uvicorn
from redis.asyncio import Redis

from ntrx.vfs.fs import FS
from ntrx.logger.logger_setup import LoggerSetup


class FastAPIServer:
    def __init__(self):
        self.fs = FS()
        self.logger = LoggerSetup.get_logger(__name__)
        self.redis: Redis | None = None
        self.app = FastAPI(lifespan=self.lifespan)
        self.setup_routes()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
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
        @self.app.get("/state")
        async def get_state():
            try:
                state = await self.app.state.redis_client.get('ntripcaster_state')
                if state:
                    return json.loads(state)
                return {"error": "State not available"}
            except Exception as e:
                self.logger.error(f"GET /state error: {e}")
                return {"error": "Internal server error"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    state = await self.app.state.redis_client.get('ntripcaster_state')
                    if state:
                        await websocket.send_text(json.dumps(json.loads(state), indent=4))
                    await asyncio.sleep(1)
            except WebSocketDisconnect:
                self.logger.info("WebSocket client disconnected")
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")

    def run(self) -> None:
        try:
            uvicorn.run(self.app, host="0.0.0.0", port=8000)
        except Exception as e:
            self.logger.error(f"Uvicorn run failed: {e}")


if __name__ == "__main__":
    server = FastAPIServer()
    server.run()
