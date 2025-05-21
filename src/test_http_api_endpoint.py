#!/usr/bin/env python
import requests
import argparse
import signal
import sys

class HttpClient:
    def __init__(self, host="0.0.0.0", port=8000):
        self.base_url = f"http://{host}:{port}"

    def get_state(self):
        response = requests.get(f"{self.base_url}/state")
        if response.status_code == 200:
            print(response.json())
        else:
            print(f"Failed to get state: {response.status_code}")

def signal_handler(sig, frame):
    print("Exiting...")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    parser = argparse.ArgumentParser(description="HTTP Client for NTRIP Caster")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host of the FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port of the FastAPI server")
    args = parser.parse_args()

    client = HttpClient(host=args.host, port=args.port)
    client.get_state()

if __name__ == "__main__":
    main()