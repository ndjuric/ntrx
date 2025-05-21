#!/usr/bin/env python
import asyncio
import websockets
import argparse
import signal
import sys

class WebSocketClient:
    def __init__(self, host="0.0.0.0", port=8000):
        self.uri = f"ws://{host}:{port}/ws"
        self.websocket = None

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)

    async def get_state(self):
        try:
            await self.connect()
            while True:
                state = await self.websocket.recv()
                print(state)
        except websockets.ConnectionClosed:
            print("Connection closed")
        except asyncio.CancelledError:
            print("Cancelled")
        finally:
            await self.websocket.close()

def signal_handler(sig, frame, loop):
    print("Exiting...")
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.stop()

def main():
    parser = argparse.ArgumentParser(description="WebSocket Client for NTRIP Caster")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host of the FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port of the FastAPI server")
    args = parser.parse_args()

    client = WebSocketClient(host=args.host, port=args.port)
    loop = asyncio.get_event_loop()
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, loop))
    try:
        loop.run_until_complete(client.get_state())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.close()

if __name__ == "__main__":
    main()