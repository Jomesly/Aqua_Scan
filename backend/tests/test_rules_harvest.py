from tilapiers.rules import harvest
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()
GROWING = {"latest_sgr": 1.0, "method": "sgr", "poly": None, "n_rounds": 2}


def test_sgr_formula():
    assert round(harvest.sgr(100, 200, 30), 4) == round(100 * 0.693147 / 30, 4)
    assert harvest.sgr(0, 200, 30) is None


def test_all_five_met_and_health_normal_is_ready():
    r = harvest.readiness([320] * 20, 1.5, 150, GROWING, "Normal", T)
    assert r["status"] == harvest.READY
    assert r["met"] == 5


def test_all_five_met_but_health_watch_needs_review():
    r = harvest.readiness([320] * 20, 1.5, 150, GROWING, "Watch", T)
    assert r["status"] == harvest.SIZE_REVIEW


def test_partial_share_with_three_met_is_approaching():
    weights = [320] * 12 + [250] * 8  # 60 % at target, CV ~ 12 %
    r = harvest.readiness(weights, 1.5, 130, None, "Normal", T)
    assert r["met"] == 3  # cv, k, doc met; share below Ready; no growth yet
    assert r["status"] == harvest.APPROACHING


def test_small_fish_not_ready():
    r = harvest.readiness([100] * 20, 1.5, 60, GROWING, "Normal", T)
    assert r["status"] == harvest.NOT_READY


def test_empty_round_is_insufficient():
    assert harvest.readiness([], None, 100, None, "Normal", T)["status"] == harvest.INSUFFICIENT


def test_growth_trend_poly_from_five_rounds():
    pts = [(30, 40), (60, 90), (90, 160), (120, 240), (150, 320)]
    g = harvest.growth_trend(pts, T)
    assert g["method"] == "polynomial" and g["poly"]["r2"] > 0.99
    assert harvest.growth_trend(pts[:4], T)["method"] == "sgr"


def test_single_fish_cannot_pass_uniformity():
    r = harvest.readiness([320], 1.5, 150, GROWING, "Normal", T)
    cv = next(c for c in r["criteria"] if c["key"] == "cv")
    assert cv["passed"] is False
    assert r["status"] != harvest.READY
