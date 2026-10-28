"""HTTP API under /api. Session cookie auth with three roles (paper Table 5)."""

import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import auth
from .services import Invalid, NotFound
from .vision import board_sheet

router = APIRouter(prefix="/api")

MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024
CARETAKER, TECH, ADMIN = "caretaker", "technician", "admin"


def svc(request: Request):
    return request.app.state.services


def current_user(request: Request):
    uid = request.app.state.sessions.read(request.cookies.get(auth.COOKIE))
    if not uid:
        raise HTTPException(401, "Please log in.")
    try:
        user = svc(request).get_user(uid)
    except NotFound:
        raise HTTPException(401, "Please log in.")
    if not user["active"]:
        raise HTTPException(401, "This account is deactivated.")
    return user


def require(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role cannot do this.")
        return user
    return dep


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(404, str(exc))
    except Invalid as exc:
        raise HTTPException(400, str(exc))


# ------------------------------------------------------------------ auth / profile
class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    user = svc(request).authenticate(body.username, body.password)
    if not user:
        time.sleep(0.4)  # slow down guessing
        raise HTTPException(401, "Wrong username or password.")
    response.set_cookie(auth.COOKIE, request.app.state.sessions.issue(user["id"]), max_age=auth.MAX_AGE_S,
                        httponly=True, samesite="lax")
    return user


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/profile/password")
def change_password(body: PasswordIn, request: Request, user=Depends(current_user)):
    call(svc(request).change_password, user["id"], body.current_password, body.new_password)
    return {"ok": True}


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=80)


@router.patch("/profile")
def update_profile(body: ProfileIn, request: Request, user=Depends(current_user)):
    return call(svc(request).update_user, user["id"], {"full_name": body.full_name}, user["id"])


@router.get("/system")
def system(request: Request):
    """Public: what the login page and the footer need."""
    s = request.app.state
    return {"demo": s.settings.demo, "screener": s.services.screener.info(),
            "segmentation": "yolo-seg" if s.services.seg_model is not None else "classical (interim)",
            "demo_accounts": [{"username": u, "password": u + "123", "role": r}
                              for u, r in (("caretaker", "caretaker"), ("technician", "technician"),
                                           ("admin", "admin"))] if s.settings.demo else []}


# ------------------------------------------------------------------ users (admin)
class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str
    role: str
    full_name: Optional[str] = None


class UserPatch(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


@router.get("/users")
def list_users(request: Request, _=Depends(require(ADMIN))):
    return svc(request).list_users()


@router.post("/users", status_code=201)
def create_user(body: UserIn, request: Request, _=Depends(require(ADMIN))):
    return call(svc(request).create_user, body.model_dump())


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserPatch, request: Request, user=Depends(require(ADMIN))):
    return call(svc(request).update_user, uid, body.model_dump(exclude_none=True), user["id"])


# ------------------------------------------------------------------ ponds
class PondIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    location: Optional[str] = None
    setup: Optional[str] = None
    stocked_at: Optional[str] = None
    stocked_count: Optional[int] = Field(default=None, ge=0)
    archived: Optional[bool] = None


class PondPatch(PondIn):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)


@router.get("/ponds")
def ponds(request: Request, include_archived: bool = False, _=Depends(current_user)):
    return svc(request).list_ponds(include_archived)


@router.post("/ponds", status_code=201)
def create_pond(body: PondIn, request: Request, _=Depends(require(ADMIN))):
    return call(svc(request).create_pond, body.model_dump(exclude_none=True))


@router.patch("/ponds/{pond_id}")
def update_pond(pond_id: int, body: PondPatch, request: Request, _=Depends(require(ADMIN))):
    return call(svc(request).update_pond, pond_id, body.model_dump(exclude_unset=True))


@router.get("/ponds/{pond_id}")
def pond_overview(pond_id: int, request: Request, _=Depends(current_user)):
    return call(svc(request).pond_overview, pond_id)


