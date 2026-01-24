import sys
import socket
import time
import threading
import argparse
import redis
import json
import base64
import logging
from typing import Optional
from dataclasses import dataclass
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NtripIntegrationTest")

@dataclass
class TestConfig:
    host: str = "127.0.0.1"
    port: int = 2101
    api_url: str = "http://127.0.0.1:8000"
    redis_host: str = "127.0.0.1"
    redis_password: str = "changeme"
    source_user: str = "test"
    source_mount: str = "TESTMOUNT"
    client_user: str = "test3"
    client_password: str = "test3"

class NtripIntegrationTester:
    def __init__(self, config: TestConfig):
        self.config = config
        self.stop_event = threading.Event()
        self.source_thread: Optional[threading.Thread] = None
        self.client_thread: Optional[threading.Thread] = None

    def run_source(self) -> None:
        try:
            logger.info("Starting Fake Source...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.config.host, self.config.port))
                req = f"SOURCE {self.config.source_user} {self.config.source_mount}\r\nSource-Agent: NTRIPTester/1.0\r\n\r\n".encode()
                s.sendall(req)
                resp = s.recv(1024)
                logger.info(f"[Source] Connect Response: {resp.strip().decode(errors='replace')}")
                
                counter = 0
                while not self.stop_event.is_set():
                    data = f"DATA-PACKET-{counter}\r\n".encode()
                    s.sendall(data)
                    counter += 1
                    time.sleep(1.0)
        except Exception as e:
            logger.error(f"[Source] Error: {e}")

    def run_client(self) -> None:
        try:
            time.sleep(1) # Wait for source
            logger.info(f"Starting Fake Client as {self.config.client_user}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.config.host, self.config.port))
                
                auth_str = f"{self.config.client_user}:{self.config.client_password}"
                auth_b64 = base64.b64encode(auth_str.encode()).decode()
                
                req = (f"GET /{self.config.source_mount} HTTP/1.0\r\n"
                       f"User-Agent: NTRIPTester/1.0\r\n"
                       f"Authorization: Basic {auth_b64}\r\n\r\n").encode()
                s.sendall(req)
                
                # Consume headers
                self._read_headers(s)
                logger.info("[Client] Handshake complete. Sending NMEA data...")
                
                while not self.stop_event.is_set():
                    # Send realistic GPGGA
                    nmea = f"$GPGGA,123456.00,4400.000,N,02000.000,E,1,08,1.0,100.0,M,0.0,M,,*XX\r\n"
                    s.sendall(nmea.encode())
                    
                    # Read incoming stream (don't buffer too much)
                    try:
                        s.settimeout(0.5)
                        s.recv(1024)
                    except socket.timeout:
                        pass
                    
                    time.sleep(1.0)
        except Exception as e:
            logger.info(f"[Client] Disconnected: {e}")

    def _read_headers(self, sock: socket.socket) -> None:
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buffer += chunk

    def verify_redis_stream(self) -> bool:
        logger.info("[Test] Verifying Redis Map Data Stream...")
        try:
            r = redis.Redis(
                host=self.config.redis_host, 
                password=self.config.redis_password, 
                decode_responses=True
            )
            pubsub = r.pubsub()
            pubsub.subscribe("ntrip:positions")
            
            start_time = time.time()
            while time.time() - start_time < 10:
                msg = pubsub.get_message(ignore_subscribe_messages=True)
                if msg:
                    data = json.loads(msg["data"])
                    logger.info(f"[Redis] Received: {data}")
                    if data.get("username") == self.config.client_user:
                        logger.info("PASS: Valid position data received via Redis")
                        return True
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Redis Verification Failed: {e}")
        
        logger.error("FAIL: No valid position data received in 10s")
        return False

    def verify_api_kill(self) -> bool:
        logger.info(f"[Test] Testing API Kill Switch for {self.config.client_user}...")
        try:
            url = f"{self.config.api_url}/api/kill/{self.config.client_user}"
            resp = requests.post(url)
            logger.info(f"[API] Response: {resp.status_code} {resp.text}")
            
            if resp.status_code == 200:
                logger.info("PASS: API Kill command accepted")
                return True
        except Exception as e:
            logger.error(f"API Kill Request Failed: {e}")
        
        logger.error("FAIL: API Kill failed")
        return False

    def verify_disconnection(self) -> bool:
        time.sleep(2)
        if hasattr(self, 'client_thread') and self.client_thread and not self.client_thread.is_alive():
             logger.info("PASS: Client thread terminated (Socket Closed)")
             return True
        logger.error("FAIL: Client thread still alive")
        return False

    def run_suite(self):
        # 1. Start threads
        self.source_thread = threading.Thread(target=self.run_source)
        self.client_thread = threading.Thread(target=self.run_client)
        
        self.source_thread.start()
        self.client_thread.start()
        
        try:
            # 2. Verify Data Flow
            if self.verify_redis_stream():
                # 3. Verify Control
                if self.verify_api_kill():
                    # 4. Verify Disconnect
                    self.verify_disconnection()
        finally:
            self.stop_event.set()
            if self.source_thread: self.source_thread.join(timeout=1)
            if self.client_thread: self.client_thread.join(timeout=1)
            logger.info("=== Test Suite Complete ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    
    config = TestConfig(host=args.host)
    tester = NtripIntegrationTester(config)
    tester.run_suite()
