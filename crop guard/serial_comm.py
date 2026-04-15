"""
serial_comm.py — CropGuard USB Serial Communication Layer

Fixes in this version:
  #9  #10  Optional[X] instead of X | None  (Python 3.8/3.9 compat)
  #15  _connected guarded by _lock
  #16  PermissionError on port → back off 30 s, print once, stop log spam
  #17  CONNECT_RETRY bumped to 5 s for non-permission errors
"""

from __future__ import annotations

import json
import threading
import time
from typing import Optional

import serial
import serial.tools.list_ports

BAUD_RATE     = 921600
CONNECT_RETRY = 5.0          # seconds between normal reconnect attempts
PERM_RETRY    = 30.0         # seconds to wait after PermissionError
READ_TIMEOUT  = 0.02
SEND_TIMEOUT  = 0.5

# ── Sensor snapshot ───────────────────────────────────────────────
_sensor_data: dict = {
    'temperature':     25.0,
    'humidity':        60.0,
    'soil_percent':    50.0,
    'soil_moisture':   50.0,
    'distance_front':  200.0,
    'gps_lat':         7.208900,
    'gps_lng':         79.861244,
    'gps_sats':        0,
    'gps_valid':       False,
    'battery_percent': 100.0,
    'battery_voltage': 12.0,
}

_lock:         threading.Lock          = threading.Lock()
_ser:          Optional[serial.Serial] = None
_connected:    bool                    = False
_send_queue:   list                    = []
_send_lock:    threading.Lock          = threading.Lock()
_port_override: Optional[str]         = None


# ── Public API ────────────────────────────────────────────────────

def set_port(port: str) -> None:
    global _port_override
    _port_override = port


def is_connected() -> bool:
    with _lock:
        return _connected


def get_sensor_data() -> dict:
    with _lock:
        d = _sensor_data.copy()
        d['esp32_online'] = _connected
    return d


def update_soil(value: float) -> None:
    with _lock:
        _sensor_data['soil_percent']  = round(value, 1)
        _sensor_data['soil_moisture'] = round(value, 1)


def send_command(cmd_dict: dict) -> None:
    line = json.dumps(cmd_dict, separators=(',', ':'))
    with _send_lock:
        _send_queue.append(line)


# ── Convenience helpers ───────────────────────────────────────────

def motor(direction: str, speed: int = 180) -> None:
    send_command({"cmd": "motor", "dir": direction, "speed": speed})

def motor_stop() -> None:
    send_command({"cmd": "motor", "dir": "stop"})

def set_speed(speed_pct: int) -> None:
    pwm = int(max(0, min(100, speed_pct)) * 255 / 100)
    send_command({"cmd": "speed", "value": pwm})

def arm_position(base=None, shoulder=None, elbow=None, wrist=None) -> None:
    cmd: dict = {"cmd": "arm"}
    if base     is not None: cmd["base"]     = int(base)
    if shoulder is not None: cmd["shoulder"] = int(shoulder)
    if elbow    is not None: cmd["elbow"]    = int(elbow)
    if wrist    is not None: cmd["wrist"]    = int(wrist)
    send_command(cmd)

def arm_home()   -> None: send_command({"cmd": "arm_home"})
def arm_scan()   -> None: send_command({"cmd": "arm_scan"})
def cam_center() -> None: send_command({"cmd": "cam_center"})
def probe_down() -> None: send_command({"cmd": "probe", "action": "down"})
def probe_up()   -> None: send_command({"cmd": "probe", "action": "up"})
def ping()       -> None: send_command({"cmd": "ping"})

def cam_pan_tilt(pan=None, tilt=None) -> None:
    cmd: dict = {"cmd": "cam"}
    if pan  is not None: cmd["pan"]  = int(pan)
    if tilt is not None: cmd["tilt"] = int(tilt)
    send_command(cmd)


# ── Port auto-detection ───────────────────────────────────────────

