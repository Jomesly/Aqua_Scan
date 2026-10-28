from tilapiers.rules import health
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()


def test_condition_factor_formula():
    assert round(health.condition_factor(300, 25), 3) == round(100 * 300 / 25 ** 3, 3)
    assert health.condition_factor(None, 25) is None
    assert health.condition_factor(300, None) is None


def test_healthy_with_k_in_range_is_normal():
    assert health.fish_status("Healthy", 0.9, 1.2, T)["status"] == health.NORMAL


def test_healthy_with_low_k_is_watch():
    r = health.fish_status("Healthy", 0.9, 0.8, T)
    assert r["status"] == health.WATCH
    assert any("K" in x for x in r["reasons"])


def test_healthy_without_k_is_normal_and_says_k_not_measured():
    r = health.fish_status("Healthy", 0.9, None, T)
    assert r["status"] == health.NORMAL
    assert any("K not measured" in x for x in r["reasons"])


def test_disease_below_referral_cutoff_is_watch():
    assert health.fish_status("TiLV", 0.4, 1.2, T)["status"] == health.WATCH


def test_disease_at_referral_cutoff_is_refer():
    assert health.fish_status("Aeromonas", 0.5, 1.2, T)["status"] == health.REFER


def test_no_screening_result_is_unscreened():
    assert health.fish_status(None, None, 1.2, T)["status"] == health.UNSCREENED


def test_pond_one_refer_fish_refers_pond():
    s = [health.NORMAL] * 19 + [health.REFER]
    assert health.pond_status(s, T)["status"] == health.REFER


def test_pond_ten_percent_watch_is_watch():
    s = [health.NORMAL] * 18 + [health.WATCH] * 2
    assert health.pond_status(s, T)["status"] == health.WATCH


def test_pond_five_percent_watch_is_normal():
    s = [health.NORMAL] * 19 + [health.WATCH]
    assert health.pond_status(s, T)["status"] == health.NORMAL


def test_pond_thirty_percent_watch_refers():
    s = [health.NORMAL] * 7 + [health.WATCH] * 3
    assert health.pond_status(s, T)["status"] == health.REFER


def test_pond_without_screened_fish_is_insufficient():
    assert health.pond_status([health.UNSCREENED], T)["status"] == health.INSUFFICIENT


def test_pond_mostly_unscreened_is_insufficient():
    s = [health.UNSCREENED] * 19 + [health.NORMAL]
    r = health.pond_status(s, T)
    assert r["status"] == health.INSUFFICIENT
    assert r["screened_share"] == 0.05


def test_pond_enough_screened_is_assessed():
    s = [health.UNSCREENED] * 2 + [health.NORMAL] * 8
    assert health.pond_status(s, T)["status"] == health.NORMAL
