"""Explicit demo simulator. Only used when TILAPIERS_SENSOR=simulate (or demo
mode). Every reading it produces is stored with source='simulated'."""

import math
import random
import time

from ..rules.environment import PH_TZ


class PondSimulator:
    def __init__(self, seed, base_c=28.0):
        self._rng = random.Random(seed)
        self.base_c = base_c + self._rng.uniform(-0.6, 0.6)
        self.temp = self.base_c
        self._excursion_left = 0

    def next(self, ts=None):
        ts = ts or time.time()
        from datetime import datetime

        hour = datetime.fromtimestamp(ts, PH_TZ).hour + datetime.fromtimestamp(ts, PH_TZ).minute / 60
        diurnal = 1.4 * math.sin((hour - 9) / 24 * 2 * math.pi)  # warmest mid-afternoon
        target = self.base_c + diurnal
        self.temp += (target - self.temp) * 0.08 + self._rng.gauss(0, 0.05)
        # occasional excursion so state changes and alerts can be demonstrated
        if self._excursion_left == 0 and self._rng.random() < 0.002:
            self._excursion_left = self._rng.randint(20, 60)
        if self._excursion_left > 0:
            self._excursion_left -= 1
            self.temp += (31.9 - self.temp) * 0.25
        return round(self.temp, 2)
