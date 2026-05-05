import asyncio
import base64
import serial_asyncio
from typing import Protocol, Optional
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.ntripclient.config import NtripClientConfig

class NtripClientProtocol(Protocol):
    async def run(self) -> None:
        ...

class NtripClient:
    logger = LoggerSetup.get_logger(__qualname__)

    def __init__(self, config: NtripClientConfig):
        self.config = config
        self.serial_reader: Optional[asyncio.StreamReader] = None
        self.serial_writer: Optional[asyncio.StreamWriter] = None

    async def connect_serial(self) -> None:
        """Opens asynchronous stream to the ZED-F9P module."""
        self.logger.info(f"[{self.config.serial_port}] Initializing connection to F9P...")
        try:
            self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                url=self.config.serial_port,
                baudrate=self.config.baudrate
            )
        except Exception as e:
            self.logger.error(f"Failed to connect to serial port {self.config.serial_port}: {e}")
            raise

    def _build_auth_request(self) -> bytes:
        auth_str = f"{self.config.username}:{self.config.password}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        request = (
            f"GET /{self.config.mountpoint} HTTP/1.0\r\n"
            f"User-Agent: {self.config.user_agent}\r\n"
            f"Authorization: Basic {auth_b64}\r\n\r\n"
        )
        return request.encode()

    async def ntrip_rx_to_serial_tx(self) -> None:
        """Pulls RTCM3 from NTRIP caster and pushes it directly to F9P."""
        request = self._build_auth_request()

        while True:
            try:
                self.logger.info(f"[NTRIP] Connecting to caster {self.config.caster_host}:{self.config.caster_port}...")
                reader, writer = await asyncio.open_connection(self.config.caster_host, self.config.caster_port)
                
                writer.write(request)
                await writer.drain()

                # Ignore HTTP headers
                while True:
                    line = await reader.readline()
                    if line == b'\r\n' or not line:
                        break
                
                self.logger.info("[NTRIP] Connection successful. Injecting RTCM3 into F9P...")
                
                if not self.serial_writer:
                    self.logger.error("Serial writer is not initialized.")
                    break
                    
                while True:
                    chunk = await reader.read(1024)
                    if not chunk:
                        self.logger.warning("[NTRIP] EOF from caster. Reconnecting...")
                        break
                    
                    # Passthrough to module processor
                    self.serial_writer.write(chunk)
                    await self.serial_writer.drain()
            except asyncio.CancelledError:
                self.logger.info("NTRIP task cancelled.")
                break
            except Exception as e:
                self.logger.error(f"[NTRIP] Network exception: {e}. Pausing {self.config.reconnect_delay}s...")
                await asyncio.sleep(self.config.reconnect_delay)

    async def serial_rx_to_app(self) -> None:
        """Reads NMEA solutions from F9P and filters RTK Fix."""
        if not self.serial_reader:
            self.logger.error("Serial reader is not initialized.")
            return

        while True:
            try:
                line = await self.serial_reader.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue

                nmea_str = line.decode('ascii', errors='replace').strip()
                if not (nmea_str.startswith('$GPGGA') or nmea_str.startswith('$GNGGA')):
                    continue
                
                parts = nmea_str.split(',')
                if len(parts) <= 6:
                    continue
                
                fix_quality = parts[6]
                if fix_quality == '4':
                    self.logger.info(f"[RTK FIX] Precision confirmed: {nmea_str}")
                elif fix_quality == '5':
                    self.logger.debug(f"[RTK FLOAT] Calculating ambiguity: {nmea_str}")
                elif fix_quality == '1':
                    self.logger.debug(f"[SPS] Standard GPS (no RTCM corrections): {nmea_str}")

            except asyncio.CancelledError:
                self.logger.info("Serial RX task cancelled.")
                break
            except Exception as e:
                self.logger.error(f"[SERIAL] I/O exception: {e}")
                await asyncio.sleep(1)

    async def run(self) -> None:
        try:
            await self.connect_serial()
        except Exception:
            return

        # Concurrent execution of network downlink and serial uplink
        try:
            await asyncio.gather(
                self.ntrip_rx_to_serial_tx(),
                self.serial_rx_to_app()
            )
        except asyncio.CancelledError:
            self.logger.info("Client run cancelled.")
