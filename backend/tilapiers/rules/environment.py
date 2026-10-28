"""Environment Monitoring rules: Good / Moderate / Critical state, Philippine
season, and stress exposure between sampling rounds."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .thresholds import Thresholds

PH_TZ = timezone(timedelta(hours=8), name="PHT")  # the Philippines has no DST

STATE_ORDER = {"Good": 0, "Moderate": 1, "Critical": 2}

# A gap between consecutive readings longer than this is treated as missing data,
# never as time spent in or out of the band. Two hours tolerates hourly logging
# and short network dropouts of the probe.
MAX_GAP_S = 2 * 3600


@dataclass
class EnvAssessment:
    state: str  # Good | Moderate | Critical | Unknown
    reasons: list = field(default_factory=list)

    def to_dict(self):
        return {"state": self.state, "reasons": list(self.reasons)}


def _worse(a, b):
    return a if STATE_ORDER[a] >= STATE_ORDER[b] else b


def temperature_direction(temp_c, thresholds):
    if temp_c is None:
        return None
    if temp_c < thresholds.temp_min_c:
        return "low"
    if temp_c > thresholds.temp_max_c:
        return "high"
    return None


def classify_environment(temp_c, algae_seen=False, do_ppm=None, thresholds=Thresholds()):
    """Combine the latest probe reading with the caretaker's latest observation.

    A missing temperature is reported as Unknown (probe offline) rather than
    assumed safe or unsafe.
    """
    t = thresholds
    if temp_c is None:
        return EnvAssessment("Unknown", ["No recent temperature reading - check the probe."])

    state = "Good"
    reasons = []
    band = f"{t.temp_min_c:g}-{t.temp_max_c:g} °C"
    if t.temp_min_c <= temp_c <= t.temp_max_c:
        reasons.append(f"Water temperature {temp_c:.1f} °C is within the {band} band.")
    else:
        off = t.temp_min_c - temp_c if temp_c < t.temp_min_c else temp_c - t.temp_max_c
        word = "below" if temp_c < t.temp_min_c else "above"
        level = "Moderate" if off <= t.temp_moderate_margin_c else "Critical"
        state = _worse(state, level)
        reasons.append(f"Water temperature {temp_c:.1f} °C is {off:.1f} °C {word} the {band} band.")

    if algae_seen:
        state = _worse(state, "Moderate")
        reasons.append("Caretaker reported visible algae.")

    if do_ppm is not None:
        if do_ppm < t.do_critical_below_ppm:
            state = _worse(state, "Critical")
            reasons.append(f"Dissolved oxygen {do_ppm:g} ppm is critically low.")
        elif do_ppm < t.do_good_min_ppm:
            state = _worse(state, "Moderate")
            reasons.append(f"Dissolved oxygen {do_ppm:g} ppm is below {t.do_good_min_ppm:g} ppm.")

    return EnvAssessment(state, reasons)


def season_for(ts):
    """PAGASA-style seasons: cool dry (Dec-Feb), hot dry (Mar-May), rainy (Jun-Nov)."""
    month = datetime.fromtimestamp(ts, PH_TZ).month
    if month in (12, 1, 2):
        return "Cool dry"
    if month in (3, 4, 5):
        return "Hot dry"
    return "Rainy"


def stress_exposure(readings, start_ts, end_ts, thresholds=Thresholds()):
    """Stress exposure features for the interval before a sampling round.

    ``readings`` is an iterable of ``(ts, temperature_c)`` sorted by time.
    Returns time outside the band, min, max, mean, mean daily range, maximum rate
    of change (on hourly means), and data coverage of the interval.
    """
    t = thresholds
    pts = [(ts, c) for ts, c in readings if c is not None and start_ts <= ts <= end_ts]
    span = max(end_ts - start_ts, 1.0)
    empty = {
        "n_readings": 0, "hours_outside_band": 0.0, "hours_below_band": 0.0, "hours_above_band": 0.0,
        "min_c": None, "max_c": None, "mean_c": None, "mean_daily_range_c": None,
        "max_rate_c_per_h": None, "coverage": 0.0, "start_ts": start_ts, "end_ts": end_ts,
    }
    if not pts:
        return empty

    below = above = covered = 0.0
    for (t0, c0), (t1, _c1) in zip(pts, pts[1:]):
        dt = t1 - t0
        if dt <= 0 or dt > MAX_GAP_S:
            continue
        covered += dt
        if c0 < t.temp_min_c:
            below += dt
        elif c0 > t.temp_max_c:
            above += dt

    temps = [c for _, c in pts]

    by_day = defaultdict(list)
    by_hour = defaultdict(list)
    for ts, c in pts:
        local = datetime.fromtimestamp(ts, PH_TZ)
        by_day[local.date()].append(c)
        by_hour[int(ts // 3600)].append(c)
    ranges = [max(v) - min(v) for v in by_day.values() if len(v) >= 2]

    hourly = sorted((h, sum(v) / len(v)) for h, v in by_hour.items())
    rates = [abs(c1 - c0) / (h1 - h0) for (h0, c0), (h1, c1) in zip(hourly, hourly[1:]) if 0 < h1 - h0 <= 2]

    return {
        "n_readings": len(pts),
        "hours_outside_band": round((below + above) / 3600, 3),
        "hours_below_band": round(below / 3600, 3),
        "hours_above_band": round(above / 3600, 3),
        "min_c": min(temps),
        "max_c": max(temps),
        "mean_c": round(sum(temps) / len(temps), 2),
        "mean_daily_range_c": round(sum(ranges) / len(ranges), 2) if ranges else None,
        "max_rate_c_per_h": round(max(rates), 2) if rates else None,
        "coverage": round(min(covered / span, 1.0), 3),
        "start_ts": start_ts,
        "end_ts": end_ts,
    }
