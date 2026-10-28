"""USB serial reader for the DS18B20 probe (firmware/tilapiers_probe).

Carried over from the previous build with two fixes:
* ``start()`` reports failure instead of silently claiming success, and
* readings carry a timestamp, so a disconnected probe goes stale instead of
  repeating its last value forever.
"""

import json
import logging
import re
import threading
import time

log = logging.getLogger("tilapiers.serial")

_TEXT_CF = re.compile(r"Temp C:\s*(-?[\d.]+)\s*\|\s*Temp F:\s*(-?[\d.]+)")
_TEXT_C = re.compile(r"Temp:\s*(-?[\d.]+)")

# DS18B20 operating range; anything outside is a wiring/parse error.
VALID_MIN_C, VALID_MAX_C = -55.0, 125.0
DS18B20_DISCONNECTED_C = -127.0


def parse_line(line):
    """Return temperature in °C from one firmware line, or None.

    Accepts the JSON format of the current firmware and the two text formats of
    older sketches.
    """
    line = (line or "").strip()
    if not line:
        return None
    temp = None
    if line.startswith("{"):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if data.get("status") != "ok":
            return None
        temp = data.get("temperature_c")
    else:
        m = _TEXT_CF.search(line) or _TEXT_C.search(line)
        if m:
            temp = m.group(1)
    try:
        temp = float(temp)
    except (TypeError, ValueError):
        return None
    if temp == DS18B20_DISCONNECTED_C or not (VALID_MIN_C <= temp <= VALID_MAX_C):
        return None
    return temp


class SerialProbe:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self._conn = None
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._latest = None  # (ts, temp_c)
        self.error = None

    # connection -----------------------------------------------------------
    def _open(self):
        import serial  # pyserial

        try:
            self._conn = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
            self._stop.wait(2.0)  # board resets when the port opens
            self.error = None
            return True
        except (serial.SerialException, PermissionError, OSError) as exc:
            self._conn = None
            self.error = str(exc)
            return False

    def _close(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    # loop -----------------------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            if self._conn is None:
                if not self._open():
                    self._stop.wait(5.0)
                    continue
            try:
                raw = self._conn.readline()
            except Exception as exc:  # handle lost (unplugged, port taken)
                log.warning("Serial read failed on %s: %s", self.port, exc)
                self.error = str(exc)
                self._close()
                self._stop.wait(2.0)
                continue
            temp = parse_line(raw.decode("utf-8", errors="replace"))
            if temp is not None:
                with self._lock:
                    self._latest = (time.time(), temp)

    def start(self):
        if not self._open():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"probe-{self.port}")
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._close()

    def latest(self, max_age_s=None):
        with self._lock:
            latest = self._latest
        if latest is None:
            return None
        if max_age_s is not None and time.time() - latest[0] > max_age_s:
            return None
        return latest

    def wait_for_reading(self, timeout_s):
        deadline = time.time() + timeout_s
        while time.time() < deadline and not self._stop.is_set():
            if self.latest() is not None:
                return True
            self._stop.wait(0.25)
        return False


def candidate_ports():
    """USB serial ports first; Bluetooth SPP ports are skipped because they open
    but never send data (the old 'ClearCommError: Access is denied')."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = []
    for p in list_ports.comports():
        text = f"{p.description or ''} {p.hwid or ''}".lower()
        if "bluetooth" in text:
            continue
        ports.append(p.device)
    return ports


def discover_probe(explicit_port=None, baudrate=115200, wait_s=5.0):
    """Return a started SerialProbe that has produced a real reading, or None."""
    ports = [explicit_port] if explicit_port else candidate_ports()
    for port in ports:
        probe = SerialProbe(port, baudrate)
        log.info("Trying probe on %s", port)
        if not probe.start():
            log.info("  cannot open %s: %s", port, probe.error)
            continue
        if probe.wait_for_reading(wait_s):
            log.info("  probe connected on %s", port)
            return probe
        log.info("  no temperature data on %s", port)
        probe.stop()
    return None