@router.get("/dashboard")
def dashboard(request: Request, _=Depends(current_user)):
    return svc(request).dashboard()


# ------------------------------------------------------------------ rounds and fish
class RoundIn(BaseModel):
    pond_id: int
    sampled_at: Optional[str] = None
    days_of_culture: Optional[float] = Field(default=None, ge=0)
    fish_count_n: Optional[int] = Field(default=None, ge=0)
    board_mode: bool = True
    capture_condition: Optional[str] = None
    notes: Optional[str] = None


class RoundPatch(BaseModel):
    sampled_at: Optional[str] = None
    days_of_culture: Optional[float] = Field(default=None, ge=0)
    fish_count_n: Optional[int] = Field(default=None, ge=0)
    board_mode: Optional[bool] = None
    capture_condition: Optional[str] = None
    notes: Optional[str] = None


SAMPLERS = (CARETAKER, ADMIN)


@router.post("/rounds", status_code=201)
def create_round(body: RoundIn, request: Request, user=Depends(require(*SAMPLERS))):
    data = body.model_dump()
    return call(svc(request).create_round, data.pop("pond_id"), data, user["username"])


@router.get("/rounds/{round_id}")
def get_round(round_id: int, request: Request, _=Depends(current_user)):
    return call(svc(request).get_round, round_id)


@router.patch("/rounds/{round_id}")
def update_round(round_id: int, body: RoundPatch, request: Request, _=Depends(require(*SAMPLERS))):
    return call(svc(request).update_round, round_id, body.model_dump(exclude_unset=True))


@router.delete("/rounds/{round_id}", status_code=204)
def delete_round(round_id: int, request: Request, _=Depends(require(*SAMPLERS))):
    call(svc(request).delete_round, round_id)
    return Response(status_code=204)


@router.post("/rounds/{round_id}/complete")
def complete_round(round_id: int, request: Request, _=Depends(require(*SAMPLERS))):
    return call(svc(request).complete_round, round_id)


class FishIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=20)
    scale_weight_g: Optional[float] = Field(default=None, gt=0)
    ruler_length_cm: Optional[float] = Field(default=None, gt=0)


@router.post("/rounds/{round_id}/fish", status_code=201)
def add_fish(round_id: int, body: FishIn, request: Request, _=Depends(require(*SAMPLERS))):
    return call(svc(request).add_fish, round_id, body.model_dump(exclude_none=True))


@router.patch("/fish/{fish_id}")
def update_fish(fish_id: int, body: FishIn, request: Request, _=Depends(require(*SAMPLERS))):
    return call(svc(request).update_fish, fish_id, body.model_dump(exclude_unset=True))


@router.delete("/fish/{fish_id}", status_code=204)
def delete_fish(fish_id: int, request: Request, _=Depends(require(*SAMPLERS))):
    call(svc(request).delete_fish, fish_id)
    return Response(status_code=204)


@router.post("/fish/{fish_id}/photos/{side}")
async def upload_photo(fish_id: int, side: str, request: Request, file: UploadFile = File(...),
                       _=Depends(require(*SAMPLERS))):
    data = await file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Photo is larger than 20 MB.")
    return call(svc(request).upload_photo, fish_id, side, data)


@router.get("/photos/{photo_id}/{kind}")
def photo(photo_id: int, kind: str, request: Request, _=Depends(current_user)):
    if kind not in ("raw", "annotated"):
        raise HTTPException(404, "Not found")
    return FileResponse(call(svc(request).photo_file, photo_id, kind), media_type="image/jpeg")


# ------------------------------------------------------------------ technician
class ReviewIn(BaseModel):
    signs: str
    note: Optional[str] = Field(default=None, max_length=500)


class AssessmentIn(BaseModel):
    tech_health: Optional[str] = None
    tech_readiness: Optional[str] = None


REVIEWERS = (TECH, ADMIN)


@router.get("/review/queue")
def review_queue(request: Request, _=Depends(require(*REVIEWERS))):
    return svc(request).review_queue()


