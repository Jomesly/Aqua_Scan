from synth import board_photo

from tilapiers.vision import board, outline, quality


def test_board_detects_four_markers_and_scale():
    r = board.detect(board_photo(), 38.0, 26.0)
    assert r["ok"], r["reasons"]
    assert sorted(r["found"]) == [0, 1, 2, 3]
    assert abs(r["cm_per_px"] - 1 / board.PX_PER_CM) < 1e-9


def test_outline_length_within_five_percent():
    r = board.detect(board_photo(fish_len_cm=20.0), 38.0, 26.0)
    m = outline.measure(r["warped"], r["cm_per_px"])
    assert m["ok"], m
    assert abs(m["length_cm"] - 20.0) / 20.0 < 0.05
    expected_area = 3.14159 * 10 * 3
    assert abs(m["area_cm2"] - expected_area) / expected_area < 0.10
    assert m["method"] == "classical"


def test_missing_marker_fails_with_reason():
    r = board.detect(board_photo(cover_marker=2), 38.0, 26.0)
    assert not r["ok"]
    assert any("marker" in x.lower() for x in r["reasons"])


def test_blurry_photo_fails_quality():
    q = quality.assess(board_photo(blur=True))
    assert not q["ok"]
    assert any("blurry" in x.lower() for x in q["reasons"])


def test_sharp_photo_passes_quality():
    assert quality.assess(board_photo())["ok"]
