from datetime import datetime

import pytest

from tilapiers.rules.environment import (
    PH_TZ,
    classify_environment,
    season_for,
    stress_exposure,
)
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()


def ts(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=PH_TZ).timestamp()


@pytest.mark.parametrize("temp", [24.0, 27.5, 31.0])
def test_in_band_is_good(temp):
    assert classify_environment(temp, thresholds=T).state == "Good"


@pytest.mark.parametrize("temp", [23.2, 31.8])
def test_just_outside_band_is_moderate(temp):
    result = classify_environment(temp, thresholds=T)
    assert result.state == "Moderate"
    assert result.reasons


@pytest.mark.parametrize("temp", [22.5, 32.5])
def test_far_outside_band_is_critical(temp):
    assert classify_environment(temp, thresholds=T).state == "Critical"


def test_missing_reading_is_unknown_not_safe():
    result = classify_environment(None, thresholds=T)
    assert result.state == "Unknown"


def test_algae_report_raises_good_to_moderate():
    result = classify_environment(28.0, algae_seen=True, thresholds=T)
    assert result.state == "Moderate"
    assert any("algae" in r.lower() for r in result.reasons)


def test_algae_does_not_lower_critical():
    assert classify_environment(33.0, algae_seen=True, thresholds=T).state == "Critical"


def test_dissolved_oxygen_optional_and_worst_wins():
    assert classify_environment(28.0, do_ppm=6.0, thresholds=T).state == "Good"
    assert classify_environment(28.0, do_ppm=4.0, thresholds=T).state == "Moderate"
    assert classify_environment(28.0, do_ppm=2.0, thresholds=T).state == "Critical"


@pytest.mark.parametrize(
    "month,season",
    [(1, "Cool dry"), (2, "Cool dry"), (12, "Cool dry"), (3, "Hot dry"), (5, "Hot dry"), (6, "Rainy"), (11, "Rainy")],
)
def test_philippine_seasons(month, season):
    assert season_for(ts(2026, month, 15)) == season


def test_stress_exposure_hours_outside_band():
    start = ts(2026, 7, 1, 0)
    # hourly readings for 6 hours: 2 hours above band, 4 inside
    temps = [28, 28, 32, 32, 28, 28, 28]
    readings = [(start + i * 3600, t) for i, t in enumerate(temps)]
    exp = stress_exposure(readings, start, start + 6 * 3600, thresholds=T)
    assert exp["hours_outside_band"] == pytest.approx(2.0)
    assert exp["min_c"] == 28
    assert exp["max_c"] == 32
    assert exp["max_rate_c_per_h"] == pytest.approx(4.0)
    assert exp["coverage"] == pytest.approx(1.0)


def test_stress_exposure_gaps_are_not_counted_as_exposure():
    start = ts(2026, 7, 1, 0)
    readings = [(start, 33.0), (start + 10 * 3600, 33.0)]  # 10 h gap: probe offline
    exp = stress_exposure(readings, start, start + 10 * 3600, thresholds=T)
    assert exp["hours_outside_band"] == pytest.approx(0.0)
    assert exp["coverage"] < 0.2


def test_stress_exposure_daily_range():
    readings = []
    for day in (1, 2):
        readings.append((ts(2026, 7, day, 6), 26.0))
        readings.append((ts(2026, 7, day, 14), 30.0 if day == 1 else 28.0))
    exp = stress_exposure(readings, ts(2026, 7, 1), ts(2026, 7, 3), thresholds=T)
    assert exp["mean_daily_range_c"] == pytest.approx(3.0)


def test_stress_exposure_empty():
    exp = stress_exposure([], 0, 3600, thresholds=T)
    assert exp["n_readings"] == 0
    assert exp["min_c"] is None
