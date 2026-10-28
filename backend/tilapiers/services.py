"""Domain services: everything the API and the background monitor need, built on
the pure rules and the database."""

import io
import json
import time
import uuid
from datetime import datetime

from .rules import environment as env_rules
from .rules import evaluation as eval_rules
from .rules import harvest as harvest_rules
from .rules import health as health_rules
from .rules.environment import PH_TZ
from .rules.thresholds import Thresholds

DAY = 86400.0

HEALTH_LABELS = ["Normal", "Watch", "Refer to technician"]
READINESS_LABELS = [harvest_rules.NOT_READY, harvest_rules.APPROACHING, harvest_rules.READY]


class NotFound(Exception):
    pass


def fmt_ts(ts):
    return datetime.fromtimestamp(ts, PH_TZ).isoformat(timespec="seconds") if ts else None


def time_of_day(ts):
    h = datetime.fromtimestamp(ts, PH_TZ).hour
    if h < 10:
        return "Morning"
    if h < 14:
        return "Midday"
    if h < 18:
        return "Afternoon"
    return "Evening"


class Services:
    def __init__(self, db, settings, notifier, detector):
        self.db = db
        self.settings = settings
        self.notifier = notifier
        self.detector = detector

    # ------------------------------------------------------------- settings
    def thresholds(self):
        return Thresholds.from_dict(self.db.get_setting("thresholds", {}))

    def set_thresholds(self, values):
        current = self.thresholds().to_dict()
        current.update({k: v for k, v in values.items() if k in current and v is not None})
        t = Thresholds.from_dict(current)
        if t.temp_min_c >= t.temp_max_c:
            raise ValueError("Minimum temperature must be below maximum.")
        if not (0 <= t.health_watch_share <= t.health_refer_share <= 1):
            raise ValueError("Watch share must not exceed the Refer share (both 0-1).")
        if not (0 <= t.approaching_share_at_target <= t.ready_share_at_target <= 1):
            raise ValueError("Approaching share must not exceed the Ready share (both 0-1).")
        self.db.set_setting("thresholds", t.to_dict())
        return t

    def fci_model(self):
        return self.db.get_setting("fci_model") or health_rules.DEFAULT_FCI_MODEL

    # ---------------------------------------------------------------- ponds
    def list_ponds(self, include_archived=False):
        sql = "SELECT * FROM ponds" + ("" if include_archived else " WHERE archived=0") + " ORDER BY id"
        return self.db.query(sql)

    def get_pond(self, pond_id):
        pond = self.db.one("SELECT * FROM ponds WHERE id=?", (pond_id,))
        if not pond:
            raise NotFound(f"Pond {pond_id} not found")
        return pond

    def create_pond(self, data):
        return self.db.insert("ponds", {
            "name": data["name"].strip(), "location": data.get("location"),
            "area_m2": data.get("area_m2"), "stocked_at": data["stocked_at"],
            "stocked_count": data.get("stocked_count"), "feeding_regime": data.get("feeding_regime"),
            "notes": data.get("notes"), "created_at": time.time(),
        })

    def update_pond(self, pond_id, data):
        self.get_pond(pond_id)
        allowed = {"name", "location", "area_m2", "stocked_at", "stocked_count", "feeding_regime", "notes", "archived"}
        self.db.update("ponds", pond_id, {k: v for k, v in data.items() if k in allowed})
        return self.get_pond(pond_id)

    def days_of_culture(self, pond, ts=None):
        return round(((ts or time.time()) - pond["stocked_at"]) / DAY, 1)

    # ---------------------------------------------------------- temperature
    def record_reading(self, pond_id, temp_c, source, ts=None):
        self.db.insert("temperature_readings", {
            "pond_id": pond_id, "ts": ts or time.time(), "temperature_c": float(temp_c), "source": source,
        })

    def record_readings(self, pond_id, readings, source):
        rows = [(pond_id, float(r["ts"]), float(r["temperature_c"]), source) for r in readings]
        self.db.executemany(
            "INSERT INTO temperature_readings (pond_id, ts, temperature_c, source) VALUES (?,?,?,?)", rows)
        return len(rows)

    def latest_reading(self, pond_id):
        return self.db.one(
            "SELECT ts, temperature_c, source FROM temperature_readings WHERE pond_id=? ORDER BY ts DESC LIMIT 1",
            (pond_id,))

    def temperature_history(self, pond_id, hours=24, max_points=360):
        end = time.time()
        start = end - hours * 3600
        bucket = max(hours * 3600 / max_points, 1)
        rows = self.db.query(
            "SELECT CAST(ts / ? AS INTEGER) AS b, MIN(ts) AS ts, AVG(temperature_c) AS avg_c, "
            "MIN(temperature_c) AS min_c, MAX(temperature_c) AS max_c, "
            "SUM(source = 'simulated' OR source = 'seed') AS synthetic, COUNT(*) AS n "
            "FROM temperature_readings WHERE pond_id=? AND ts>=? GROUP BY b ORDER BY b",
            (bucket, pond_id, start))
        return [{
            "ts": r["ts"], "temperature_c": round(r["avg_c"], 2),
            "min_c": round(r["min_c"], 2), "max_c": round(r["max_c"], 2),
            "synthetic": r["synthetic"] == r["n"],
        } for r in rows]

    def readings_between(self, pond_id, start, end):
        rows = self.db.query(
            "SELECT ts, temperature_c FROM temperature_readings WHERE pond_id=? AND ts BETWEEN ? AND ? ORDER BY ts",
            (pond_id, start, end))
        return [(r["ts"], r["temperature_c"]) for r in rows]

    def critical_between(self, pond_id, start, end, t):
        lo = t.temp_min_c - t.temp_moderate_margin_c
        hi = t.temp_max_c + t.temp_moderate_margin_c
        n = self.db.scalar(
            "SELECT COUNT(*) FROM temperature_readings WHERE pond_id=? AND ts BETWEEN ? AND ? "
            "AND (temperature_c < ? OR temperature_c > ?)", (pond_id, start, end, lo, hi))
        do_bad = self.db.scalar(
            "SELECT COUNT(*) FROM observations WHERE pond_id=? AND ts BETWEEN ? AND ? AND do_ppm IS NOT NULL "
            "AND do_ppm < ?", (pond_id, start, end, t.do_critical_below_ppm))
        return (n or 0) > 0 or (do_bad or 0) > 0

    # ---------------------------------------------------------- observations
    def add_observation(self, pond_id, data):
        self.get_pond(pond_id)
        return self.db.insert("observations", {
            "pond_id": pond_id, "ts": data.get("ts") or time.time(),
            "algae_seen": 1 if data["algae_seen"] else 0,
            "do_ppm": data.get("do_ppm"), "ph": data.get("ph"),
            "ammonia_ppm": data.get("ammonia_ppm"), "nitrate_ppm": data.get("nitrate_ppm"),
            "notes": data.get("notes"), "recorded_by": data.get("recorded_by"),
        })

    def observations(self, pond_id, limit=30):
        rows = self.db.query("SELECT * FROM observations WHERE pond_id=? ORDER BY ts DESC LIMIT ?", (pond_id, limit))
        for r in rows:
            r["algae_seen"] = bool(r["algae_seen"])
        return rows

    # ------------------------------------------------------- environment now
    def environment_now(self, pond_id, t=None):
        t = t or self.thresholds()
        now = time.time()
        reading = self.latest_reading(pond_id)
        stale = reading is None or now - reading["ts"] > t.sensor_stale_after_s
        obs = self.db.one("SELECT * FROM observations WHERE pond_id=? ORDER BY ts DESC LIMIT 1", (pond_id,))
        algae_active = bool(obs and obs["algae_seen"] and now - obs["ts"] <= t.algae_report_valid_days * DAY)
        do_ppm = obs["do_ppm"] if obs and now - obs["ts"] <= DAY else None
        temp = None if stale else reading["temperature_c"]
        assessment = env_rules.classify_environment(temp, algae_seen=algae_active, do_ppm=do_ppm, thresholds=t)
        if obs:
            obs = dict(obs, algae_seen=bool(obs["algae_seen"]))
        return {
            "pond_id": pond_id,
            "temperature_c": reading["temperature_c"] if reading else None,
            "reading_ts": reading["ts"] if reading else None,
            "source": reading["source"] if reading else None,
            "stale": stale,
            "direction": env_rules.temperature_direction(temp, t),
            "state": assessment.state,
            "reasons": assessment.reasons,
            "season": env_rules.season_for(now),
            "algae_active": algae_active,
            "latest_observation": obs,
            "band": {"min_c": t.temp_min_c, "max_c": t.temp_max_c, "moderate_margin_c": t.temp_moderate_margin_c},
        }

    def evaluate_environment(self, pond_id):
        """Called by the monitor every tick: notify on state transitions only."""
        pond = self.db.one("SELECT name FROM ponds WHERE id=?", (pond_id,))
        if not pond:
            return None
        now_env = self.environment_now(pond_id)
        state = now_env["state"]
        prev = self.db.one("SELECT state FROM env_state WHERE pond_id=?", (pond_id,))
        prev_state = prev["state"] if prev else None
        if state == prev_state:
            return now_env
        self.db.execute(
            "INSERT INTO env_state (pond_id, state, since_ts) VALUES (?,?,?) "
            "ON CONFLICT(pond_id) DO UPDATE SET state=excluded.state, since_ts=excluded.since_ts",
            (pond_id, state, time.time()))
        name = pond["name"]
        reason = " ".join(now_env["reasons"])
        if state == "Critical":
            self.notifier.notify("environment", "critical", f"{name}: environment Critical", reason, pond_id)
        elif state == "Unknown" and prev_state is not None:
            self.notifier.notify("probe", "warning", f"{name}: temperature probe offline",
                                 "No reading received recently. Check the probe's power and connection.", pond_id)
        elif state == "Moderate" and prev_state in (None, "Good", "Unknown"):
            self.notifier.notify("environment", "warning", f"{name}: environment Moderate", reason, pond_id)
        elif state == "Good" and prev_state in ("Critical", "Moderate"):
            self.notifier.notify("environment", "info", f"{name}: environment back to Good", reason, pond_id)
        return now_env

    # -------------------------------------------------------- sampling rounds
    def create_round(self, pond_id, data):
        pond = self.get_pond(pond_id)
        ts = data.get("sampled_at") or time.time()
        return self.db.insert("sampling_rounds", {
            "pond_id": pond_id, "sampled_at": ts, "days_of_culture": self.days_of_culture(pond, ts),
            "capture_condition": data.get("capture_condition"),
            "time_of_day": data.get("time_of_day") or time_of_day(ts),
            "weather": data.get("weather"), "phone_model": data.get("phone_model"),
            "notes": data.get("notes"), "status": "draft", "created_at": time.time(),
        })

    def get_round_row(self, round_id):
        row = self.db.one("SELECT * FROM sampling_rounds WHERE id=?", (round_id,))
        if not row:
            raise NotFound(f"Sampling round {round_id} not found")
        return row

    def update_round(self, round_id, data):
        self.get_round_row(round_id)
        allowed = {"capture_condition", "weather", "phone_model", "notes", "technician_health", "technician_readiness"}
        self.db.update("sampling_rounds", round_id, {k: v for k, v in data.items() if k in allowed})
        return self.round_detail(round_id)

    def fish_for_round(self, round_id):
        rows = self.db.query("SELECT * FROM fish WHERE round_id=? ORDER BY seq", (round_id,))
        for r in rows:
            r["flagged"] = bool(r["flagged"])
            r["quality"] = json.loads(r.pop("quality_json") or "null")
            r["detection"] = json.loads(r.pop("detection_json") or "null")
            r["photo_url"] = f"/api/photos/{r['photo_path']}" if r["photo_path"] else None
        return rows

    def _previous_round(self, rnd):
        return self.db.one(
            "SELECT * FROM sampling_rounds WHERE pond_id=? AND sampled_at < ? ORDER BY sampled_at DESC LIMIT 1",
            (rnd["pond_id"], rnd["sampled_at"]))

    def _round_stats(self, round_id):
        return self.db.one(
            "SELECT COUNT(*) AS n, AVG(weight_g) AS mean_w, AVG(condition_factor) AS mean_k, AVG(fci) AS mean_fci "
            "FROM fish WHERE round_id=?", (round_id,))

    def compute_round(self, rnd, t=None):
        t = t or self.thresholds()
        pond = self.get_pond(rnd["pond_id"])
        fish = self.db.query("SELECT weight_g, condition_factor, fci FROM fish WHERE round_id=?", (rnd["id"],))
        prev = self._previous_round(rnd)
        start = prev["sampled_at"] if prev else max(pond["stocked_at"], rnd["sampled_at"] - 30 * DAY)
        stress = env_rules.stress_exposure(self.readings_between(pond["id"], start, rnd["sampled_at"]),
                                           start, rnd["sampled_at"], thresholds=t)
        stress["season"] = env_rules.season_for(rnd["sampled_at"])
        stress["algae_reports"] = self.db.scalar(
            "SELECT COUNT(*) FROM observations WHERE pond_id=? AND algae_seen=1 AND ts BETWEEN ? AND ?",
            (pond["id"], start, rnd["sampled_at"])) or 0
        env_critical = self.critical_between(pond["id"], start, rnd["sampled_at"], t)
        ks = [f["condition_factor"] for f in fish if f["condition_factor"] is not None]
        mean_k = sum(ks) / len(ks) if ks else None
        health = health_rules.health_status([f["fci"] for f in fish], mean_k, env_critical, t)

        history = self.db.query(
            "SELECT r.days_of_culture AS doc, AVG(f.weight_g) AS mean_w FROM sampling_rounds r "
            "JOIN fish f ON f.round_id = r.id WHERE r.pond_id=? AND r.sampled_at <= ? "
            "GROUP BY r.id ORDER BY r.sampled_at", (pond["id"], rnd["sampled_at"]))
        growth = harvest_rules.growth_trend([(h["doc"], h["mean_w"]) for h in history], t)
        recent_critical = self.critical_between(pond["id"], rnd["sampled_at"] - t.recent_critical_days * DAY,
                                                rnd["sampled_at"], t)
        readiness = harvest_rules.harvest_readiness(
            [f["weight_g"] for f in fish], mean_k, rnd["days_of_culture"], health["status"],
            recent_critical, growth, t)
        return {
            "health": health, "readiness": readiness, "growth": growth, "stress": stress,
            "env_critical_in_interval": env_critical, "mean_k": round(mean_k, 3) if mean_k else None,
            "interval_start": start,
        }

    def round_detail(self, round_id):
        rnd = self.get_round_row(round_id)
        snapshot = json.loads(rnd.pop("snapshot_json") or "null")
        result = dict(rnd)
        result["fish"] = self.fish_for_round(round_id)
        result["assessment"] = snapshot if snapshot else self.compute_round(rnd)
        result["assessment_recorded"] = bool(snapshot)
        result["pond"] = self.get_pond(rnd["pond_id"])
        return result

    def list_rounds(self, pond_id):
        rows = self.db.query("SELECT * FROM sampling_rounds WHERE pond_id=? ORDER BY sampled_at DESC", (pond_id,))
        out = []
        for r in rows:
            snapshot = json.loads(r.pop("snapshot_json") or "null")
            stats = self._round_stats(r["id"])
            a = snapshot or self.compute_round(r)
            out.append({**r, "n_fish": stats["n"], "mean_weight_g": stats["mean_w"],
                        "mean_fci": round(stats["mean_fci"], 2) if stats["mean_fci"] else None,
                        "health_status": a["health"]["status"], "readiness_status": a["readiness"]["status"]})
        return out

    def complete_round(self, round_id):
        rnd = self.get_round_row(round_id)
        if rnd["status"] == "completed":
            return self.round_detail(round_id)
        assessment = self.compute_round(rnd)
        self.db.update("sampling_rounds", round_id, {
            "status": "completed", "completed_at": time.time(), "snapshot_json": json.dumps(assessment)})
        pond = self.get_pond(rnd["pond_id"])
        h = assessment["health"]
        if h["status"] in ("Watch", "Refer to technician"):
            self.notifier.notify(
                "health", "critical" if h["status"].startswith("Refer") else "warning",
                f"{pond['name']}: health status {h['status']}",
                " ".join(h["reasons"]) + " Set flagged fish aside for the technician's review.", pond["id"])
        r = assessment["readiness"]
        if r["status"] in (harvest_rules.READY, harvest_rules.SIZE_REVIEW):
            self.notifier.notify("harvest", "info", f"{pond['name']}: {r['status']}",
                                 "Review the harvest readiness indicators with the technician.", pond["id"])
        return self.round_detail(round_id)

    def delete_round(self, round_id):
        rnd = self.get_round_row(round_id)
        if rnd["status"] == "completed":
            raise ValueError("Completed rounds are part of the record and cannot be deleted.")
        self.db.execute("DELETE FROM fish WHERE round_id=?", (round_id,))
        self.db.execute("DELETE FROM sampling_rounds WHERE id=?", (round_id,))

    # ------------------------------------------------------------------ fish
    def add_fish(self, round_id, weight_g, length_cm, technician_score=None, photo_bytes=None, photo_name=None):
        from .vision.indicators import measure_indicators
        from .vision.quality import check_quality, load_rgb

        rnd = self.get_round_row(round_id)
        if rnd["status"] == "completed":
            raise ValueError("This round is completed; start a new round to add fish.")
        t = self.thresholds()
        seq = (self.db.scalar("SELECT MAX(seq) FROM fish WHERE round_id=?", (round_id,)) or 0) + 1
        k = health_rules.condition_factor(weight_g, length_cm)
        values = {
            "round_id": round_id, "seq": seq, "weight_g": weight_g, "length_cm": length_cm,
            "condition_factor": round(k, 4) if k else None, "technician_score": technician_score,
            "analysis_source": "manual", "created_at": time.time(),
        }
        if photo_bytes:
            ext = (photo_name or "photo.jpg").rsplit(".", 1)[-1].lower()
            ext = ext if ext in ("jpg", "jpeg", "png", "webp", "heic") else "jpg"
            fname = f"r{round_id}_f{seq}_{uuid.uuid4().hex[:8]}.{ext}"
            self.settings.uploads_dir.mkdir(parents=True, exist_ok=True)
            (self.settings.uploads_dir / fname).write_bytes(photo_bytes)
            try:
                rgb = load_rgb(io.BytesIO(photo_bytes))
            except Exception as exc:
                raise ValueError(f"Could not read the photo: {exc}") from exc
            checks = check_quality(rgb)
            detection = self.detector.detect(rgb, photo_bytes)
            if detection.is_stub:
                checks.append({"key": "scale", "label": "Reference scale", "value": "not checked (no trained detector)",
                               "passed": True, "hint": "Checked once YOLO26 is trained."})
            else:
                checks.append({"key": "scale", "label": "Reference scale",
                               "value": "detected" if detection.scale_px_per_cm else "missing",
                               "passed": detection.scale_px_per_cm is not None,
                               "hint": "Keep the printed scale fully inside the frame."})
            ind = measure_indicators(rgb, detection)
            if detection.is_stub:
                ind["image_length_cm"] = None  # a placeholder scale would give a meaningless length
            values.update({
                "photo_path": fname, "analysis_source": "photo",
                "image_length_cm": ind["image_length_cm"],
                "gill_color_index": ind["gill_color_index"], "skin_color_index": ind["skin_color_index"],
                "fin_integrity": ind["fin_integrity"], "eye_clarity": ind["eye_clarity"],
                "body_shape": ind["body_shape"],
                "quality_json": json.dumps({"checks": checks, "passed": all(c["passed"] for c in checks),
                                            "lighting_correction": ind["lighting_correction"]}),
                "detection_json": json.dumps(detection.to_dict()),
            })
        fci = health_rules.predict_fci(self.fci_model(), values) if photo_bytes else None
        values["fci"] = fci
        values["flagged"] = 1 if fci is not None and fci < t.fci_flag_below else 0
        fish_id = self.db.insert("fish", values)
        return next(f for f in self.fish_for_round(round_id) if f["id"] == fish_id)

    def update_fish(self, fish_id, data):
        fish = self.db.one("SELECT * FROM fish WHERE id=?", (fish_id,))
        if not fish:
            raise NotFound(f"Fish {fish_id} not found")
        allowed = {"weight_g", "length_cm", "technician_score"}
        values = {k: v for k, v in data.items() if k in allowed}
        merged = {**fish, **values}
        k = health_rules.condition_factor(merged["weight_g"], merged["length_cm"])
        values["condition_factor"] = round(k, 4) if k else None
        merged["condition_factor"] = values["condition_factor"]
        if fish["analysis_source"] != "manual":
            merged_fci = health_rules.predict_fci(self.fci_model(), merged)
            values["fci"] = merged_fci
            values["flagged"] = 1 if merged_fci is not None and merged_fci < self.thresholds().fci_flag_below else 0
        self.db.update("fish", fish_id, values)
        return self.db.one("SELECT * FROM fish WHERE id=?", (fish_id,))

    def delete_fish(self, fish_id):
        fish = self.db.one("SELECT f.id, r.status FROM fish f JOIN sampling_rounds r ON r.id=f.round_id WHERE f.id=?",
                           (fish_id,))
        if not fish:
            raise NotFound(f"Fish {fish_id} not found")
        if fish["status"] == "completed":
            raise ValueError("Fish in a completed round are part of the record.")
        self.db.execute("DELETE FROM fish WHERE id=?", (fish_id,))

    # ------------------------------------------------------------- overview
    def pond_summary(self, pond, t=None):
        t = t or self.thresholds()
        env = self.environment_now(pond["id"], t)
        latest = self.db.one(
            "SELECT * FROM sampling_rounds WHERE pond_id=? ORDER BY sampled_at DESC LIMIT 1", (pond["id"],))
        latest_summary = None
        if latest:
            snapshot = json.loads(latest.pop("snapshot_json") or "null")
            a = snapshot or self.compute_round(latest, t)
            latest_summary = {
                "id": latest["id"], "sampled_at": latest["sampled_at"], "status": latest["status"],
                "days_of_culture": latest["days_of_culture"], "health": a["health"], "readiness": a["readiness"]["status"],
                "readiness_detail": a["readiness"],
            }
        return {**pond, "days_of_culture": self.days_of_culture(pond), "environment": env,
                "latest_round": latest_summary,
                "rounds_count": self.db.scalar("SELECT COUNT(*) FROM sampling_rounds WHERE pond_id=?", (pond["id"],))}

    def growth_for_pond(self, pond_id):
        t = self.thresholds()
        rounds = self.db.query(
            "SELECT r.id, r.sampled_at, r.days_of_culture AS doc, COUNT(f.id) AS n, AVG(f.weight_g) AS mean_w, "
            "AVG(f.condition_factor) AS mean_k FROM sampling_rounds r JOIN fish f ON f.round_id=r.id "
            "WHERE r.pond_id=? GROUP BY r.id ORDER BY r.sampled_at", (pond_id,))
        trend = harvest_rules.growth_trend([(r["doc"], r["mean_w"]) for r in rounds], t)
        for r in rounds:
            weights = [x["weight_g"] for x in self.db.query("SELECT weight_g FROM fish WHERE round_id=?", (r["id"],))]
            r.update(harvest_rules.round_size_stats(weights, t))
        return {"rounds": rounds, "trend": trend, "target_weight_g": t.target_weight_g}

    # ----------------------------------------------------------- evaluation
    def add_calibration(self, data):
        return self.db.insert("probe_calibrations", {
            "pond_id": data.get("pond_id"), "ts": data.get("ts") or time.time(),
            "probe_c": data["probe_c"], "reference_c": data["reference_c"], "notes": data.get("notes")})

    def scored_fish_rows(self):
        return self.db.query(
            "SELECT f.*, r.pond_id, r.id AS round_id FROM fish f JOIN sampling_rounds r ON r.id=f.round_id "
            "WHERE f.technician_score IS NOT NULL")

    def fit_fci(self, poly_features=()):
        rows = self.scored_fish_rows()
        model = health_rules.fit_fci_model(rows, health_rules.FEATURES, poly_features)
        self.db.set_setting("fci_model", model)
        self.rescore_all_fish(model)
        return model

    def reset_fci_model(self):
        self.db.execute("DELETE FROM settings WHERE key='fci_model'")
        self.rescore_all_fish(health_rules.DEFAULT_FCI_MODEL)

    def rescore_all_fish(self, model):
        t = self.thresholds()
        for f in self.db.query("SELECT * FROM fish WHERE analysis_source != 'manual'"):
            fci = health_rules.predict_fci(model, f)
            self.db.update("fish", f["id"], {"fci": fci, "flagged": 1 if fci is not None and fci < t.fci_flag_below else 0})

    def evaluation(self):
        calib_rows = self.db.query("SELECT * FROM probe_calibrations ORDER BY ts DESC")
        rounds = self.db.query("SELECT * FROM sampling_rounds WHERE status='completed' ORDER BY sampled_at")
        health_pairs, ready_pairs, assoc_rows = [], [], []
        for r in rounds:
            snap = json.loads(r["snapshot_json"] or "null")
            if not snap:
                continue
            health_pairs.append((snap["health"]["status"], r["technician_health"]))
            sys_ready = snap["readiness"]["status"]
            if sys_ready == harvest_rules.SIZE_REVIEW:
                sys_ready = harvest_rules.APPROACHING  # not cleared as Ready
            ready_pairs.append((sys_ready, r["technician_readiness"]))
            stats = self._round_stats(r["id"])
            assoc_rows.append({"pond_id": r["pond_id"], "x": snap["stress"]["hours_outside_band"],
                               "y": round(stats["mean_fci"], 3) if stats["mean_fci"] else None})
        scored = self.scored_fish_rows()
        model = self.fci_model()
        return {
            "probe_calibration": {**eval_rules.calibration_metrics([(c["probe_c"], c["reference_c"]) for c in calib_rows]),
                                  "rows": calib_rows[:50]},
            "fci_model": model,
            "feature_labels": health_rules.FEATURE_LABELS,
            "feature_groups": health_rules.compare_feature_groups(scored),
            "n_scored_fish": len(scored),
            "health_agreement": eval_rules.agreement(health_pairs, HEALTH_LABELS),
            "readiness_agreement": eval_rules.agreement(ready_pairs, READINESS_LABELS),
            "stress_association": eval_rules.stress_association(assoc_rows),
            "length_error": self._length_error(),
        }

    def _length_error(self):
        rows = self.db.query("SELECT f.length_cm, f.image_length_cm, f.detection_json FROM fish f "
                             "WHERE f.length_cm IS NOT NULL AND f.image_length_cm IS NOT NULL")
        real = [r for r in rows if not json.loads(r["detection_json"] or "{}").get("is_stub", True)]
        pairs = [(r["image_length_cm"], r["length_cm"]) for r in real]
        m = eval_rules.calibration_metrics(pairs)
        m["n_stub_excluded"] = len(rows) - len(real)
        return m
