"""Background monitor: logs probe readings and re-evaluates each pond's
environment state (notifying only on transitions).

Sensor modes (TILAPIERS_SENSOR):
  auto      discover the USB probe; if none is found, log nothing (the pond shows
            'probe offline' - it never falls back to fake data)
  serial    same, but keep retrying discovery until a probe appears
  simulate  explicit demo mode; readings stored with source='simulated'
  off       no local sensor (readings arrive via POST /api/ingest/temperature)
"""

import logging
import threading
import time

from .sensors.serial_probe import discover_probe
from .sensors.simulator import PondSimulator

log = logging.getLogger("tilapiers.monitor")


class Monitor:
    def __init__(self, services, settings):
        self.services = services
        self.settings = settings
        self._stop = threading.Event()
        self._thread = None
        self.probe = None
        self.sims = {}
        self.status = {"mode": settings.sensor_mode, "probe_port": None, "probe_error": None,
                       "serial_pond_id": settings.serial_pond_id, "last_tick": None}

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="tilapiers-monitor")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self.probe:
            self.probe.stop()
        if self._thread:
            self._thread.join(timeout=5)

    def _connect_probe(self):
        self.probe = discover_probe(self.settings.serial_port)
        if self.probe:
            self.status.update(probe_port=self.probe.port, probe_error=None)
            log.info("Probe on %s logging to pond %s", self.probe.port, self.settings.serial_pond_id)
        else:
            self.status.update(probe_port=None, probe_error="No probe found on USB serial ports")
            log.warning("No temperature probe found; pond will show 'probe offline'.")

    def _run(self):
        mode = self.settings.sensor_mode
        if mode in ("auto", "serial"):
            self._connect_probe()
        last_discovery = time.time()
        interval = self.settings.log_interval_s

        while not self._stop.is_set():
            try:
                now = time.time()
                if mode in ("auto", "serial"):
                    if self.probe is None and mode == "serial" and now - last_discovery > 30:
                        last_discovery = now
                        self._connect_probe()
                    if self.probe is not None:
                        latest = self.probe.latest(max_age_s=interval * 3)
                        if latest:
                            self.services.record_reading(self.settings.serial_pond_id, latest[1], "probe-serial", latest[0])
                        self.status["probe_error"] = self.probe.error
                elif mode == "simulate":
                    for pond in self.services.list_ponds():
                        sim = self.sims.get(pond["id"])
                        if sim is None:
                            sim = self.sims[pond["id"]] = PondSimulator(seed=pond["id"])
                            last = self.services.latest_reading(pond["id"])
                            if last:  # continue smoothly from the stored log
                                sim.temp = last["temperature_c"]
                        self.services.record_reading(pond["id"], sim.next(now), "simulated", now)

                for pond in self.services.list_ponds():
                    self.services.evaluate_environment(pond["id"])
                self.status["last_tick"] = now
            except Exception:  # keep monitoring even if one tick fails
                log.exception("monitor tick failed")
            self._stop.wait(interval)
