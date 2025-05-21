#!/usr/bin/env python
import socket
import base64
from pyrtcm import RTCMReader
import argparse
import logging

class NtripClient:
    def __init__(self, host="93.87.41.86", port=2101, user="pygimel",
                 password="pygimel", mount_point="/proba", log_level=logging.INFO):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.mount_point = mount_point
        self._setup_logging(log_level)
        self.sock = None  # Initialize socket attribute

    def _setup_logging(self, level):
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    def _create_ntrip_request(self):
        auth_string = base64.b64encode(
            f"{self.user}:{self.password}".encode()).decode()
        ntrip_request = (
            f"GET {self.mount_point} HTTP/1.0\r\n"
            f"User-Agent: NTRIP pyrtcm\r\n"
            f"Authorization: Basic {auth_string}\r\n"
            f"\r\n"
        )
        return ntrip_request

    def _connect_to_caster(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logging.info(f"Connected to NTRIP caster at {self.host}:{self.port}")
        except socket.error as e:
            logging.error(f"Error connecting to NTRIP caster: {e}")
            raise

    def _send_ntrip_request(self):
        try:
            ntrip_request = self._create_ntrip_request()
            self.sock.sendall(ntrip_request.encode())
            logging.debug(f"NTRIP request sent: {ntrip_request}")
        except socket.error as e:
            logging.error(f"Error sending NTRIP request: {e}")
            raise

    def _send_initial_gga(self):
        try:
            gga_sentence = "$GPGGA,185204.160,4535.936,N,02033.319,E,1,12,1.0,0.0,M,0.0,M,,*61\r\n"
            self.sock.sendall(gga_sentence.encode())
            logging.debug(f"Initial NMEA GGA message sent: {gga_sentence}")
        except socket.error as e:
            logging.error(f"Error sending initial NMEA GGA message: {e}")
            raise

    def decode_rtcm_stream(self):
        try:
            self._connect_to_caster()
            self._send_ntrip_request()
            self._send_initial_gga()

            reader = RTCMReader(self.sock)
            while True:
                raw_data, parsed_data = reader.read()
                if parsed_data:
                    print(parsed_data)  # Or process the parsed data as needed
                    logging.debug(f"Decoded RTCM message: {parsed_data}")

        except Exception as e:
            logging.error(f"An error occurred: {e}")
        finally:
            if self.sock:
                self.sock.close()
                logging.info("Connection to NTRIP caster closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Connect to an NTRIP caster and decode RTCM data.")
    parser.add_argument("--host", type=str, default="93.87.41.86",
                        help="NTRIP caster hostname or IP address (default: 93.87.41.86)")
    parser.add_argument("--port", type=int, default=2101,
                        help="NTRIP caster port number (default: 2101)")
    parser.add_argument("--user", type=str, default="pygimel",
                        help="NTRIP caster username (default: pygimel)")
    parser.add_argument("--password", type=str, default="pygimel",
                        help="NTRIP caster password (default: pygimel)")
    parser.add_argument("--mount_point", type=str, default="/proba",
                        help="NTRIP caster mount point (default: /proba)")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level (default: INFO)")

    args = parser.parse_args()

    # Convert log level string to logging level constant
    log_level = getattr(logging, args.log_level.upper())

    client = NtripClient(host=args.host, port=args.port, user=args.user,
                         password=args.password, mount_point=args.mount_point,
                         log_level=log_level)
    client.decode_rtcm_stream()