# NTRIP Client Terminal User Interface (TUI) Suggestion

## Overview
A textual interface (TUI) for the NTRIP Client using `textual` or `urwid` (Python TUI libraries) that provides real-time monitoring of RTCM injection, NMEA metrics, and Fix statuses.

## Layout Options

### Option 1: Split-Pane Monitoring Dashboard
A classic split-terminal layout that shows communication happening in real-time.

```
+-------------------------------------------------------------+
| NTRX Client - Connected to [127.0.0.1:2101 / TESTMOUNT]     |
| Serial: /dev/ttyACM0 @ 115200 bps                           |
+-------------------------------------------------------------+
| [SENT - GGA (Every 5-10s)]                                  |
| 10:45:01 -> $GPGGA,104501.00,4448.2345,N,02028.1234,E,1...  |
| 10:45:11 -> $GPGGA,104511.00,4448.2346,N,02028.1235,E,1...  |
|                                                             |
+-------------------------------------------------------------+
| [RECEIVED - RTCM Corrections (~1-5 msgs/sec)]               |
| 10:45:12 <- RTCM3 Chunk Received (142 bytes)                |
|          <- [... 3 other messages received ...]             |
| 10:45:13 <- RTCM3 Chunk Received (89 bytes)                 |
|                                                             |
+-------------------------------------------------------------+
| [STATUS / FIX INFO]                                         |
| Current Status: RTK FIX (4)                                 |
| Satellites: 12                                              |
| Raw Coord:  4448.2345 N, 02028.1234 E                       |
| Fixed Coord: 44.803908° N, 20.468723° E                     |
+-------------------------------------------------------------+
| (y) Yank Fixed Coord | (c) Yank Raw Coord | (q) Quit        |
+-------------------------------------------------------------+
```

### Features
1. **Send Log (GGA Messages)**:
   - Displays NMEA strings sent *to* the NTRIP Caster (usually GGA).
   - Frequency: Typically once every 5 to 10 seconds.
   - Purpose: Keep-alive for the caster, and tells the caster where the rover is so it can provide localized corrections (VRS - Virtual Reference Station).

2. **Receive Log (RTCM Corrections)**:
   - Displays chunks of binary data received from the caster.
   - Frequency: Very frequent (usually 1 to 10 chunks per second).
   - Display optimization: Log 1 message, summarize the others (e.g., `<- [... 4 other messages received ...]`) to avoid overwhelming the screen.

3. **Status & Coordinate Decoders**:
   - Parses the incoming GGA from the serial port.
   - Displays the GPS Fix Quality:
     - `0`: Invalid
     - `1`: GPS fix (SPS)
     - `2`: DGPS fix
     - `3`: PPS fix
     - `4`: Real Time Kinematic (RTK Fix) -> **Highly Accurate (cm-level)**
     - `5`: Float RTK -> **Decent, but ambiguities not fully resolved (sub-meter level)**
     - `6`: Estimated (dead reckoning)
   - Decodes DDMM.MMMMM into Decimal Degrees (DD.DDDDD) for easy Google Maps usage.

4. **Interactive Keybinds**:
   - `y` - Copy fixed coordinates (Decimal Degrees) to clipboard.
   - `c` - Copy raw NMEA string to clipboard.
   - `Tab` - Switch focus between Send Log, Receive Log, and Status Panels.
   - `q` or `Ctrl+C` - Quit application safely.

## Recommended Libraries
- `Textual`: For modern, CSS-styled, async-native terminal interfaces (Highly recommended).
- `pyperclip`: For cross-platform clipboard support (copying coordinates).
- `pynmea2`: For safely parsing and decoding NMEA strings.

## RTCM3 Message Reference
Based on real network tests, the following RTCM3 messages are typically broadcast by the caster:
- `1006` (every 30s): Base station ARP (Antenna Reference Point) with antenna height.
- `1008` (every 30s): Antenna Descriptor and Serial Number.
- `1019`: GPS Ephemerides.
- `1020`: GLONASS Ephemerides.
- `1077` (every 1s): GPS MSM7 (Multiple Signal Messages) - High precision observables.
- `1087` (every 1s): GLONASS MSM7.
- `1097` (every 1s): Galileo MSM7.
- `1107` (every 1s): SBAS MSM7 (on future base stations).
- `1127` (every 1s): BeiDou MSM7.
- `1230` (every 60s): GLONASS L1/L2 Code-Phase Biases.
