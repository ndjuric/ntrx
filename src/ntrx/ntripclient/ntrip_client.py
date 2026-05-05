import asyncio
import base64
import time
import threading
from typing import Protocol, Optional

import serial
from pyubx2 import UBXReader
import pyrtcm

from ntrx.logger.logger_setup import LoggerSetup
from ntrx.ntripclient.config import NtripClientConfig

class NtripClientProtocol(Protocol):
    async def run(self) -> None:
        ...

class NtripClient:
    logger = LoggerSetup.get_logger(__qualname__)

    def __init__(self, config: NtripClientConfig):
        self.config = config
        self.sync_serial: Optional[serial.Serial] = None
        
        self.latest_gga: Optional[str] = None
        self.last_fix_quality: int = -1
        self.last_gga_log_time: float = 0.0
        
        self._loop = asyncio.get_event_loop()
        self._stop_event = threading.Event()

    async def connect_serial(self) -> None:
        self.logger.info(f"[NTRIP CLIENT] Opening serial port {self.config.serial_port} @ {self.config.baudrate} bps...")
        try:
            # We use blocking serial for reliable UBX framing in a background thread
            self.sync_serial = serial.Serial(self.config.serial_port, self.config.baudrate, timeout=0.5)
        except Exception as e:
            self.logger.error(f"[NTRIP CLIENT] Failed to open serial port: {e}")
            raise
            
        # Start the background decoding thread
        threading.Thread(target=self._serial_decoder_thread, daemon=True).start()

    def _generate_dummy_gga(self, lat, lon, fix, sats, alt) -> str:
        """Generates a minimal GGA string if the F9P only outputs UBX NAV-PVT."""
        abs_lat = abs(lat)
        lat_d = int(abs_lat)
        lat_m = (abs_lat - lat_d) * 60.0
        lat_str = f"{lat_d:02d}{lat_m:07.4f}"
        ns = 'N' if lat >= 0 else 'S'
        
        abs_lon = abs(lon)
        lon_d = int(abs_lon)
        lon_m = (abs_lon - lon_d) * 60.0
        lon_str = f"{lon_d:03d}{lon_m:07.4f}"
        ew = 'E' if lon >= 0 else 'W'
        
        utc = time.strftime("%H%M%S.00", time.gmtime())
        gga = f"GPGGA,{utc},{lat_str},{ns},{lon_str},{ew},{fix},{sats:02d},1.0,{alt:.1f},M,0.0,M,,"
        
        chk = 0
        for char in gga:
            chk ^= ord(char)
        return f"${gga}*{chk:02X}\r\n"

    def _serial_decoder_thread(self):
        """Continuously reads and decodes ALL protocols (NMEA, UBX, RTCM3) from the antenna."""
        self.logger.info("[SERIAL DECODER] Thread started. Listening for NMEA, UBX, and RTCM3 from F9P...")
        ubr = UBXReader(self.sync_serial, protfilter=7) # 1=NMEA, 2=UBX, 4=RTCM3
        
        try:
            for raw_data, parsed_data in ubr:
                if self._stop_event.is_set():
                    break
                    
                if parsed_data:
                    # Safely hand off to the asyncio event loop for logging & state management
                    self._loop.call_soon_threadsafe(self._handle_antenna_message, parsed_data)
        except Exception as e:
            if not self._stop_event.is_set():
                self.logger.error(f"[SERIAL DECODER] Thread closed or error: {e}")

    def _handle_antenna_message(self, msg):
        """Processes a fully decoded message from the F9P Antenna."""
        now = time.time()
        fix = -1
        lat, lon, alt, sats = 0.0, 0.0, 0.0, 0
        is_valid_pos = False
        msg_identity = getattr(msg, 'identity', 'Unknown')
        
        # Parse NMEA GGA
        if msg_identity == 'GGA':
            fix = getattr(msg, 'quality', 0)
            lat = getattr(msg, 'lat', 0.0)
            lon = getattr(msg, 'lon', 0.0)
            alt = getattr(msg, 'alt', 0.0)
            sats = getattr(msg, 'numSV', 0)
            is_valid_pos = bool(lat and lon)
            if is_valid_pos:
                try:
                    self.latest_gga = msg.serialize().decode('ascii').strip() + "\r\n"
                except:
                    pass
                    
        # Parse UBX NAV-PVT
        elif msg_identity == 'NAV-PVT':
            fix_type = getattr(msg, 'fixType', 0)
            carr_soln = getattr(msg, 'carrSoln', 0) # 0=None, 1=Float, 2=Fix
            
            if carr_soln == 2: fix = 4
            elif carr_soln == 1: fix = 5
            elif fix_type == 3: fix = 1
            else: fix = 0
            
            lat = getattr(msg, 'lat', 0.0)
            lon = getattr(msg, 'lon', 0.0)
            alt = getattr(msg, 'hMSL', 0) / 1000.0
            sats = getattr(msg, 'numSV', 0)
            is_valid_pos = (lat != 0.0 and lon != 0.0)
            
            if is_valid_pos:
                self.latest_gga = self._generate_dummy_gga(lat, lon, fix, sats, alt)
                
        # Log periodically or on state change (only for positioning messages)
        if msg_identity in ('GGA', 'NAV-PVT'):
            status_changed = (fix != self.last_fix_quality)
            if status_changed or (now - self.last_gga_log_time >= 5):
                if fix == 4: status_str = "RTK FIX (cm-level precision)"
                elif fix == 5: status_str = "RTK FLOAT (sub-meter precision)"
                elif fix == 1: status_str = "3D FIX (meter-level, no corrections)"
                elif fix == 2: status_str = "DGPS (sub-meter)"
                else: status_str = f"NO FIX (Searching...)"
                
                if is_valid_pos:
                    coord_str = f"{abs(lat):.6f}° {'N' if lat>=0 else 'S'}, {abs(lon):.6f}° {'E' if lon>=0 else 'W'}"
                else:
                    coord_str = "Unknown"
                
                self.logger.info(
                    f"[ANTENNA STATE] {status_str} | "
                    f"Satellites: {sats} | Coords: {coord_str} | Alt: {alt:.1f}m | "
                    f"Decoded from: {msg_identity}"
                )
                
                self.last_fix_quality = fix
                self.last_gga_log_time = now

    async def _send_gga_loop(self, writer: asyncio.StreamWriter) -> None:
        """Sends Keep-Alive / VRS position to the NTRIP Caster."""
        last_sent = 0.0
        while True:
            try:
                now = time.time()
                if self.latest_gga and (now - last_sent >= 10):
                    writer.write(self.latest_gga.encode('ascii'))
                    await writer.drain()
                    
                    self.logger.info(f"[ANTENNA -> CASTER] TX Keep-Alive | Message: {self.latest_gga.strip()}")
                    last_sent = now
            except Exception as e:
                self.logger.error(f"[NTRIP TX] Error sending Keep-Alive: {e}")
            
            await asyncio.sleep(1)

    def _peek_rtcm_identities(self, chunk: bytes) -> str:
        """Attempts to decode RTCM3 chunks to identify message types (e.g. 1005, 1074)."""
        identities = set()
        idx = 0
        while idx < len(chunk):
            start = chunk.find(b'\xd3', idx)
            if start == -1: break
            # We need at least 5 bytes to read the message type (Sync, Length[2], Type[2])
            if start + 4 < len(chunk):
                # Type is 12 bits across byte 3 and 4
                msg_id = (chunk[start+3] << 4) | (chunk[start+4] >> 4)
                identities.add(str(msg_id))
                
                # Try to skip the message length to find the next one faster
                length = ((chunk[start+1] & 0x03) << 8) | chunk[start+2]
                idx = start + length + 6 # +3 for header, +3 for CRC
            else:
                idx = start + 1
        return ", ".join(identities) if identities else ""

    def _build_auth_request(self) -> bytes:
        auth_str = f"{self.config.username}:{self.config.password}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        return (
            f"GET /{self.config.mountpoint} HTTP/1.0\r\n"
            f"User-Agent: {self.config.user_agent}\r\n"
            f"Authorization: Basic {auth_b64}\r\n\r\n"
        ).encode()

    async def ntrip_rx_to_serial_tx(self) -> None:
        """Pulls RTCM3 from NTRIP caster and pushes it directly to F9P."""
        request = self._build_auth_request()

        while True:
            send_task = None
            try:
                self.logger.info(f"[NTRIP CLIENT] Connecting to Caster at {self.config.caster_host}:{self.config.caster_port}...")
                reader, writer = await asyncio.open_connection(self.config.caster_host, self.config.caster_port)
                
                writer.write(request)
                await writer.drain()

                # Ignore HTTP headers
                while True:
                    line = await reader.readline()
                    if line == b'\r\n' or not line:
                        break
                
                self.logger.info("[NTRIP CLIENT] Connection successful. Waiting for incoming RTCM3 stream...")
                
                if not self.sync_serial:
                    break
                
                send_task = asyncio.create_task(self._send_gga_loop(writer))
                    
                msgs_received = 0
                last_log_time = time.time()
                last_identities = set()

                while True:
                    chunk = await reader.read(1024)
                    if not chunk:
                        self.logger.warning("[NTRIP CLIENT] EOF from caster. Connection dropped.")
                        break
                    
                    # Peek into the chunk to see what RTCM messages the caster sent us
                    ids = self._peek_rtcm_identities(chunk)
                    if ids:
                        for i in ids.split(", "): last_identities.add(i)
                    
                    # Safely write the RTCM chunk to the serial port
                    if self.sync_serial and not self._stop_event.is_set():
                        await asyncio.to_thread(self.sync_serial.write, chunk)

                    msgs_received += 1
                    now = time.time()
                    if now - last_log_time >= 5:
                        id_str = ", ".join(sorted(last_identities)) if last_identities else "Unknown RTCM3"
                        if msgs_received == 1:
                            self.logger.info(f"[CASTER -> ANTENNA] RX 1 Chunk | Decoded Types: [{id_str}]")
                        elif msgs_received > 1:
                            self.logger.info(f"[CASTER -> ANTENNA] RX {msgs_received} Chunks | Decoded Types: [{id_str}]")
                        
                        msgs_received = 0
                        last_identities.clear()
                        last_log_time = now

            except asyncio.CancelledError:
                self.logger.info("[NTRIP CLIENT] Caster task cancelled.")
                if send_task: send_task.cancel()
                break
            except Exception as e:
                self.logger.error(f"[NTRIP CLIENT] Network exception: {e}. Pausing {self.config.reconnect_delay}s...")
                await asyncio.sleep(self.config.reconnect_delay)
            finally:
                if send_task and not send_task.done():
                    send_task.cancel()

    async def run(self) -> None:
        try:
            await self.connect_serial()
        except Exception:
            return

        try:
            await self.ntrip_rx_to_serial_tx()
        except asyncio.CancelledError:
            self.logger.info("[NTRIP CLIENT] Shutdown requested.")
        finally:
            self._stop_event.set()
            if self.sync_serial:
                self.sync_serial.close()
