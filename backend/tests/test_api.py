import time

from conftest import board_photo


def test_system_reports_stub_detector_and_no_external_channel(client):
    s = client.get("/api/system").json()
    assert s["detector"]["is_stub"] is True
    assert s["notifications"]["ready"] is False
    assert s["thresholds"]["temp_min_c"] == 24.0
    assert s["thresholds"]["temp_max_c"] == 31.0


def test_pond_without_readings_is_unknown_not_safe(client, pond):
    env = client.get(f"/api/ponds/{pond['id']}/environment").json()
    assert env["now"]["state"] == "Unknown"
    assert env["now"]["stale"] is True


def test_ingest_requires_token_and_updates_state(client, pond):
    body = {"pond_id": pond["id"], "readings": [{"ts": time.time() - 5, "temperature_c": 33.5}]}
    assert client.post("/api/ingest/temperature", json=body).status_code == 401
    r = client.post("/api/ingest/temperature", json=body, headers={"X-Device-Token": "secret"})
    assert r.json() == {"stored": 1}
    env = client.get(f"/api/ponds/{pond['id']}/environment").json()["now"]
    assert env["state"] == "Critical"
    notes = client.get("/api/notifications").json()["notifications"]
    assert notes[0]["kind"] == "environment"
    assert notes[0]["deliveries"] == [notes[0]["deliveries"][0]]
    assert notes[0]["deliveries"][0]["channel"] == "dashboard"


def test_algae_observation_makes_environment_moderate(client, pond):
    client.post("/api/ingest/temperature", headers={"X-Device-Token": "secret"},
                json={"pond_id": pond["id"], "readings": [{"ts": time.time(), "temperature_c": 28.0}]})
    env = client.post(f"/api/ponds/{pond['id']}/observations", json={"algae_seen": True}).json()
    assert env["state"] == "Moderate"
    assert env["algae_active"] is True


def test_sampling_round_with_photo_flow(client, pond):
    rnd = client.post(f"/api/ponds/{pond['id']}/rounds", json={"capture_condition": "shade"}).json()
    assert rnd["status"] == "draft"
    assert 99 < rnd["days_of_culture"] < 101

    fish = client.post(f"/api/rounds/{rnd['id']}/fish",
                       data={"weight_g": "180", "length_cm": "21.5", "technician_score": "4"},
                       files={"photo": ("fish.jpg", board_photo(), "image/jpeg")})
    assert fish.status_code == 201, fish.text
    f = fish.json()
    assert f["analysis_source"] == "photo"
    assert f["detection"]["is_stub"] is True
    assert f["fci"] is not None
    assert {c["key"] for c in f["quality"]["checks"]} == {"sharpness", "exposure", "glare", "scale"}
    assert client.get(f["photo_url"]).status_code == 200

    manual = client.post(f"/api/rounds/{rnd['id']}/fish", data={"weight_g": "175", "length_cm": "21"}).json()
    assert manual["analysis_source"] == "manual"
    assert manual["fci"] is None

    done = client.post(f"/api/rounds/{rnd['id']}/complete").json()
    assert done["status"] == "completed"
    assert done["assessment_recorded"] is True
    assert done["assessment"]["readiness"]["status"] in ("Not Ready", "Approaching")

    # completed rounds are part of the record
    assert client.delete(f"/api/rounds/{rnd['id']}").status_code == 400
    assert client.post(f"/api/rounds/{rnd['id']}/fish", data={"weight_g": "1", "length_cm": "1"}).status_code == 400


def test_bad_photo_is_rejected(client, pond):
    rnd = client.post(f"/api/ponds/{pond['id']}/rounds", json={}).json()
    r = client.post(f"/api/rounds/{rnd['id']}/fish", data={"weight_g": "180", "length_cm": "21"},
                    files={"photo": ("fish.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_thresholds_validation_and_fixed_band(client):
    r = client.put("/api/settings/thresholds", json={"health_watch_share": 0.5, "health_refer_share": 0.2})
    assert r.status_code == 400
    r = client.put("/api/settings/thresholds", json={"target_weight_g": 300, "temp_min_c": 10})
    assert r.status_code == 200
    assert r.json()["values"]["target_weight_g"] == 300
    assert r.json()["values"]["temp_min_c"] == 24.0  # band is fixed by the study team


def test_photo_path_traversal_blocked(client):
    assert client.get("/api/photos/..%2F..%2Fsecret.txt").status_code == 404


def test_demo_seed_end_to_end(make_client):
    with make_client(demo=True) as c:
        overview = c.get("/api/overview").json()
        assert len(overview["ponds"]) == 3
        statuses = {p["name"]: p["latest_round"]["readiness"] for p in overview["ponds"]}
        assert statuses["Pond C"] in ("Ready", "Size reached - health review needed")
        assert statuses["Pond B"] == "Not Ready"

        pond_b = next(p for p in overview["ponds"] if p["name"] == "Pond B")
        assert pond_b["latest_round"]["health"]["status"] in ("Watch", "Refer to technician")

        growth = c.get("/api/ponds/1/growth").json()
        assert growth["trend"]["method"] == "polynomial"

        ev = c.get("/api/evaluation").json()
        assert ev["n_scored_fish"] > 50
        assert ev["probe_calibration"]["n"] == 12
        assert ev["health_agreement"]["n"] == 17
        assert ev["stress_association"]["n_ponds"] == 3
        assert ev["length_error"]["n"] == 0  # seed has no real detector output

        fitted = c.post("/api/evaluation/fit", json={"poly_features": []}).json()
        assert fitted["metrics"]["cv"]["method"] == "leave-one-pond-out"
        assert c.get("/api/system").json()["fci_model"]["name"] == "fitted"

        csv_text = c.get("/api/export/fish.csv").text
        assert csv_text.startswith("id,pond,round_id")
        assert "seed" in csv_text