@router.post("/fish/{fish_id}/review")
def review_fish(fish_id: int, body: ReviewIn, request: Request, user=Depends(require(*REVIEWERS))):
    return call(svc(request).review_fish, fish_id, body.signs, body.note, user["username"])


@router.post("/rounds/{round_id}/assessment")
def round_assessment(round_id: int, body: AssessmentIn, request: Request, user=Depends(require(*REVIEWERS))):
    return call(svc(request).set_round_assessment, round_id, body.tech_health, body.tech_readiness,
                user["username"])


# ------------------------------------------------------------------ maintenance
class ThresholdsIn(BaseModel):
    values: dict = {}
    confirmed: Optional[bool] = None


@router.get("/thresholds")
def thresholds(request: Request, _=Depends(current_user)):
    return svc(request).thresholds_meta()


@router.put("/thresholds")
def put_thresholds(body: ThresholdsIn, request: Request, user=Depends(require(ADMIN))):
    return call(svc(request).update_thresholds, body.values, user["username"], body.confirmed)


@router.get("/weight-model")
def weight_model(request: Request, _=Depends(current_user)):
    return svc(request).weight_model_info()


class FitIn(BaseModel):
    include_demo: bool = False


@router.post("/weight-model/fit")
def fit_weight_model(body: FitIn, request: Request, user=Depends(require(ADMIN))):
    return call(svc(request).fit_weight_model, user["username"], body.include_demo)


@router.post("/weight-model/reset")
def reset_weight_model(request: Request, _=Depends(require(ADMIN))):
    return svc(request).reset_weight_model()


@router.get("/backup")
def backup(request: Request, _=Depends(require(ADMIN))):
    stamp = time.strftime("%Y%m%d-%H%M")
    return Response(svc(request).backup_zip(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="tilapiers-backup-{stamp}.zip"'})


@router.post("/restore")
async def restore(request: Request, file: UploadFile = File(...), _=Depends(require(ADMIN))):
    data = await file.read(MAX_BACKUP_BYTES + 1)
    if len(data) > MAX_BACKUP_BYTES:
        raise HTTPException(413, "Backup is too large.")
    call(svc(request).restore_zip, data)
    return {"ok": True}


@router.get("/board.png")
def board_png(request: Request, _=Depends(current_user)):
    t = svc(request).thresholds()
    return Response(board_sheet.render_png(t.board_width_cm, t.board_height_cm), media_type="image/png")


@router.get("/board.pdf")
def board_pdf(request: Request, _=Depends(current_user)):
    t = svc(request).thresholds()
    return Response(board_sheet.render_pdf(t.board_width_cm, t.board_height_cm), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="tilapiers-sampling-board.pdf"'})


# ------------------------------------------------------------------ evaluation / export
@router.get("/evaluation")
def evaluation(request: Request, include_demo: bool = True, _=Depends(require(TECH, ADMIN))):
    return svc(request).evaluation(include_demo)


@router.get("/benchmarks/{name}")
def benchmark_image(name: str, request: Request, _=Depends(current_user)):
    from .benchmarks import IMAGES

    if name not in IMAGES:
        raise HTTPException(404, "Not found")
    path = request.app.state.settings.benchmarks_dir / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@router.get("/export/{kind}.csv")
def export(kind: str, request: Request, _=Depends(require(TECH, ADMIN))):
    text = call(svc(request).export_csv, kind)
    return Response(text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="tilapiers-{kind}.csv"'})


# ------------------------------------------------------------------ content (FAQs, About Us)
class ContentIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body_md: str = Field(max_length=20000)


@router.get("/content")
def list_content(request: Request, _=Depends(current_user)):
    return svc(request).list_content()


@router.get("/content/{key}")
def get_content(key: str, request: Request, _=Depends(current_user)):
    return call(svc(request).get_content, key)


@router.put("/content/{key}")
def put_content(key: str, body: ContentIn, request: Request, _=Depends(require(ADMIN))):
    return svc(request).set_content(key, body.title, body.body_md)
