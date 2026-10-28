"""HTTP API. All routes live under /api; the built React app is served for
everything else (see main.py)."""

import csv
import hmac
import io
import json
import time
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .notify import row_to_notification
from .rules import environment as env_rules
from .rules.thresholds import FIXED_KEYS, GROUPS
from .services import DAY, NotFound

router = APIRouter(prefix="/api")

MAX_PHOTO_BYTES = 15 * 1024 * 1024


def svc(request: Request):
    return request.app.state.services


# ------------------------------------------------------------------ models
class PondIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    stocked_at: float
    location: Optional[str] = None
    area_m2: Optional[float] = Field(default=None, ge=0)
    stocked_count: Optional[int] = Field(default=None, ge=0)
    feeding_regime: Optional[str] = None
    notes: Optional[str] = None


class PondPatch(BaseModel):
    name: Optional[str] = None
    stocked_at: Optional[float] = None
    location: Optional[str] = None
    area_m2: Optional[float] = None
    stocked_count: Optional[int] = None
    feeding_regime: Optional[str] = None
    notes: Optional[str] = None
    archived: Optional[int] = None


class ObservationIn(BaseModel):
    algae_seen: bool
    do_ppm: Optional[float] = Field(default=None, ge=0, le=30)
    ph: Optional[float] = Field(default=None, ge=0, le=14)
    ammonia_ppm: Optional[float] = Field(default=None, ge=0)
    nitrate_ppm: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    recorded_by: Optional[str] = None


class RoundIn(BaseModel):
    sampled_at: Optional[float] = None
    capture_condition: Optional[str] = None
    weather: Optional[str] = None
    phone_model: Optional[str] = None
    notes: Optional[str] = None


class RoundPatch(BaseModel):
    capture_condition: Optional[str] = None
    weather: Optional[str] = None
    phone_model: Optional[str] = None
    notes: Optional[str] = None
    technician_health: Optional[str] = None
    technician_readiness: Optional[str] = None


class FishPatch(BaseModel):
    weight_g: Optional[float] = Field(default=None, gt=0)
    length_cm: Optional[float] = Field(default=None, gt=0)
    technician_score: Optional[float] = Field(default=None, ge=1, le=5)


