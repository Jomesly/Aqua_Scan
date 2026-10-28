import numpy as np
import pytest

from tilapiers.rules.health import (
    DEFAULT_FCI_MODEL,
    FEATURE_GROUPS,
    compare_feature_groups,
    condition_factor,
    fit_fci_model,
    health_status,
    predict_fci,
)
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()

HEALTHY = dict(condition_factor=1.7, gill_color_index=0.7, skin_color_index=0.7,
               fin_integrity=0.9, eye_clarity=0.7, body_shape=0.38)
POOR = dict(condition_factor=1.2, gill_color_index=0.3, skin_color_index=0.4,
            fin_integrity=0.5, eye_clarity=0.3, body_shape=0.33)


def test_condition_factor_fulton():
    # K = 100 * W / L^3 ; 200 g fish at 22 cm
    assert condition_factor(200, 22) == pytest.approx(100 * 200 / 22**3)
    assert condition_factor(None, 22) is None
    assert condition_factor(200, 0) is None


def test_default_model_orders_healthy_above_poor():
    good = predict_fci(DEFAULT_FCI_MODEL, HEALTHY)
    bad = predict_fci(DEFAULT_FCI_MODEL, POOR)
    assert 1.0 <= bad < T.fci_flag_below < good <= 5.0


def test_predict_imputes_missing_feature_with_model_mean():
    partial = dict(HEALTHY)
    partial.pop("eye_clarity")
    assert predict_fci(DEFAULT_FCI_MODEL, partial) is not None


def test_predict_requires_condition_factor():
    partial = dict(HEALTHY)
    partial["condition_factor"] = None
    assert predict_fci(DEFAULT_FCI_MODEL, partial) is None


def _synthetic(n=60, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        x = {
            "condition_factor": rng.uniform(1.1, 2.0),
            "gill_color_index": rng.uniform(0.2, 0.9),
            "skin_color_index": rng.uniform(0.3, 0.9),
            "fin_integrity": rng.uniform(0.4, 1.0),
            "eye_clarity": rng.uniform(0.2, 0.9),
            "body_shape": rng.uniform(0.3, 0.45),
        }
        score = 0.5 + 1.2 * x["condition_factor"] + 2.0 * x["gill_color_index"] + 1.0 * x["fin_integrity"]
        score += rng.normal(0, 0.15)
        rows.append({**x, "technician_score": float(np.clip(score, 1, 5)), "pond_id": 1 + i % 3, "round_id": i % 9})
    return rows


def test_fit_recovers_signal_and_reports_grouped_cv():
    model = fit_fci_model(_synthetic(), FEATURE_GROUPS["full"])
    assert model["n"] == 60
    assert model["metrics"]["train"]["r2"] > 0.8
    assert model["metrics"]["cv"]["method"] == "leave-one-pond-out"
    assert model["metrics"]["cv"]["r2"] > 0.6
    assert model["coefs"]["gill_color_index"] > model["coefs"]["eye_clarity"]


def test_fit_polynomial_terms_limited_to_degree_two():
    model = fit_fci_model(_synthetic(), ["condition_factor"], poly_features=["condition_factor"])
    assert "condition_factor^2" in model["coefs"]


def test_fit_refuses_too_few_rows():
    with pytest.raises(ValueError):
        fit_fci_model(_synthetic(n=4), FEATURE_GROUPS["full"])


def test_compare_groups_full_model_beats_k_only():
    result = compare_feature_groups(_synthetic())
    names = [r["group"] for r in result]
    assert names == list(FEATURE_GROUPS)
    by = {r["group"]: r for r in result}
    assert by["full"]["cv"]["r2"] > by["k_only"]["cv"]["r2"]


def test_health_normal_watch_refer():
    normal = health_status([4.2] * 10, mean_k=1.7, env_critical=False, thresholds=T)
    assert normal["status"] == "Normal"

    watch = health_status([4.2] * 8 + [2.0] * 2, mean_k=1.7, env_critical=False, thresholds=T)
    assert watch["status"] == "Watch"
    assert watch["share_flagged"] == pytest.approx(0.2)

    refer = health_status([4.2] * 6 + [2.0] * 4, mean_k=1.7, env_critical=False, thresholds=T)
    assert refer["status"] == "Refer to technician"


def test_health_low_k_or_critical_environment_is_watch():
    assert health_status([4.2] * 10, mean_k=1.2, env_critical=False, thresholds=T)["status"] == "Watch"
    assert health_status([4.2] * 10, mean_k=1.7, env_critical=True, thresholds=T)["status"] == "Watch"


def test_health_no_fish():
    assert health_status([], mean_k=None, env_critical=False, thresholds=T)["status"] == "Insufficient data"