def _find_esp32_port() -> Optional[str]:
    KEYWORDS = ('ESP', 'CP210', 'CH340', 'CH9102', 'FTDI', 'Silicon Labs', 'USB Serial')
    VID_PIDS = {
        (0x303A, 0x1001),
        (0x10C4, 0xEA60),
        (0x1A86, 0x7523),
        (0x1A86, 0x55D4),
    }
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if (p.vid, p.pid) in VID_PIDS:
            return p.device
    for p in ports:
        desc = (p.description or '') + (p.manufacturer or '')
        if any(k.lower() in desc.lower() for k in KEYWORDS):
            return p.device
    return ports[0].device if ports else None


# ── Internal helpers ──────────────────────────────────────────────

def _set_connected(state: bool) -> None:
    global _connected
    with _lock:
        _connected = state


def _close_port() -> None:
    global _ser
    try:
        if _ser:
            _ser.close()
    except Exception:
        pass
    _ser = None
    _set_connected(False)


# ── Background worker ─────────────────────────────────────────────

def _serial_worker() -> None:
    global _ser
    buf = ""

    while True:
        # ── Connect ───────────────────────────────────────────────
        if _ser is None or not _ser.is_open:
            _set_connected(False)
            port = _port_override or _find_esp32_port()
            if not port:
                time.sleep(CONNECT_RETRY)
                continue
            try:
                _ser = serial.Serial(
                    port=port,
                    baudrate=BAUD_RATE,
                    timeout=READ_TIMEOUT,
                    write_timeout=SEND_TIMEOUT,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                )
                _ser.reset_input_buffer()
                _ser.reset_output_buffer()
                _set_connected(True)
                buf = ""
                print(f"[serial_comm] Connected → {port} @ {BAUD_RATE} baud")

            except PermissionError as exc:
                # Another program (Arduino IDE, other app) owns the port.
                # Print once and wait 30 s before retrying — no log spam.
                print(
                    f"[serial_comm] Port {port} is in use by another program "
                    f"(PermissionError). Close Arduino IDE / other serial monitors. "
                    f"Retrying in {int(PERM_RETRY)} s…"
                )
                _ser = None
                time.sleep(PERM_RETRY)
                continue

            except serial.SerialException as exc:
                print(f"[serial_comm] Cannot open {port}: {exc}")
                _ser = None
                time.sleep(CONNECT_RETRY)
                continue

        # ── Read ──────────────────────────────────────────────────
        try:
            raw = _ser.read(256)
            if raw:
                buf += raw.decode('utf-8', errors='replace')
                while '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    line = line.strip()
                    if line:
                        _parse_incoming(line)

        except (serial.SerialException, OSError) as exc:
            print(f"[serial_comm] Read error: {exc} — reconnecting…")
            _close_port()
            time.sleep(1.0)
            continue

        # ── Send ──────────────────────────────────────────────────
        with _send_lock:
            pending = _send_queue[:]
            _send_queue.clear()

        if pending and _ser and _ser.is_open:
            try:
                _ser.write(('\n'.join(pending) + '\n').encode('utf-8'))
            except (serial.SerialException, OSError) as exc:
                print(f"[serial_comm] Write error: {exc}")
                with _send_lock:
                    _send_queue[:0] = pending   # re-queue unsent commands
                _close_port()


def _parse_incoming(line: str) -> None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return
    with _lock:
        if 'temperature'    in data: _sensor_data['temperature']    = float(data['temperature'])
        if 'humidity'       in data: _sensor_data['humidity']       = float(data['humidity'])
        if 'soil_percent'   in data:
            v = float(data['soil_percent'])
            _sensor_data['soil_percent']  = round(v, 1)
            _sensor_data['soil_moisture'] = round(v, 1)
        if 'distance_front' in data: _sensor_data['distance_front'] = float(data['distance_front'])
        if 'gps_lat'        in data: _sensor_data['gps_lat']        = float(data['gps_lat'])
        if 'gps_lng'        in data: _sensor_data['gps_lng']        = float(data['gps_lng'])
        if 'gps_sats'       in data: _sensor_data['gps_sats']       = int(data['gps_sats'])
        if 'gps_valid'      in data: _sensor_data['gps_valid']      = bool(data['gps_valid'])


# ── Start on import ───────────────────────────────────────────────
_thread = threading.Thread(target=_serial_worker, daemon=True, name="serial_worker")
_thread.start()
print("[serial_comm] USB serial worker started — scanning for ESP32-S3…")
