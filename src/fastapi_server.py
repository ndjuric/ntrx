#!/usr/bin/env python
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import asyncio
from redis.asyncio import Redis
import json
import os
import logging
from config import *

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retrieve configuration from environment variables.
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_password = os.getenv("REDIS_PASSWORD", "")
    if redis_password:
        redis_url = f"redis://:{redis_password}@{redis_host}:6379"
    else:
        redis_url = f"redis://{redis_host}:6379"
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    app.state.redis_client = redis_client
    yield
    if app.state.redis_client:
        await app.state.redis_client.close()

class FastAPIServer:
    def __init__(self):
        self.app = FastAPI(lifespan=lifespan)
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/state")
        async def get_state():
            state = await self.app.state.redis_client.get('ntripcaster_state')
            if state:
                return json.loads(state)
            return {"error": "State not available"}

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
                logging.info("WebSocket client disconnected")
            except Exception as e:
                logging.error(f"WebSocket error: {e}")

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    fastapi_server = FastAPIServer()
    fastapi_server.run()