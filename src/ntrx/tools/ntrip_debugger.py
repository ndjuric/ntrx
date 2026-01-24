#!/usr/bin/env python
import socket
import base64
import argparse
import logging
import sys
from typing import Optional
from pyrtcm import RTCMReader, RTCMMessage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NtripDebugClient")

class NtripDebugClient:
    """
    A simple NTRIP client for debugging. 
    Connects to a caster, sends GPGGA, and decodes incoming RTCM stream.
    """
    def __init__(self, host: str, port: int, user: str, password: str, mountpoint: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.mountpoint = mountpoint
        self.sock: Optional[socket.socket] = None

    def connect(self) -> None:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            sys.exit(1)

    def send_request(self) -> None:
        if not self.sock:
            return
            
        auth_str = f"{self.user}:{self.password}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        
        req = (
            f"GET {self.mountpoint} HTTP/1.0\r\n"
            f"User-Agent: NTRX-Debugger/1.0\r\n"
            f"Authorization: Basic {auth_b64}\r\n"
            f"\r\n"
        )
        self.sock.sendall(req.encode())
        logger.info("Sent NTRIP GET request")

    def send_nmea(self) -> None:
        if not self.sock:
            return
        # Example position (Belgrade)
        nmea = "$GPGGA,120000.00,4448.000,N,02028.000,E,1,08,1.0,100.0,M,0.0,M,,*XX\r\n"
        self.sock.sendall(nmea.encode())
        logger.info(f"Sent initial NMEA: {nmea.strip()}")

    def run(self) -> None:
        self.connect()
        self.send_request()
        self.send_nmea()
        
        try:
            reader = RTCMReader(self.sock)
            logger.info("Listening for RTCM data...")
            while True:
                # pyrtcm read return (raw, parsed)
                # handle potential errors if stream is not RTCM
                try:
                    raw_data, parsed_data = reader.read()
                    if parsed_data:
                        logger.info(f"[RTCM] {parsed_data.identity} ({parsed_data.payload})")
                    else:
                        # Could be HTTP headers or non-RTCM trash
                        pass
                except Exception:
                    # RTCMReader might raise on garbage
                    pass
        except KeyboardInterrupt:
            logger.info("Stopping...")
        except Exception as e:
            logger.error(f"Stream error: {e}")
        finally:
            if self.sock:
                self.sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NTRIP Stream Debugger")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2101)
    parser.add_argument("--user", default="test3")
    parser.add_argument("--password", default="test3")
    parser.add_argument("--mountpoint", default="/TESTMOUNT")
    args = parser.parse_args()

    client = NtripDebugClient(args.host, args.port, args.user, args.password, args.mountpoint)
    client.run()
