import cv2
import pytest
from fakes import FakeScreener
from fastapi.testclient import TestClient
from synth import board_photo

from tilapiers.main import create_app


@pytest.fixture
def app_client(settings):
    app = create_app(settings, screener=FakeScreener("TiLV", 0.8))
    with TestClient(app) as c:
        svc = app.state.services
        svc.create_user({"username": "care", "password": "care123", "role": "caretaker"})
        svc.create_user({"username": "tech", "password": "tech123", "role": "technician"})
        svc.update_thresholds({"board_width_cm": 38, "board_height_cm": 26}, "test")
        yield c


def login(c, user, pw):
    r = c.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_and_me(app_client):
    assert login(app_client, "care", "care123")["role"] == "caretaker"
    assert app_client.get("/api/auth/me").json()["username"] == "care"


def test_bad_login_rejected(app_client):
    r = app_client.post("/api/auth/login", json={"username": "care", "password": "nope"})
    assert r.status_code == 401


def test_anonymous_gets_401(app_client):
    assert app_client.get("/api/ponds").status_code == 401


def test_caretaker_cannot_change_cutoffs(app_client):
    login(app_client, "care", "care123")
    assert app_client.put("/api/thresholds", json={"values": {"target_weight_g": 1}}).status_code == 403
    assert app_client.get("/api/users").status_code == 403


def test_technician_cannot_create_rounds(app_client):
    login(app_client, "admin", "admin123")
    pond = app_client.post("/api/ponds", json={"name": "P"}).json()
    login(app_client, "tech", "tech123")
    assert app_client.post("/api/rounds", json={"pond_id": pond["id"]}).status_code == 403


def test_full_round_flow(app_client):
    login(app_client, "admin", "admin123")
    pond = app_client.post("/api/ponds", json={"name": "Pond A", "stocked_count": 500}).json()
    login(app_client, "care", "care123")
    rnd = app_client.post("/api/rounds", json={"pond_id": pond["id"], "days_of_culture": 90,
                                               "board_mode": True}).json()
    fish = app_client.post(f"/api/rounds/{rnd['id']}/fish", json={}).json()
    jpg = cv2.imencode(".jpg", board_photo())[1].tobytes()
    r = app_client.post(f"/api/fish/{fish['id']}/photos/A", files={"file": ("a.jpg", jpg, "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["photo"]["ok"] and body["fish"]["cls"] == "TiLV"
    assert app_client.get(body["photo"]["annotated_url"]).status_code == 200
    app_client.patch(f"/api/fish/{fish['id']}", json={"scale_weight_g": 120, "ruler_length_cm": 20.2})
    done = app_client.post(f"/api/rounds/{rnd['id']}/complete").json()
    assert done["status"] == "completed"
    assert done["assessment"]["health"]["status"] == "Refer to technician"
    login(app_client, "tech", "tech123")
    q = app_client.get("/api/review/queue").json()
    assert q["fish"][0]["id"] == fish["id"]
    r = app_client.post(f"/api/fish/{fish['id']}/review", json={"signs": "tilv", "note": "eye cloudy"})
    assert r.status_code == 200
    r = app_client.post(f"/api/rounds/{rnd['id']}/assessment",
                        json={"tech_health": "Refer to technician", "tech_readiness": "Not Ready"})
    assert r.status_code == 200
    ev = app_client.get("/api/evaluation").json()
    assert ev["health"]["n"] == 1 and ev["health"]["accuracy"] == 1.0


def test_board_sheet_downloads(app_client):
    login(app_client, "care", "care123")
    r = app_client.get("/api/board.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_backup_restore_round_trip(app_client):
    login(app_client, "admin", "admin123")
    app_client.post("/api/ponds", json={"name": "Keep me"})
    blob = app_client.get("/api/backup").content
    app_client.post("/api/ponds", json={"name": "After backup"})
    r = app_client.post("/api/restore", files={"file": ("b.zip", blob, "application/zip")})
    assert r.status_code == 200, r.text
    names = [p["name"] for p in app_client.get("/api/ponds").json()]
    assert names == ["Keep me"]
