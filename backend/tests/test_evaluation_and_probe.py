import pytest

from tilapiers.rules.evaluation import agreement, calibration_metrics, stress_association
from tilapiers.sensors.serial_probe import parse_line


def test_calibration_metrics():
    m = calibration_metrics([(28.2, 28.0), (27.9, 28.0), (30.3, 30.0)])
    assert m["n"] == 3
    assert m["bias"] == pytest.approx((0.2 - 0.1 + 0.3) / 3, abs=1e-3)
    assert m["max_abs"] == pytest.approx(0.3)


def test_agreement_perfect_and_kappa():
    labels = ["Normal", "Watch", "Refer to technician"]
    a = agreement([("Normal", "Normal"), ("Watch", "Watch"), ("Normal", "Normal")], labels)
    assert a["accuracy"] == 1.0
    assert a["kappa"] == pytest.approx(1.0)
    b = agreement([("Normal", "Watch"), ("Watch", "Normal")], labels)
    assert b["accuracy"] == 0.0
    assert b["confusion"]["Watch"]["Normal"] == 1


def test_stress_association_negative_slope():
    rows = [{"pond_id": p, "x": x, "y": 4.5 - 0.05 * x + (0.2 if p == 2 else 0)}
            for p in (1, 2) for x in (0, 5, 10, 20)]
    res = stress_association(rows)
    assert res["slope"] == pytest.approx(-0.05, abs=1e-6)
    assert res["n_ponds"] == 2


def test_stress_association_needs_data():
    assert stress_association([{"pond_id": 1, "x": 1, "y": 4}])["slope"] is None


@pytest.mark.parametrize("line,expected", [
    ('{"status":"ok","temperature_c":28.4,"temperature_f":83.1}', 28.4),
    ('{"status":"error","message":"DS18B20 not detected"}', None),
    ("Temp C: 27.75 | Temp F: 81.95", 27.75),
    ("Temp: 26.1", 26.1),
    ('{"status":"ok","temperature_c":-127}', None),
    ("garbage", None),
    ("", None),
])
def test_parse_probe_lines(line, expected):
    assert parse_line(line) == expected
