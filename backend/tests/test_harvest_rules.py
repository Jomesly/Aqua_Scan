import math

import pytest

from tilapiers.rules.harvest import growth_trend, harvest_readiness, round_size_stats, specific_growth_rate
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()


def test_specific_growth_rate():
    assert specific_growth_rate(100, 150, 14) == pytest.approx(100 * (math.log(150) - math.log(100)) / 14)
    assert specific_growth_rate(100, 150, 0) is None
    assert specific_growth_rate(None, 150, 14) is None


def test_round_size_stats():
    stats = round_size_stats([200, 260, 270, 300], T)
    assert stats["n"] == 4
    assert stats["share_at_target"] == pytest.approx(0.75)
    assert stats["mean_weight_g"] == pytest.approx(257.5)
    assert 0 < stats["weight_cv"] < 0.2


def test_growth_trend_uses_sgr_below_five_rounds():
    trend = growth_trend([(30, 50), (45, 80), (60, 120)], T)
    assert trend["method"] == "sgr"
    assert trend["poly"] is None
    assert trend["latest_sgr"] > 0


def test_growth_trend_fits_degree_two_with_five_rounds():
    pts = [(d, 0.01 * d * d + 10) for d in (30, 45, 60, 75, 90)]
    trend = growth_trend(pts, T)
    assert trend["method"] == "polynomial"
    assert trend["poly"]["degree"] == 2
    assert trend["poly"]["r2"] == pytest.approx(1.0)
    # never extrapolated beyond the observed days of culture
    assert trend["poly"]["curve"][0][0] == 30
    assert trend["poly"]["curve"][-1][0] == 90


def _ready_kwargs(**over):
    base = dict(
        weights_g=[260, 270, 255, 280, 265, 275, 258, 262, 290, 240],
        mean_k=1.7, days_of_culture=150, health="Normal",
        recent_critical=False, growth={"method": "sgr", "latest_sgr": 0.8, "poly": None},
        thresholds=T,
    )
    base.update(over)
    return base


def test_ready():
    result = harvest_readiness(**_ready_kwargs())
    assert result["status"] == "Ready"
    assert all(c["passed"] for c in result["criteria"] if c["key"] in ("size", "uniformity", "health"))


def test_size_reached_but_health_review_needed():
    result = harvest_readiness(**_ready_kwargs(health="Watch"))
    assert result["status"] == "Size reached - health review needed"


def test_recent_critical_blocks_ready():
    result = harvest_readiness(**_ready_kwargs(recent_critical=True))
    assert result["status"] == "Size reached - health review needed"


def test_approaching_by_share_or_days():
    half = [260] * 6 + [200] * 4
    assert harvest_readiness(**_ready_kwargs(weights_g=half))["status"] == "Approaching"
    small = [150] * 10
    assert harvest_readiness(**_ready_kwargs(weights_g=small, days_of_culture=125))["status"] == "Approaching"


def test_not_ready():
    result = harvest_readiness(**_ready_kwargs(weights_g=[120] * 10, days_of_culture=60))
    assert result["status"] == "Not Ready"


def test_uneven_sizes_block_ready():
    uneven = [400, 420, 410, 390, 405, 400, 410, 395, 120, 110]
    result = harvest_readiness(**_ready_kwargs(weights_g=uneven))
    assert result["status"] != "Ready"


def test_small_sample_warning():
    result = harvest_readiness(**_ready_kwargs(weights_g=[260, 270, 280]))
    assert any("fish" in n for n in result["notes"])


def test_no_fish():
    assert harvest_readiness(**_ready_kwargs(weights_g=[]))["status"] == "Insufficient data"
