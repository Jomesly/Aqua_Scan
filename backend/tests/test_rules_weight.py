import numpy as np

from tilapiers.rules import weight
from tilapiers.rules.thresholds import Thresholds

T = Thresholds()


def _rows(n=40, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        L = rng.uniform(12, 30)
        A = 0.22 * L * L * rng.uniform(0.95, 1.05)
        W = 0.015 * L ** 3 * rng.uniform(0.95, 1.05)
        rows.append({"L": L, "A": A, "W": W, "group": i % 4})
    return rows


def test_provisional_model_is_power_curve():
    m = weight.provisional_model(T)
    assert m["kind"] == "power"
    assert round(weight.predict(m, 20, None), 2) == round(0.0141 * 20 ** 3, 2)


def test_predict_without_length_is_none():
    assert weight.predict(weight.provisional_model(T), None, None) is None


def test_fit_models_selects_good_model():
    out = weight.fit_models(_rows(), T)
    sel = out[out["selected"]]
    assert sel["cv"]["r2"] > 0.95
    assert set(out["linear"]["terms"]) <= {"L", "A"}
    assert set(out["poly"]["terms"]) <= {"L", "A", "L2", "A2", "LA"}
    for k in ("r2", "rmse", "mae", "mare", "mxae", "mxre"):
        assert k in out["linear"]["cv"]


def test_fit_requires_minimum_rows():
    try:
        weight.fit_models(_rows(5), T)
    except ValueError as e:
        assert "at least" in str(e)
    else:
        raise AssertionError("expected ValueError")