class ContactIn(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""


class CalibrationIn(BaseModel):
    probe_c: float
    reference_c: float
    pond_id: Optional[int] = None
    notes: Optional[str] = None


class FitIn(BaseModel):
    poly_features: list[str] = []


class IngestReading(BaseModel):
    ts: float
    temperature_c: float = Field(ge=-55, le=125)


class IngestIn(BaseModel):
    pond_id: int
    readings: list[IngestReading]


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ------------------------------------------------------------------ system
@router.get("/system")
def system(request: Request):
    s = svc(request)
    app = request.app
    detector = s.detector
    return {
        "demo": app.state.settings.demo,
        "sensor": app.state.monitor.status if app.state.monitor else {"mode": "off"},
        "detector": {"name": detector.name, "is_stub": detector.is_stub},
        "fci_model": {k: s.fci_model().get(k) for k in ("name", "source", "n")},
        "notifications": s.notifier.channel_status(),
        "thresholds": s.thresholds().to_dict(),
        "season": env_rules.season_for(time.time()),
        "server_time": time.time(),
    }


@router.get("/overview")
def overview(request: Request):
    s = svc(request)
    t = s.thresholds()
    ponds = [s.pond_summary(p, t) for p in s.list_ponds()]
    notes = [row_to_notification(r) for r in s.db.query("SELECT * FROM notifications ORDER BY ts DESC LIMIT 8")]
    unread = s.db.scalar("SELECT COUNT(*) FROM notifications WHERE acknowledged=0")
    return {"ponds": ponds, "notifications": notes, "unread": unread}


# ------------------------------------------------------------------- ponds
@router.get("/ponds")
def ponds(request: Request, include_archived: bool = False):
    s = svc(request)
    return [s.pond_summary(p) for p in s.list_ponds(include_archived)]


@router.post("/ponds", status_code=201)
def create_pond(request: Request, body: PondIn):
    s = svc(request)
    pond_id = s.create_pond(body.model_dump())
    return s.pond_summary(s.get_pond(pond_id))


@router.get("/ponds/{pond_id}")
def pond(request: Request, pond_id: int):
    s = svc(request)
    return _guard(lambda: s.pond_summary(s.get_pond(pond_id)))


@router.patch("/ponds/{pond_id}")
def patch_pond(request: Request, pond_id: int, body: PondPatch):
    s = svc(request)
    return _guard(s.update_pond, pond_id, body.model_dump(exclude_unset=True))


@router.get("/ponds/{pond_id}/environment")
def pond_environment(request: Request, pond_id: int, hours: float = 24):
    s = svc(request)
    pond_row = _guard(s.get_pond, pond_id)
    t = s.thresholds()
    now = time.time()
    last = s.db.one("SELECT sampled_at FROM sampling_rounds WHERE pond_id=? ORDER BY sampled_at DESC LIMIT 1",
                    (pond_id,))
    start = last["sampled_at"] if last else max(pond_row["stocked_at"], now - 30 * DAY)
    stress = env_rules.stress_exposure(s.readings_between(pond_id, start, now), start, now, thresholds=t)
    stress["since"] = "last sampling round" if last else "stocking (max 30 days)"
    return {
        "now": s.environment_now(pond_id, t),
        "history": s.temperature_history(pond_id, hours=min(max(hours, 1), 24 * 60)),
        "hours": hours,
        "observations": s.observations(pond_id),
        "stress_since_last_round": stress,
    }


@router.post("/ponds/{pond_id}/observations", status_code=201)
def add_observation(request: Request, pond_id: int, body: ObservationIn):
    s = svc(request)
    _guard(s.add_observation, pond_id, body.model_dump())
    s.evaluate_environment(pond_id)
    return s.environment_now(pond_id)


@router.get("/ponds/{pond_id}/rounds")
def rounds(request: Request, pond_id: int):
    s = svc(request)
    _guard(s.get_pond, pond_id)
    return s.list_rounds(pond_id)


@router.post("/ponds/{pond_id}/rounds", status_code=201)
def create_round(request: Request, pond_id: int, body: RoundIn):
    s = svc(request)
    round_id = _guard(s.create_round, pond_id, body.model_dump())
    return s.round_detail(round_id)


@router.get("/ponds/{pond_id}/growth")
def growth(request: Request, pond_id: int):
    s = svc(request)
    _guard(s.get_pond, pond_id)
    return s.growth_for_pond(pond_id)


# ------------------------------------------------------------------ rounds
@router.get("/rounds/{round_id}")
def round_detail(request: Request, round_id: int):
    return _guard(svc(request).round_detail, round_id)


@router.patch("/rounds/{round_id}")
def patch_round(request: Request, round_id: int, body: RoundPatch):
    return _guard(svc(request).update_round, round_id, body.model_dump(exclude_unset=True))


@router.delete("/rounds/{round_id}", status_code=204)
def delete_round(request: Request, round_id: int):
    _guard(svc(request).delete_round, round_id)


@router.post("/rounds/{round_id}/complete")
def complete_round(request: Request, round_id: int):
    return _guard(svc(request).complete_round, round_id)


@router.post("/rounds/{round_id}/fish", status_code=201)
async def add_fish(
    request: Request,
    round_id: int,
    weight_g: float = Form(..., gt=0, le=5000),
    length_cm: float = Form(..., gt=0, le=80),
    technician_score: Optional[float] = Form(None, ge=1, le=5),
    photo: Optional[UploadFile] = File(None),
):
    data = None
    name = None
    if photo is not None and photo.filename:
        data = await photo.read()
        name = photo.filename
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Photo is larger than 15 MB.")
        if not data:
            data = None
    return _guard(svc(request).add_fish, round_id, weight_g, length_cm, technician_score, data, name)


@router.patch("/fish/{fish_id}")
def patch_fish(request: Request, fish_id: int, body: FishPatch):
    return _guard(svc(request).update_fish, fish_id, body.model_dump(exclude_unset=True))


@router.delete("/fish/{fish_id}", status_code=204)
def delete_fish(request: Request, fish_id: int):
    _guard(svc(request).delete_fish, fish_id)


@router.get("/photos/{name}")
def photo(request: Request, name: str):
    uploads = request.app.state.settings.uploads_dir.resolve()
    path = (uploads / name).resolve()
    if path.parent != uploads or not path.is_file():
        raise HTTPException(404, "Photo not found")
    return FileResponse(path)


# ----------------------------------------------------------- notifications
@router.get("/notifications")
def notifications(request: Request, limit: int = 100):
    s = svc(request)
    rows = s.db.query("SELECT * FROM notifications ORDER BY ts DESC LIMIT ?", (min(limit, 500),))
    return {"notifications": [row_to_notification(r) for r in rows], "channel": s.notifier.channel_status()}


@router.post("/notifications/{note_id}/ack")
def ack(request: Request, note_id: int):
    svc(request).db.execute("UPDATE notifications SET acknowledged=1 WHERE id=?", (note_id,))
    return {"ok": True}


@router.post("/notifications/ack-all")
def ack_all(request: Request):
    svc(request).db.execute("UPDATE notifications SET acknowledged=1 WHERE acknowledged=0")
    return {"ok": True}


# ---------------------------------------------------------------- settings
@router.get("/settings/thresholds")
def get_thresholds(request: Request):
    return {"values": svc(request).thresholds().to_dict(), "groups": GROUPS, "fixed": list(FIXED_KEYS)}


@router.put("/settings/thresholds")
def put_thresholds(request: Request, body: dict):
    s = svc(request)
    body = {k: v for k, v in body.items() if k not in FIXED_KEYS}
    t = _guard(s.set_thresholds, body)
    return {"values": t.to_dict(), "groups": GROUPS, "fixed": list(FIXED_KEYS)}


@router.get("/settings/contact")
def get_contact(request: Request):
    return svc(request).notifier.channel_status()


@router.put("/settings/contact")
def put_contact(request: Request, body: ContactIn):
    s = svc(request)
    s.db.set_setting("contact", body.model_dump())
    return s.notifier.channel_status()


@router.post("/notifications/test")
def test_notification(request: Request):
    s = svc(request)
    note_id = s.notifier.notify("system", "info", "Test notification",
                                "This is a test alert from Tilapiers settings.")
    row = s.db.one("SELECT * FROM notifications WHERE id=?", (note_id,))
    return row_to_notification(row)


# -------------------------------------------------------------- evaluation
@router.get("/evaluation")
def evaluation(request: Request):
    return svc(request).evaluation()


@router.post("/evaluation/fit")
def fit(request: Request, body: FitIn):
    return _guard(svc(request).fit_fci, body.poly_features)


@router.post("/evaluation/reset-model")
def reset_model(request: Request):
    svc(request).reset_fci_model()
    return {"ok": True}


@router.post("/calibrations", status_code=201)
def add_calibration(request: Request, body: CalibrationIn):
    svc(request).add_calibration(body.model_dump())
    return svc(request).evaluation()["probe_calibration"]


# ------------------------------------------------------------------ ingest
@router.post("/ingest/temperature")
def ingest(request: Request, body: IngestIn, x_device_token: Optional[str] = Header(None)):
    """Batch upload from a networked probe that buffers readings while offline."""
    token = request.app.state.settings.ingest_token
    if not token:
        raise HTTPException(503, "Ingest disabled: set TILAPIERS_INGEST_TOKEN.")
    if not x_device_token or not hmac.compare_digest(x_device_token, token):
        raise HTTPException(401, "Invalid device token")
    s = svc(request)
    _guard(s.get_pond, body.pond_id)
    n = s.record_readings(body.pond_id, [r.model_dump() for r in body.readings], "probe-http")
    s.evaluate_environment(body.pond_id)
    return {"stored": n}


# ------------------------------------------------------------------ export
EXPORTS = {
    "temperature": "SELECT r.id, p.name AS pond, r.ts, r.temperature_c, r.source FROM temperature_readings r "
                   "JOIN ponds p ON p.id=r.pond_id ORDER BY r.ts",
    "observations": "SELECT o.*, p.name AS pond FROM observations o JOIN ponds p ON p.id=o.pond_id ORDER BY o.ts",
    "rounds": "SELECT r.id, p.name AS pond, r.sampled_at, r.days_of_culture, r.capture_condition, r.time_of_day, "
              "r.weather, r.phone_model, r.status, r.technician_health, r.technician_readiness, r.snapshot_json "
              "FROM sampling_rounds r JOIN ponds p ON p.id=r.pond_id ORDER BY r.sampled_at",
    "fish": "SELECT f.id, p.name AS pond, r.id AS round_id, r.days_of_culture, r.capture_condition, f.seq, "
            "f.weight_g, f.length_cm, f.image_length_cm, f.condition_factor, f.gill_color_index, "
            "f.skin_color_index, f.fin_integrity, f.eye_clarity, f.body_shape, f.fci, f.flagged, "
            "f.technician_score, f.analysis_source, f.detection_json FROM fish f "
            "JOIN sampling_rounds r ON r.id=f.round_id JOIN ponds p ON p.id=r.pond_id ORDER BY r.sampled_at, f.seq",
    "notifications": "SELECT * FROM notifications ORDER BY ts",
}
TS_COLS = {"ts", "sampled_at"}


@router.get("/export/{table}.csv")
def export(request: Request, table: str):
    if table not in EXPORTS:
        raise HTTPException(404, "Unknown export")
    rows = svc(request).db.query(EXPORTS[table])
    buf = io.StringIO()
    if rows:
        headers = list(rows[0].keys())
        if table == "fish":
            headers = [h for h in headers if h != "detection_json"] + ["detector"]
        writer = csv.writer(buf)
        writer.writerow(headers)
        from .services import fmt_ts

        for r in rows:
            if table == "fish":
                det = json.loads(r.pop("detection_json") or "null")
                r["detector"] = (det or {}).get("model") or r["analysis_source"]
            writer.writerow([fmt_ts(r[h]) if h in TS_COLS else r[h] for h in headers])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="tilapiers_{table}.csv"'})
