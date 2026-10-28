"""Domain services: sampling rounds, per-fish processing, statuses, maintenance,
evaluation and backups, on top of the pure rules and the database."""

import csv
import io
import json
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import date, datetime
from pathlib import Path

import cv2

from . import auth
from .rules import evaluation as ev
from .rules import harvest, health, weight
from .rules.thresholds import FRACTIONS, GROUPS, LABELS, MIN_INT, POSITIVE, Thresholds
from .vision import pipeline, quality

SIDES = ("A", "B")
TECH_SIGNS = ("none", "aeromonas", "tilv", "other")
HEALTH_LABELS = [health.NORMAL, health.WATCH, health.REFER]
READY_LABELS = [harvest.NOT_READY, harvest.APPROACHING, harvest.READY]


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


def _today():
    return date.today().isoformat()


def _days_between(start_iso, end_iso):
    try:
        return (datetime.fromisoformat(end_iso[:10]) - datetime.fromisoformat(start_iso[:10])).days
    except (TypeError, ValueError):
        return None


class Services:
    def __init__(self, db, settings, screener, seg_model=None):
        self.db = db
        self.settings = settings
        self.screener = screener
        self.seg_model = seg_model
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ cutoffs
    def thresholds(self):
        return Thresholds.from_dict(self.db.get_setting("thresholds", {}))

    def thresholds_meta(self):
        hist = self.db.all("SELECT * FROM threshold_history ORDER BY id DESC LIMIT 100")
        for h in hist:
            h["changes"] = json.loads(h.pop("changes_json"))
            h["confirmed"] = bool(h["confirmed"])
        return {"values": self.thresholds().to_dict(), "defaults": Thresholds().to_dict(), "groups": GROUPS,
                "labels": LABELS, "confirmed": bool(self.db.get_setting("thresholds_confirmed", False)),
                "history": hist}

    def update_thresholds(self, changes, user, confirmed=None):
        old = self.thresholds()
        merged = {**old.to_dict(), **{k: v for k, v in (changes or {}).items() if k in old.to_dict()}}
        try:
            new = Thresholds.from_dict(merged)
        except (TypeError, ValueError) as exc:
            raise Invalid("Every cutoff must be a number (whole numbers for round and fish counts).") from exc
        for k in FRACTIONS:
            if not 0 <= getattr(new, k) <= 1:
                raise Invalid(f"{LABELS[k]} must be between 0 and 1.")
        for k in POSITIVE:
            if getattr(new, k) <= 0:
                raise Invalid(f"{LABELS[k]} must be above 0.")
        for k, low in MIN_INT.items():
            if getattr(new, k) < low:
                raise Invalid(f"{LABELS[k]} must be at least {low}.")
        if new.culture_days_min > new.culture_days_max:
            raise Invalid("The usual culture period must start before it ends.")
        if new.k_min >= new.k_max:
            raise Invalid("K lower limit must be below the upper limit.")
        if new.approaching_share > new.ready_share:
            raise Invalid("The Approaching share cannot be above the Ready share.")
        if new.pond_watch_share > new.pond_refer_share:
            raise Invalid("The pond Watch share cannot be above the pond Refer share.")
        if min(new.board_width_cm, new.board_height_cm) <= 0:
            raise Invalid("Board size must be positive.")
        diff = {k: [getattr(old, k), getattr(new, k)] for k in merged if getattr(old, k) != getattr(new, k)}
        self.db.set_setting("thresholds", new.to_dict())
        if confirmed is not None:
            self.db.set_setting("thresholds_confirmed", bool(confirmed))
        if diff or confirmed is not None:
            self.db.insert("threshold_history", {"ts": time.time(), "user": user, "changes_json": json.dumps(diff),
                                                 "confirmed": int(bool(confirmed))})
        self.refresh_drafts()
        return self.thresholds_meta()

    # ------------------------------------------------------------------ users
    def create_user(self, data):
        username = (data.get("username") or "").strip().lower()
        if not username or len(data.get("password") or "") < 6:
            raise Invalid("Username is required and the password needs at least 6 characters.")
        if data.get("role") not in auth.ROLES:
            raise Invalid("Role must be caretaker, technician or admin.")
        if self.db.one("SELECT id FROM users WHERE username = ?", (username,)):
            raise Invalid("That username is taken.")
        uid = self.db.insert("users", {"username": username, "full_name": data.get("full_name") or username,
                                       "role": data["role"], "pw_hash": auth.hash_password(data["password"])})
        return self.get_user(uid)

    def get_user(self, uid):
        u = self.db.one("SELECT id, username, full_name, role, active, created_at FROM users WHERE id = ?", (uid,))
        if not u:
            raise NotFound("User not found")
        u["active"] = bool(u["active"])
        return u

    def list_users(self):
        return [self.get_user(u["id"]) for u in self.db.all("SELECT id FROM users ORDER BY role, username")]

    def authenticate(self, username, password):
        u = self.db.one("SELECT * FROM users WHERE username = ? AND active = 1", ((username or "").strip().lower(),))
        if not u or not auth.verify_password(password or "", u["pw_hash"]):
            return None
        return self.get_user(u["id"])

    def update_user(self, uid, data, acting_user_id):
        user = self.get_user(uid)
        values = {}
        if "full_name" in data:
            values["full_name"] = data["full_name"]
        if "role" in data:
            if data["role"] not in auth.ROLES:
                raise Invalid("Unknown role.")
            values["role"] = data["role"]
        if "active" in data:
            values["active"] = int(bool(data["active"]))
        if data.get("password"):
            if len(data["password"]) < 6:
                raise Invalid("The password needs at least 6 characters.")
            values["pw_hash"] = auth.hash_password(data["password"])
        demoting = user["role"] == "admin" and (values.get("role", "admin") != "admin" or values.get("active") == 0)
        if demoting:
            admins = self.db.one("SELECT COUNT(*) n FROM users WHERE role = 'admin' AND active = 1")["n"]
            if admins <= 1:
                raise Invalid("At least one active administrator must remain.")
        if uid == acting_user_id and values.get("active") == 0:
            raise Invalid("You cannot deactivate your own account.")
        self.db.update("users", uid, values)
        return self.get_user(uid)

    def change_password(self, uid, old, new):
        u = self.db.one("SELECT * FROM users WHERE id = ?", (uid,))
        if not u or not auth.verify_password(old or "", u["pw_hash"]):
            raise Invalid("Current password is incorrect.")
        if len(new or "") < 6:
            raise Invalid("The new password needs at least 6 characters.")
        self.db.update("users", uid, {"pw_hash": auth.hash_password(new)})

    # ------------------------------------------------------------------ ponds
    POND_FIELDS = ("name", "location", "setup", "stocked_at", "stocked_count", "archived")

    def create_pond(self, data, source="real"):
        if not (data.get("name") or "").strip():
            raise Invalid("Pond name is required.")
        values = {k: data.get(k) for k in self.POND_FIELDS if k in data}
        values["archived"] = int(bool(values.get("archived", 0)))
        return self.get_pond(self.db.insert("ponds", {**values, "source": source}))

    def update_pond(self, pond_id, data):
        self.get_pond(pond_id)
        values = {k: data[k] for k in self.POND_FIELDS if k in data}
        if "archived" in values:
            values["archived"] = int(bool(values["archived"]))
        self.db.update("ponds", pond_id, values)
        return self.get_pond(pond_id)

    def get_pond(self, pond_id):
        p = self.db.one("SELECT * FROM ponds WHERE id = ?", (pond_id,))
        if not p:
            raise NotFound("Pond not found")
        p["archived"] = bool(p["archived"])
        return p

    def list_ponds(self, include_archived=False):
        sql = "SELECT id FROM ponds" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY name"
        return [self.get_pond(r["id"]) for r in self.db.all(sql)]

    # ------------------------------------------------------------------ rounds
    def create_round(self, pond_id, data, user, source="real"):
        pond = self.get_pond(pond_id)
        sampled_at = data.get("sampled_at") or _today()
        doc = data.get("days_of_culture")
        if doc in (None, "") and pond.get("stocked_at"):
            doc = _days_between(pond["stocked_at"], sampled_at)
        rid = self.db.insert("rounds", {
            "pond_id": pond_id, "sampled_at": sampled_at,
            "days_of_culture": float(doc) if doc not in (None, "") else None,
            "fish_count_n": data.get("fish_count_n") or pond.get("stocked_count"),
            "board_mode": int(bool(data.get("board_mode", True))),
            "capture_condition": data.get("capture_condition"), "notes": data.get("notes"),
            "created_by": user, "source": source})
        return self.get_round(rid)

    def _round_row(self, round_id):
        r = self.db.one("SELECT r.*, p.name AS pond_name FROM rounds r JOIN ponds p ON p.id = r.pond_id "
                        "WHERE r.id = ?", (round_id,))
        if not r:
            raise NotFound("Sampling round not found")
        r["board_mode"] = bool(r["board_mode"])
        return r

    def get_round(self, round_id):
        r = self._round_row(round_id)
        snap = r.pop("snapshot_json")
        fish = self.db.all("SELECT * FROM fish WHERE round_id = ? ORDER BY id", (round_id,))
        r["fish"] = [self._fish_view(f) for f in fish]
        r["assessment"] = json.loads(snap) if snap else self.round_assessment(round_id)
        return r

    def update_round(self, round_id, data):
        r = self._round_row(round_id)
        if r["status"] != "draft":
            raise Invalid("A completed round cannot be edited.")
        values = {k: data[k] for k in ("sampled_at", "days_of_culture", "fish_count_n", "capture_condition", "notes")
                  if k in data}
        if "board_mode" in data:
            values["board_mode"] = int(bool(data["board_mode"]))
        self.db.update("rounds", round_id, values)
        if "board_mode" in data:
            for f in self.db.all("SELECT id FROM fish WHERE round_id = ?", (round_id,)):
                self.reprocess_fish(f["id"])
        return self.get_round(round_id)

    def delete_round(self, round_id):
        r = self._round_row(round_id)
        if r["status"] != "draft":
            raise Invalid("Only a draft round can be deleted.")
        shutil.rmtree(self._round_dir(round_id), ignore_errors=True)
        self.db.run("DELETE FROM rounds WHERE id = ?", (round_id,))

    def complete_round(self, round_id):
        r = self._round_row(round_id)
        if r["status"] != "draft":
            raise Invalid("This round is already completed.")
        assessment = self.round_assessment(round_id)
        self.db.update("rounds", round_id, {"status": "completed", "completed_at": time.time(),
                                            "snapshot_json": json.dumps(assessment)})
        return self.get_round(round_id)

    def set_round_assessment(self, round_id, tech_health, tech_readiness, user):
        self._round_row(round_id)
        if tech_health and tech_health not in HEALTH_LABELS:
            raise Invalid("Unknown health status.")
        if tech_readiness and tech_readiness not in READY_LABELS:
            raise Invalid("Unknown readiness status.")
        self.db.update("rounds", round_id, {"tech_health": tech_health or None,
                                            "tech_readiness": tech_readiness or None, "tech_by": user})
        return self.get_round(round_id)

    # ------------------------------------------------------------------ fish
    def add_fish(self, round_id, data=None, source="real"):
        r = self._round_row(round_id)
        if r["status"] != "draft":
            raise Invalid("Fish can only be added to a draft round.")
        data = data or {}
        n = self.db.one("SELECT COUNT(*) n FROM fish WHERE round_id = ?", (round_id,))["n"]
        fid = self.db.insert("fish", {"round_id": round_id, "code": data.get("code") or f"F{n + 1:02d}",
                                      "scale_weight_g": data.get("scale_weight_g"),
                                      "ruler_length_cm": data.get("ruler_length_cm"), "source": source,
                                      "status": health.UNSCREENED})
        return self.get_fish(fid)

    def get_fish(self, fish_id):
        f = self.db.one("SELECT * FROM fish WHERE id = ?", (fish_id,))
        if not f:
            raise NotFound("Fish not found")
        return self._fish_view(f)

    def update_fish(self, fish_id, data):
        f = self.db.one("SELECT f.*, r.status AS round_status FROM fish f JOIN rounds r ON r.id = f.round_id "
                        "WHERE f.id = ?", (fish_id,))
        if not f:
            raise NotFound("Fish not found")
        if f["round_status"] != "draft":
            raise Invalid("A completed round cannot be edited.")
        values = {}
        for k in ("code", "scale_weight_g", "ruler_length_cm"):
            if k in data:
                v = data[k]
                if k != "code" and v not in (None, ""):
                    v = float(v)
                    if v <= 0:
                        raise Invalid("Weight and length must be positive.")
                values[k] = None if v == "" else v
        self.db.update("fish", fish_id, values)
        return self.get_fish(fish_id)

    def delete_fish(self, fish_id):
        f = self.db.one("SELECT f.id, r.status FROM fish f JOIN rounds r ON r.id = f.round_id WHERE f.id = ?",
                        (fish_id,))
        if not f:
            raise NotFound("Fish not found")
        if f["status"] != "draft":
            raise Invalid("A completed round cannot be edited.")
        self.db.run("DELETE FROM fish WHERE id = ?", (fish_id,))

    def _fish_view(self, f):
        f = dict(f)
        f["reasons"] = json.loads(f.pop("reasons_json") or "[]")
        photos = self.db.all("SELECT * FROM photos WHERE fish_id = ? AND current = 1 ORDER BY side", (f["id"],))
        f["photos"] = [self._photo_view(p) for p in photos]
        return f

    @staticmethod
    def _photo_view(p):
        res = json.loads(p.get("result_json") or "{}")
        return {"id": p["id"], "side": p["side"], "ok": bool(p["ok"]), "reasons": res.get("reasons", []),
                "top": res.get("top"), "length_cm": res.get("length_cm"), "quality": res.get("quality"),
                "board": res.get("board"), "outline_method": (res.get("outline") or {}).get("method"),
                "url": f"/api/photos/{p['id']}/raw",
                "annotated_url": f"/api/photos/{p['id']}/annotated" if p.get("annotated_path") else None}

    def _round_dir(self, round_id):
        d = self.settings.uploads_dir / f"round_{round_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def upload_photo(self, fish_id, side, data):
        side = (side or "").upper()
        if side not in SIDES:
            raise Invalid("Side must be A or B.")
        f = self.db.one("SELECT * FROM fish WHERE id = ?", (fish_id,))
        if not f:
            raise NotFound("Fish not found")
        r = self._round_row(f["round_id"])
        if r["status"] != "draft":
            raise Invalid("A completed round cannot be edited.")
        try:
            img = quality.load(data)
        except Exception as exc:
            raise Invalid("That file is not a readable photo.") from exc
        stamp = int(time.time() * 1000)
        d = self._round_dir(r["id"])
        raw = d / f"fish{fish_id}_{side}_{stamp}.jpg"
        ann = d / f"fish{fish_id}_{side}_{stamp}_annotated.jpg"
        cv2.imwrite(str(raw), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        result = pipeline.process_photo(img, r["board_mode"], self.thresholds(), self.screener, self.seg_model, ann)
        self.db.run("UPDATE photos SET current = 0 WHERE fish_id = ? AND side = ?", (fish_id, side))
        pid = self.db.insert("photos", {"fish_id": fish_id, "side": side, "path": str(raw),
                                        "annotated_path": str(ann) if result["annotated"] else None,
                                        "ok": int(result["ok"]), "result_json": json.dumps(result)})
        fish = self.reprocess_fish(fish_id)
        photo = self._photo_view(self.db.one("SELECT * FROM photos WHERE id = ?", (pid,)))
        return {"photo": photo, "fish": fish}

    def reprocess_fish(self, fish_id):
        """Re-run the pipeline over the stored photos (after a board-mode or cutoff change)."""
        f = self.db.one("SELECT * FROM fish WHERE id = ?", (fish_id,))
        photos = self.db.all("SELECT * FROM photos WHERE fish_id = ? AND current = 1", (fish_id,))
        results = [json.loads(p["result_json"]) for p in photos]
        merged = pipeline.merge_sides(results)
        self.db.update("fish", fish_id, {"cls": merged["cls"], "conf": merged["conf"], "sides": merged["sides"],
                                         "length_cm": merged["length_cm"], "area_cm2": merged["area_cm2"]})
        if f["source"] == "real":
            self._derive(fish_id)
        return self.get_fish(fish_id)

    def _derive(self, fish_id, t=None, model=None):
        t = t or self.thresholds()
        model = model or self.active_weight_model()
        f = self.db.one("SELECT * FROM fish WHERE id = ?", (fish_id,))
        w = weight.predict(model, f["length_cm"], f["area_cm2"])
        k = health.condition_factor(w, f["length_cm"])
        st = health.fish_status(f["cls"], f["conf"], k, t)
        self.db.update("fish", fish_id, {"est_weight_g": round(w, 1) if w is not None else None,
                                         "k": round(k, 3) if k is not None else None,
                                         "status": st["status"], "reasons_json": json.dumps(st["reasons"])})

    def refresh_drafts(self):
        t, model = self.thresholds(), self.active_weight_model()
        for f in self.db.all("SELECT f.id FROM fish f JOIN rounds r ON r.id = f.round_id WHERE r.status = 'draft'"):
            self._derive(f["id"], t, model)

    def photo_file(self, photo_id, kind):
        p = self.db.one("SELECT * FROM photos WHERE id = ?", (photo_id,))
        path = p and (p["annotated_path"] if kind == "annotated" else p["path"])
        if not path or not Path(path).exists():
            raise NotFound("Photo not found")
        return path

    # ------------------------------------------------------------------ assessment
    def round_assessment(self, round_id):
        r = self._round_row(round_id)
        t = self.thresholds()
        fish = self.db.all("SELECT * FROM fish WHERE round_id = ?", (round_id,))
        pond = self.get_pond(r["pond_id"])
        h = health.pond_status([f["status"] for f in fish], t)
        weights = [f["est_weight_g"] for f in fish if f["est_weight_g"] is not None]
        ks = [f["k"] for f in fish if f["k"] is not None]
        mean_k = round(sum(ks) / len(ks), 3) if ks else None
        size = harvest.size_stats(weights, t)
        count = r["fish_count_n"] or pond.get("stocked_count")
        biomass = round(size["mean_weight_g"] * count / 1000, 2) if size["mean_weight_g"] and count else None
        points = [(p["doc"], p["avg"]) for p in self._history_points(r["pond_id"], exclude_round=round_id)]
        if size["mean_weight_g"] and r["days_of_culture"] is not None:
            points.append((r["days_of_culture"], size["mean_weight_g"]))
        growth = harvest.growth_trend(points, t)
        ready = harvest.readiness(weights, mean_k, r["days_of_culture"], growth, h["status"], t)
        classes = {c: sum(1 for f in fish if f["cls"] == c) for c in ("Healthy", "Aeromonas", "TiLV")}
        model = self.active_weight_model()
        return {
            "health": h, "readiness": ready, "growth": growth,
            "summary": {"n_fish": len(fish), "n_screened": sum(1 for f in fish if f["cls"]),
                        "n_measured": len(weights), "avg_weight_g": size["mean_weight_g"],
                        "biomass_kg": biomass, "count_used": count, "cv": size["cv"],
                        "share_at_target": size["share_at_target"], "mean_k": mean_k, "classes": classes,
                        "status_counts": {s: sum(1 for f in fish if f["status"] == s)
                                          for s in HEALTH_LABELS + [health.UNSCREENED]}},
            "thresholds": t.to_dict(),
            "thresholds_confirmed": bool(self.db.get_setting("thresholds_confirmed", False)),
            "weight_model": {"id": model.get("id"), "label": model.get("label"), "kind": model["kind"],
                             "provisional": model["kind"] == "power"},
            "screener": self.screener.info()["name"], "computed_at": time.time()}

    def _history_points(self, pond_id, exclude_round=None):
        rows = self.db.all("SELECT id, days_of_culture, snapshot_json FROM rounds WHERE pond_id = ? AND "
                           "status = 'completed' ORDER BY days_of_culture", (pond_id,))
        pts = []
        for row in rows:
            if row["id"] == exclude_round or row["days_of_culture"] is None:
                continue
            avg = json.loads(row["snapshot_json"])["summary"]["avg_weight_g"]
            if avg:
                pts.append({"round_id": row["id"], "doc": row["days_of_culture"], "avg": avg})
        return pts

    def _round_brief(self, r):
        a = json.loads(r["snapshot_json"]) if r.get("snapshot_json") else self.round_assessment(r["id"])
        return {"id": r["id"], "sampled_at": r["sampled_at"], "days_of_culture": r["days_of_culture"],
                "status": r["status"], "source": r["source"], "board_mode": bool(r["board_mode"]),
                "health": a["health"]["status"], "readiness": a["readiness"]["status"],
                "avg_weight_g": a["summary"]["avg_weight_g"], "biomass_kg": a["summary"]["biomass_kg"],
                "n_fish": a["summary"]["n_fish"], "refer": a["summary"]["status_counts"].get(health.REFER, 0),
                "tech_health": r["tech_health"], "tech_readiness": r["tech_readiness"]}

    def pond_overview(self, pond_id):
        pond = self.get_pond(pond_id)
        rounds = self.db.all("SELECT * FROM rounds WHERE pond_id = ? ORDER BY sampled_at DESC, id DESC", (pond_id,))
        briefs = [self._round_brief(r) for r in rounds]
        latest = next((r for r in rounds if r["status"] == "completed"), None)
        pts = self._history_points(pond_id)
        return {"pond": pond, "rounds": briefs,
                "latest": {**self._round_brief(latest), "assessment": json.loads(latest["snapshot_json"])}
                if latest else None,
                "growth": harvest.growth_trend([(p["doc"], p["avg"]) for p in pts], self.thresholds()),
                "points": pts}

    def dashboard(self):
        out = []
        for p in self.list_ponds():
            rounds = self.db.all("SELECT * FROM rounds WHERE pond_id = ? ORDER BY sampled_at DESC, id DESC", (p["id"],))
            latest = next((r for r in rounds if r["status"] == "completed"), None)
            out.append({"pond": p, "latest": self._round_brief(latest) if latest else None,
                        "drafts": [r["id"] for r in rounds if r["status"] == "draft"],
                        "n_rounds": len(rounds)})
        return {"ponds": out, "review_count": len(self.review_queue()["fish"]),
                "screener": self.screener.info(), "weight_model": self.weight_model_info()["active"],
                "thresholds_confirmed": bool(self.db.get_setting("thresholds_confirmed", False))}

    # ------------------------------------------------------------------ technician
    def review_queue(self):
        fish = self.db.all(
            "SELECT f.*, r.pond_id, r.sampled_at, r.status AS round_status, p.name AS pond_name FROM fish f "
            "JOIN rounds r ON r.id = f.round_id JOIN ponds p ON p.id = r.pond_id "
            "WHERE f.status IN (?, ?) AND f.tech_signs IS NULL ORDER BY f.status DESC, r.sampled_at DESC",
            (health.REFER, health.WATCH))
        rounds = self.db.all(
            "SELECT r.*, p.name AS pond_name FROM rounds r JOIN ponds p ON p.id = r.pond_id "
            "WHERE r.status = 'completed' AND (r.tech_health IS NULL OR r.tech_readiness IS NULL) "
            "ORDER BY r.sampled_at DESC")
        return {"fish": [{**self._fish_view(f), "pond_name": f["pond_name"], "sampled_at": f["sampled_at"]}
                         for f in fish],
                "rounds": [{**self._round_brief(r), "pond_name": r["pond_name"]} for r in rounds]}

    def review_fish(self, fish_id, signs, note, user):
        self.get_fish(fish_id)
        if signs not in TECH_SIGNS:
            raise Invalid("Signs must be none, aeromonas, tilv or other.")
        self.db.update("fish", fish_id, {"tech_signs": signs, "tech_note": note, "reviewed_by": user,
                                         "reviewed_at": time.time()})
        return self.get_fish(fish_id)

    # ------------------------------------------------------------------ weight model
    def active_weight_model(self):
        row = self.db.one("SELECT * FROM weight_models WHERE active = 1 ORDER BY id DESC LIMIT 1")
        if not row:
            return weight.provisional_model(self.thresholds())
        m = json.loads(row["model_json"])
        m["id"] = row["id"]
        if row["includes_demo"]:
            m["label"] = m["label"] + " (fitted on demo data)"
        return m

    def _fit_rows(self, include_demo):
        sql = ("SELECT f.length_cm L, f.area_cm2 A, f.scale_weight_g W, r.pond_id grp, r.id rid FROM fish f "
               "JOIN rounds r ON r.id = f.round_id WHERE f.length_cm IS NOT NULL AND f.area_cm2 IS NOT NULL "
               "AND f.scale_weight_g IS NOT NULL" + ("" if include_demo else " AND f.source = 'real'"))
        rows = self.db.all(sql)
        by_pond = len({r["grp"] for r in rows}) >= 2
        return [{"L": r["L"], "A": r["A"], "W": r["W"], "group": r["grp"] if by_pond else r["rid"]} for r in rows], \
            "leave one pond out" if by_pond else "leave one round out"

    def weight_model_info(self):
        row = self.db.one("SELECT * FROM weight_models WHERE fit_json IS NOT NULL ORDER BY id DESC LIMIT 1")
        real_rows, _ = self._fit_rows(False)
        all_rows, _ = self._fit_rows(True)
        active = self.active_weight_model()
        return {"active": {"id": active.get("id"), "label": active["label"], "kind": active["kind"],
                           "provisional": active["kind"] == "power",
                           "terms": active.get("terms"), "range_L": active.get("range_L")},
                "last_fit": json.loads(row["fit_json"]) if row else None,
                "last_fit_at": row["created_at"] if row else None,
                "available_rows": {"real": len(real_rows), "including_demo": len(all_rows)},
                "min_rows": self.thresholds().weight_fit_min_fish}

    def fit_weight_model(self, user, include_demo=False):
        rows, scheme = self._fit_rows(include_demo)
        try:
            fit = weight.fit_models(rows, self.thresholds())
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        fit["cv_scheme"] = scheme
        chosen = fit[fit["selected"]]
        self.db.run("UPDATE weight_models SET active = 0")
        self.db.insert("weight_models", {"created_by": user, "kind": "ols", "model_json": json.dumps(chosen),
                                         "fit_json": json.dumps(fit), "includes_demo": int(include_demo),
                                         "active": 1})
        self.refresh_drafts()
        return self.weight_model_info()

    def reset_weight_model(self):
        self.db.run("UPDATE weight_models SET active = 0")
        self.refresh_drafts()
        return self.weight_model_info()

    # ------------------------------------------------------------------ evaluation
    def evaluation(self, include_demo=True):
        src = "" if include_demo else " AND r.source = 'real'"
        rounds = self.db.all("SELECT r.* FROM rounds r WHERE r.status = 'completed'" + src)
        hp, rp = [], []
        for r in rounds:
            snap = json.loads(r["snapshot_json"])
            if r["tech_health"]:
                hp.append((snap["health"]["status"], r["tech_health"]))
            if r["tech_readiness"]:
                sys_r = snap["readiness"]["status"]
                rp.append((harvest.APPROACHING if sys_r == harvest.SIZE_REVIEW else sys_r, r["tech_readiness"]))
        fsrc = "" if include_demo else " AND f.source = 'real'"
        fish = self.db.all("SELECT f.* FROM fish f JOIN rounds r ON r.id = f.round_id WHERE 1 = 1" + fsrc)
        tech_map = {"none": "Healthy", "aeromonas": "Aeromonas", "tilv": "TiLV", "other": "Other signs"}
        screen_labels = ["Healthy", "Aeromonas", "TiLV"]
        screen_pairs = [(f["cls"] or "Not screened", tech_map[f["tech_signs"]]) for f in fish if f["tech_signs"]]
        refer_pairs = [(f["status"], health.REFER if f["tech_signs"] in ("aeromonas", "tilv") else "no")
                       for f in fish if f["tech_signs"]]
        sm = ev.agreement(screen_pairs, screen_labels)
        per_round = {}
        for f in fish:
            if f["est_weight_g"] is not None and f["scale_weight_g"] is not None:
                per_round.setdefault(f["round_id"], []).append((f["est_weight_g"], f["scale_weight_g"]))
        avg_pairs = [(sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v)) for v in per_round.values()]
        n_demo = sum(1 for r in rounds if r["source"] == "demo")
        return {
            "health": {**ev.agreement(hp, HEALTH_LABELS), "refer_recall": ev.refer_recall(hp)},
            "readiness": ev.agreement(rp, READY_LABELS),
            "screening": {**sm, "n_reviewed": len(screen_pairs),
                          "other_or_unscreened": sum(1 for s, t in screen_pairs
                                                     if s not in screen_labels or t not in screen_labels),
                          "fish_refer_recall": ev.refer_recall(refer_pairs)},
            "length_error": ev.error_stats([(f["length_cm"], f["ruler_length_cm"]) for f in fish]),
            "weight_error": ev.error_stats([(f["est_weight_g"], f["scale_weight_g"]) for f in fish]),
            "avg_weight_error": ev.error_stats(avg_pairs),
            "retakes": self.retake_stats(include_demo),
            "weight_model": self.weight_model_info(),
            "rounds_used": len(rounds), "demo_rounds": n_demo,
            "benchmarks": self.benchmarks(),
        }

    def retake_stats(self, include_demo=True):
        row = self.db.one("SELECT COUNT(*) total, SUM(CASE WHEN p.ok = 0 THEN 1 ELSE 0 END) failed FROM photos p "
                          "JOIN fish f ON f.id = p.fish_id" + ("" if include_demo else " WHERE f.source = 'real'"))
        total, failed = row["total"] or 0, row["failed"] or 0
        return {"total": total, "failed": failed, "rate": round(failed / total, 4) if total else None}

    def benchmarks(self):
        from .benchmarks import load_benchmarks

        return load_benchmarks(self.settings.benchmarks_dir, self.screener.info())

    # ------------------------------------------------------------------ export / backup
    def export_csv(self, kind):
        buf = io.StringIO()
        if kind == "fish":
            rows = self.db.all(
                "SELECT p.name pond, r.id round_id, r.sampled_at, r.days_of_culture, f.code, f.source, f.cls, "
                "f.conf, f.status, f.length_cm, f.area_cm2, f.est_weight_g, f.k, f.scale_weight_g, "
                "f.ruler_length_cm, f.tech_signs, f.tech_note, f.sides FROM fish f JOIN rounds r ON r.id = f.round_id "
                "JOIN ponds p ON p.id = r.pond_id ORDER BY r.sampled_at, f.id")
        elif kind == "rounds":
            rows = []
            for r in self.db.all("SELECT r.*, p.name pond FROM rounds r JOIN ponds p ON p.id = r.pond_id "
                                 "ORDER BY r.sampled_at"):
                b = self._round_brief(r)
                rows.append({"pond": r["pond"], **{k: v for k, v in b.items()}})
        else:
            raise NotFound("Unknown export")
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return buf.getvalue()

    def backup_zip(self):
        out = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "tilapiers.db"
            dst = sqlite3.connect(snap)
            with self.db._lock:
                self.db.conn.backup(dst)
            dst.close()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(snap, "tilapiers.db")
                for f in self.settings.uploads_dir.rglob("*"):
                    if f.is_file():
                        z.write(f, "uploads/" + f.relative_to(self.settings.uploads_dir).as_posix())
        return out.getvalue()

    def restore_zip(self, data):
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise Invalid("That file is not a Tilapiers backup (.zip).") from exc
        if "tilapiers.db" not in z.namelist():
            raise Invalid("The backup does not contain tilapiers.db.")
        with tempfile.TemporaryDirectory() as tmp:
            z.extract("tilapiers.db", tmp)
            src = sqlite3.connect(Path(tmp) / "tilapiers.db")
            try:
                if not src.execute("SELECT name FROM sqlite_master WHERE name = 'users'").fetchone():
                    raise Invalid("The backup database has no users table.")
                if not src.execute("SELECT 1 FROM users WHERE role = 'admin' AND active = 1").fetchone():
                    raise Invalid("The backup has no active administrator.")
                with self.db._lock:
                    src.backup(self.db.conn)
            finally:
                src.close()
        uploads = self.settings.uploads_dir
        shutil.rmtree(uploads, ignore_errors=True)
        uploads.mkdir(parents=True, exist_ok=True)
        root = uploads.resolve()
        for name in z.namelist():
            if name.startswith("uploads/") and not name.endswith("/"):
                target = (uploads / name[len("uploads/"):]).resolve()
                if root not in target.parents:
                    continue  # zip-slip guard
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        # photo paths in the restored DB point at this machine's uploads folder
        for p in self.db.all("SELECT id, path, annotated_path FROM photos"):
            vals = {}
            for col in ("path", "annotated_path"):
                if p[col]:
                    parts = Path(p[col]).parts
                    if "uploads" in parts:
                        rel = Path(*parts[parts.index("uploads") + 1:])
                        vals[col] = str(uploads / rel)
            self.db.update("photos", p["id"], vals)

    # ------------------------------------------------------------------ content
    def list_content(self):
        return self.db.all("SELECT key, title, body_md, updated_at FROM content ORDER BY key")

    def get_content(self, key):
        c = self.db.one("SELECT key, title, body_md, updated_at FROM content WHERE key = ?", (key,))
        if not c:
            raise NotFound("Page not found")
        return c

    def set_content(self, key, title, body_md):
        self.db.run("INSERT INTO content (key, title, body_md, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) "
                    "DO UPDATE SET title = excluded.title, body_md = excluded.body_md, updated_at = excluded.updated_at",
                    (key, title, body_md, time.time()))
        return self.get_content(key)
