from synth import board_photo

from tilapiers.rules.thresholds import Thresholds
from tilapiers.vision import pipeline

T = Thresholds(board_width_cm=38.0, board_height_cm=26.0)


class FakeScreener:
    available = True
    name = "fake"

    def __init__(self, cls="Healthy", conf=0.9):
        self.cls, self.conf = cls, conf

    def predict(self, img, conf):
        h, w = img.shape[:2]
        return [{"cls": self.cls, "conf": self.conf, "box": [0, 0, w, h]}] if self.conf >= conf else []


def _side(cls, conf, L=None, A=None):
    return {"ok": True, "top": {"cls": cls, "conf": conf} if cls else None, "length_cm": L, "area_cm2": A}


def test_merge_disease_on_one_side_wins():
    m = pipeline.merge_sides([_side("Healthy", 0.9, 20, 90), _side("TiLV", 0.6, 22, 94)])
    assert (m["cls"], m["conf"]) == ("TiLV", 0.6)
    assert m["length_cm"] == 21 and m["area_cm2"] == 92 and m["sides"] == 2


def test_merge_two_healthy_takes_max_confidence():
    m = pipeline.merge_sides([_side("Healthy", 0.7), _side("Healthy", 0.9)])
    assert (m["cls"], m["conf"]) == ("Healthy", 0.9)


def test_merge_single_side():
    m = pipeline.merge_sides([_side("Healthy", 0.8, 20, 90)])
    assert m["sides"] == 1 and m["length_cm"] == 20


def test_merge_ignores_failed_photos():
    bad = {"ok": False, "top": {"cls": "TiLV", "conf": 0.99}, "length_cm": 50, "area_cm2": 1}
    m = pipeline.merge_sides([bad, _side("Healthy", 0.8, 20, 90)])
    assert m["cls"] == "Healthy" and m["sides"] == 1


def test_board_photo_is_screened_and_measured(tmp_path):
    r = pipeline.process_photo(board_photo(), True, T, FakeScreener("Aeromonas", 0.7), None, tmp_path / "a.jpg")
    assert r["ok"], r["reasons"]
    assert r["top"] == {"cls": "Aeromonas", "conf": 0.7}
    assert abs(r["length_cm"] - 20) < 1.0
    assert (tmp_path / "a.jpg").exists()


def test_no_board_photo_is_screened_but_not_measured(tmp_path):
    r = pipeline.process_photo(board_photo(warp=False), False, T, FakeScreener(), None, tmp_path / "b.jpg")
    assert r["ok"] and r["top"]["cls"] == "Healthy"
    assert r["length_cm"] is None and r["area_cm2"] is None


def test_board_mode_missing_marker_needs_retake(tmp_path):
    r = pipeline.process_photo(board_photo(cover_marker=1), True, T, FakeScreener(), None, tmp_path / "c.jpg")
    assert not r["ok"]
    assert any("marker" in x.lower() for x in r["reasons"])


def test_below_detection_threshold_is_not_screened(tmp_path):
    r = pipeline.process_photo(board_photo(), True, T, FakeScreener("TiLV", 0.1), None, tmp_path / "d.jpg")
    assert r["ok"] and r["top"] is None


def test_real_model_loads_and_runs_when_present(tmp_path):
    import pytest

    from tilapiers.config import MODELS_DIR
    from tilapiers.vision.screening import Screener

    path = MODELS_DIR / "yolov8s_best.pt"
    if not path.exists():
        pytest.skip("team weights not copied into backend/models")
    s = Screener(path)
    assert s.available, s.error
    assert set(s.names.values()) == {"Healthy", "Aeromonas", "TiLV"}
    r = pipeline.process_photo(board_photo(), True, T, s, None, tmp_path / "r.jpg")
    assert r["ok"] and r["length_cm"] is not None
