import cv2
import pytest
from fakes import FakeScreener
from synth import board_photo

from tilapiers.db import Database
from tilapiers.services import Services


def _jpg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


@pytest.fixture
def svc(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    s = Services(Database(settings.db_path), settings, FakeScreener("Aeromonas", 0.8), None)
    s.update_thresholds({"board_width_cm": 38.0, "board_height_cm": 26.0}, "test", confirmed=False)
    return s


@pytest.fixture
def rnd(svc):
    pond = svc.create_pond({"name": "Pond 1", "stocked_count": 1000, "stocked_at": "2026-06-01"})
    return svc.create_round(pond["id"], {"days_of_culture": 120, "board_mode": True}, "caretaker")


def test_upload_side_a_screens_and_measures(svc, rnd):
    fish = svc.add_fish(rnd["id"])
    out = svc.upload_photo(fish["id"], "A", _jpg(board_photo()))
    assert out["photo"]["ok"], out["photo"]["result"]["reasons"]
    f = out["fish"]
    assert f["cls"] == "Aeromonas" and f["conf"] == 0.8
    assert abs(f["length_cm"] - 20) < 1
    assert f["status"] == "Refer to technician"
    assert f["est_weight_g"] is not None and f["k"] is not None
    assert f["sides"] == 1


def test_missing_marker_photo_is_rejected_and_fish_not_processed(svc, rnd):
    fish = svc.add_fish(rnd["id"])
    out = svc.upload_photo(fish["id"], "A", _jpg(board_photo(cover_marker=0)))
    assert not out["photo"]["ok"]
    assert out["fish"]["cls"] is None
    assert out["fish"]["status"] == "Not screened"


def test_retake_replaces_side(svc, rnd):
    fish = svc.add_fish(rnd["id"])
    svc.upload_photo(fish["id"], "A", _jpg(board_photo(cover_marker=0)))
    out = svc.upload_photo(fish["id"], "A", _jpg(board_photo()))
    assert out["photo"]["ok"]
    assert len(svc.get_round(rnd["id"])["fish"][0]["photos"]) == 1
    assert svc.retake_stats()["failed"] == 1


def test_empty_round_completes_as_insufficient(svc, rnd):
    done = svc.complete_round(rnd["id"])
    a = done["assessment"]
    assert a["readiness"]["status"] == "Insufficient data"
    assert a["health"]["status"] == "Insufficient data"


def test_snapshot_unchanged_after_cutoff_change(svc, rnd):
    fish = svc.add_fish(rnd["id"])
    svc.upload_photo(fish["id"], "A", _jpg(board_photo()))
    before = svc.complete_round(rnd["id"])["assessment"]
    svc.update_thresholds({"referral_conf": 0.95, "target_weight_g": 10}, "admin", confirmed=False)
    after = svc.get_round(rnd["id"])["assessment"]
    assert after == before
    assert after["health"]["status"] == "Refer to technician"


def test_biomass_uses_count(svc, rnd):
    fish = svc.add_fish(rnd["id"])
    svc.upload_photo(fish["id"], "A", _jpg(board_photo()))
    s = svc.round_assessment(rnd["id"])["summary"]
    assert s["biomass_kg"] == pytest.approx(s["avg_weight_g"] * 1000 / 1000, rel=1e-3)


def test_users_authenticate(svc):
    svc.create_user({"username": "ana", "password": "secret123", "role": "caretaker", "full_name": "Ana"})
    assert svc.authenticate("ana", "secret123")["role"] == "caretaker"
    assert svc.authenticate("ana", "wrong") is None


def test_threshold_history_records_changes(svc):
    svc.update_thresholds({"target_weight_g": 280}, "admin", confirmed=True)
    meta = svc.thresholds_meta()
    assert meta["values"]["target_weight_g"] == 280
    assert meta["confirmed"] is True
    assert meta["history"][0]["changes"]["target_weight_g"] == [300.0, 280.0]


@pytest.mark.parametrize("changes", [{"det_conf": 5}, {"ready_share": 2}, {"min_screened_share": -0.1},
                                     {"target_weight_g": 0}, {"det_conf": "abc"}])
def test_out_of_range_cutoffs_rejected(svc, changes):
    from tilapiers.services import Invalid
    with pytest.raises(Invalid):
        svc.update_thresholds(changes, "admin")
