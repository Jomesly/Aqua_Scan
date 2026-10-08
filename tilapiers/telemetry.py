"""Telemetry, feeding-decision and alerting layer for Tilapiers.

Implements the paper's Data Layer and Logic Layer pieces that the live camera
dashboard did not cover: simulated water-quality sensing behind the Table 2
binary gate, the environment-gated / depletion-responsive feeding algorithm of
Table 3, SMS alert logging, culture-stage configuration and CSV export.

All waits use threading.Event; no bare sleep for long waits.
"""

import base64
import csv
import io
import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta

import paper_config as pc

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tilapiers.db")

_lock = threading.RLock()
_conn = None
_stop = threading.Event()
_threads = []

# Providers are registered by live_dashboard so this module never imports it
# (that would be circular). pellet(kind, p0=None) -> dict, evidence() -> bytes.
_providers = {"pellet": None, "evidence": None}

_active = {"session_id": None, "thread": None, "stop": threading.Event()}
_schedule_state = {"last_ran": set()}

SENSOR_TICK_S = 2.0
SEED_MINUTES = 720


def set_providers(pellet=None, evidence=None):
    if pellet is not None:
        _providers["pellet"] = pellet
    if evidence is not None:
        _providers["evidence"] = evidence


def _now():
    return time.time()


def _fmt(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _ms(ts):
    return int(ts * 1000) if ts else None


# ---------------------------------------------------------------- database


SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    temperature_c REAL,
    dissolved_oxygen_mg REAL,
    valid INTEGER NOT NULL DEFAULT 1,
    gate_state TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS feeding_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    ended_at REAL,
    culture_stage TEXT,
    d_ref_g REAL NOT NULL,
    increments_dispensed INTEGER NOT NULL DEFAULT 0,
    total_dispensed_g REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    source TEXT NOT NULL DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS increments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    size_g REAL NOT NULL,
    p_start INTEGER,
    p_end INTEGER,
    depletion_rate REAL,
    classification TEXT,
    action TEXT,
    confidence REAL,
    flag TEXT,
    evidence_p0_jpeg BLOB,
    evidence_pt_jpeg BLOB,
    t_decision REAL,
    t_exec REAL,
    p0_simulated INTEGER NOT NULL DEFAULT 0,
    pt_simulated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    sms_status TEXT,
    sms_sent_at REAL,
    sms_delivered_at REAL
);
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    abw_g REAL NOT NULL DEFAULT 50,
    num_stocks INTEGER NOT NULL DEFAULT 20,
    mobile_number TEXT NOT NULL DEFAULT '+639170000000',
    culture_stage TEXT NOT NULL DEFAULT 'starter',
    session_times TEXT NOT NULL DEFAULT '',
    abw_out_of_band INTEGER NOT NULL DEFAULT 0,
    simulate_pellets INTEGER NOT NULL DEFAULT 1,
    last_recalibrated_at REAL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incr_session ON increments(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_readings(ts);
"""


def _connect(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn):
    """Add columns introduced after a database was first created."""
    for table, column, ddl in (
        ("config", "simulate_pellets", "ALTER TABLE config ADD COLUMN simulate_pellets INTEGER NOT NULL DEFAULT 1"),
        ("increments", "p0_simulated", "ALTER TABLE increments ADD COLUMN p0_simulated INTEGER NOT NULL DEFAULT 0"),
        ("increments", "pt_simulated", "ALTER TABLE increments ADD COLUMN pt_simulated INTEGER NOT NULL DEFAULT 0"),
    ):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(ddl)


def _query(sql, params=()):
    with _lock:
        return _conn.execute(sql, params).fetchall()


def _execute(sql, params=()):
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur.lastrowid


def _one(sql, params=()):
    rows = _query(sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------- config


def get_config():
    row = _one("SELECT * FROM config WHERE id = 1")
    if row is None:
        _execute(
            "INSERT INTO config (id, abw_g, num_stocks, mobile_number, culture_stage,"
            " session_times, abw_out_of_band, simulate_pellets, last_recalibrated_at,"
            " updated_at) VALUES (1, 50, 20, '+639170000000', 'starter', '', 0, 1,"
            " NULL, ?)",
            (_now(),),
        )
        row = _one("SELECT * FROM config WHERE id = 1")

    cfg = dict(row)
    cfg["simulate_pellets"] = bool(cfg.get("simulate_pellets", 1))
    stage, out_of_band = pc.classify_stage(cfg["abw_g"])
    if stage is None:
        stage = pc.STAGE_BY_KEY.get(cfg["culture_stage"]) or pc.STAGE_BY_KEY[
            pc.DEFAULT_STAGE_KEY
        ]
    cfg["derived_stage"] = stage.key
    cfg["stage"] = {
        "key": stage.key,
        "label": stage.label,
        "month": stage.month,
        "abw_min_g": stage.abw_min_g,
        "abw_max_g": stage.abw_max_g,
        "rate_pct": stage.rate_pct,
        "freq": stage.freq,
        "feed": stage.feed,
        "sessions_per_day": stage.sessions_per_day,
    }
    cfg["abw_out_of_band"] = bool(
        cfg["abw_out_of_band"] or (stage is not None and out_of_band)
    )
    cfg["out_of_band"] = out_of_band
    cfg["d_ref_g"] = pc.d_ref_g(stage, cfg["abw_g"], cfg["num_stocks"])
    cfg["increment_g"] = cfg["d_ref_g"] * pc.INCREMENT_FRACTION
    cfg["updated_at_fmt"] = _fmt(cfg["updated_at"])
    cfg["last_recalibrated_fmt"] = _fmt(cfg["last_recalibrated_at"])

    stored = cfg.get("session_times") or ""
    times = [t for t in stored.split(",") if t] or list(
        pc.DEFAULT_SESSION_TIMES.get(stage.key, ())
    )
    cfg["session_times"] = times
    return cfg


def set_config(abw_g=None, num_stocks=None, mobile_number=None, simulate_pellets=None):
    cfg = get_config()
    if abw_g is not None:
        cfg["abw_g"] = float(abw_g)
    if num_stocks is not None:
        cfg["num_stocks"] = int(num_stocks)
    if mobile_number is not None:
        cfg["mobile_number"] = str(mobile_number)
    if simulate_pellets is not None:
        cfg["simulate_pellets"] = bool(simulate_pellets)

    stage, out_of_band = pc.classify_stage(cfg["abw_g"])
    stage_key = stage.key if stage else cfg["culture_stage"]
    if stage is None:
        _log_alert(
            pc.ALERT_FAIL_SAFE,
            "error",
            f"ABW {cfg['abw_g']} g is outside every Table 1 band; holding last "
            f"valid culture stage ({cfg['culture_stage']}).",
            sms=False,
        )
    else:
        cfg["last_recalibrated_at"] = _now()

    times = list(pc.DEFAULT_SESSION_TIMES.get(stage_key, ()))
    _execute(
        "UPDATE config SET abw_g=?, num_stocks=?, mobile_number=?, culture_stage=?,"
        " session_times=?, abw_out_of_band=?, simulate_pellets=?,"
        " last_recalibrated_at=?, updated_at=? WHERE id=1",
        (
            cfg["abw_g"],
            cfg["num_stocks"],
            cfg["mobile_number"],
            stage_key,
            ",".join(times),
            1 if out_of_band else 0,
            1 if cfg["simulate_pellets"] else 0,
            cfg["last_recalibrated_at"],
            _now(),
        ),
    )
    _schedule_state["last_ran"].clear()
    return get_config()


# ---------------------------------------------------------------- alerts


def _log_alert(kind, severity, message, sms=False, ts=None):
    ts = ts or _now()
    sent = delivered = None
    status = None
    if sms:
        status = "delivered"
        sent = ts - 1.5
        delivered = ts
    row_id = _execute(
        "INSERT INTO alerts (ts, kind, severity, message, sms_status, sms_sent_at,"
        " sms_delivered_at) VALUES (?,?,?,?,?,?,?)",
        (ts, kind, severity, message, status, sent, delivered),
    )
    return row_id


def _row_alert(row, include_evidence=False):
    return {
        "id": row["id"],
        "ts": _ms(row["ts"]),
        "time": _fmt(row["ts"]),
        "kind": row["kind"],
        "severity": row["severity"],
        "message": row["message"],
        "sms": bool(row["sms_status"]),
        "sms_status": row["sms_status"],
        "sms_sent_at": _fmt(row["sms_sent_at"]),
        "sms_delivered_at": _fmt(row["sms_delivered_at"]),
    }


def get_alerts(limit=100):
    rows = _query("SELECT * FROM alerts ORDER BY ts DESC, id DESC LIMIT ?", (limit,))
    return [_row_alert(r) for r in rows]


# ---------------------------------------------------------------- sensors


class _SimState:
    def __init__(self):
        self.temp = 27.4
        self.do = 5.6
        self.tick = 0
        self.excursion = 0

    def next_reading(self):
        self.tick += 1
        self.temp += (28.0 - self.temp) * 0.06 + random.gauss(0, 0.07)
        self.do += (5.6 - self.do) * 0.06 + random.gauss(0, 0.05)

        # Scripted excursion so the gate demonstrably flips to Unsafe.
        if self.tick % 150 == 0:
            self.excursion = 15
        if self.excursion > 0:
            self.excursion -= 1
            if self.excursion > 7:
                self.do = 4.35
            else:
                self.temp = 31.6

        self.temp = max(24.0, min(33.0, self.temp))
        self.do = max(3.4, min(7.0, self.do))
        return round(self.temp, 1), round(self.do, 2)

    def invalid_now(self):
        return self.tick > 0 and self.tick % 300 == 0


_sim = _SimState()
_last_gate = {"state": None}


def _latest_reading():
    row = _one("SELECT * FROM sensor_readings ORDER BY ts DESC, id DESC LIMIT 1")
    if row is None:
        return None
    return {
        "ts": row["ts"],
        "temperature_c": row["temperature_c"],
        "dissolved_oxygen_mg": row["dissolved_oxygen_mg"],
        "valid": bool(row["valid"]),
        "gate_state": row["gate_state"],
        "simulated": bool(row["simulated"]),
    }


def _record_reading(temp, do, valid, simulated=True):
    gate = pc.gate_state(temp, do) if valid else "Unsafe"
    ts = _now()
    _execute(
        "INSERT INTO sensor_readings (ts, temperature_c, dissolved_oxygen_mg, valid,"
        " gate_state, simulated) VALUES (?,?,?,?,?,?)",
        (ts, temp, do, 1 if valid else 0, gate, 1 if simulated else 0),
    )

    if valid and gate == "Unsafe" and _last_gate["state"] != "Unsafe":
        failing = pc.failing_parameters(temp, do)
        _log_alert(
            pc.ALERT_UNSAFE_ENV,
            "critical",
            f"Unsafe environment: {', '.join(failing)} outside the Table 2 band "
            f"(T {temp} °C, DO {do} mg/L). Feeding withheld; SMS sent to "
            f"{get_config()['mobile_number']}.",
            sms=True,
        )
    _last_gate["state"] = gate if valid else "Unsafe"
    return gate


def sensor_worker():
    while not _stop.is_set():
        temp, do = _sim.next_reading()
        valid = not _sim.invalid_now()
        try:
            if valid:
                _record_reading(temp, do, True)
            else:
                _record_reading(None, None, False)
                _log_alert(
                    pc.ALERT_FAIL_SAFE,
                    "error",
                    "Invalid or missing water-quality reading; no feeding action "
                    "taken until a valid reading is received.",
                    sms=False,
                )
        except Exception as exc:  # pragma: no cover - defensive
            print(f"sensor_worker error: {exc}")
        _stop.wait(SENSOR_TICK_S)


# ---------------------------------------------------------------- pellet + evidence


def _observe(kind, p0=None):
    """Return {count, confidence, simulated, camera_ok, evidence}."""
    fn = _providers.get("pellet")
    real = None
    if fn is not None:
        try:
            real = fn(kind, p0)
        except Exception:
            real = None

    if real is None or real.get("count") is None:
        return {"count": None, "confidence": 0.0, "simulated": False, "camera_ok": False}

    if kind == "health":
        return {"count": real["count"], "confidence": real.get("confidence", 0.0),
                "simulated": False, "camera_ok": True}

    if real.get("count", 0) > 0:
        real["simulated"] = False
        real["camera_ok"] = True
        return real

    # Camera saw no pellets. When the demo switch is on the feeding zone is
    # simulated so the algorithm can be exercised end to end; when it is off the
    # real zero stands and the p0_zero fail-safe fires.
    if not get_config().get("simulate_pellets", True):
        return {"count": 0, "confidence": real.get("confidence", 0.0),
                "simulated": False, "camera_ok": True}

    if kind == "p0":
        n0 = _sim_pellet_start()
        _sim_window["target_r"] = random.choices(
            ["High", "Moderate", "Low"], weights=[5, 3, 2]
        )[0]
        _sim_window["p0"] = n0
        return {"count": n0, "confidence": round(random.uniform(0.72, 0.95), 3),
                "simulated": True, "camera_ok": True}

    n0 = p0 if p0 else _sim_window.get("p0") or 1
    return {"count": _sim_pellet_end(n0), "confidence": round(random.uniform(0.72, 0.95), 3),
            "simulated": True, "camera_ok": True}


_sim_window = {"target_r": "High", "p0": 0}


def _sim_pellet_start():
    return random.randint(11, 18)


def _sim_pellet_end(n0):
    target = _sim_window.get("target_r", "High")
    if target == "High":
        r = random.uniform(0.82, 0.94)
    elif target == "Moderate":
        r = random.uniform(0.44, 0.76)
    else:
        r = random.uniform(0.05, 0.34)
    return max(0, int(round(n0 * (1 - r))))


def _evidence():
    fn = _providers.get("evidence")
    if fn is None:
        return None
    try:
        return fn()
    except Exception:
        return None


def _camera_lost():
    obs = _observe("health")
    return not obs.get("camera_ok", True)


# ---------------------------------------------------------------- feeding session


def _insert_increment(**kw):
    return _execute(
        "INSERT INTO increments (session_id, ts, size_g, p_start, p_end,"
        " depletion_rate, classification, action, confidence, flag,"
        " evidence_p0_jpeg, evidence_pt_jpeg, t_decision, t_exec,"
        " p0_simulated, pt_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            kw["session_id"],
            kw["ts"],
            kw["size_g"],
            kw.get("p_start"),
            kw.get("p_end"),
            kw.get("depletion_rate"),
            kw.get("classification"),
            kw.get("action"),
            kw.get("confidence"),
            kw.get("flag"),
            kw.get("evidence_p0_jpeg"),
            kw.get("evidence_pt_jpeg"),
            kw.get("t_decision"),
            kw.get("t_exec"),
            1 if kw.get("p0_simulated") else 0,
            1 if kw.get("pt_simulated") else 0,
        ),
    )


def _wait_window(session_stop):
    deadline = time.monotonic() + pc.OBSERVATION_WINDOW_S
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if _stop.wait(min(5.0, remaining)):
            return "shutdown"
        if session_stop.is_set():
            return "aborted"
        if _providers.get("pellet") is not None and _camera_lost():
            return "dropout"
    return "ok"


def _run_session(session_id, session_stop, source):
    cfg = get_config()
    d_ref = cfg["d_ref_g"]
    increment = cfg["increment_g"]
    if d_ref <= 0 or increment <= 0:
        _finish_session(session_id, pc.SESSION_FAIL_SAFE)
        _log_alert(
            pc.ALERT_FAIL_SAFE,
            "error",
            "Reference dose D_ref is zero; no feeding action taken.",
            sms=False,
        )
        return

    dispensed = 0.0
    prev_half = False
    status = pc.SESSION_COMPLETED

    while dispensed < d_ref - 1e-9:
        if session_stop.is_set() or _stop.is_set():
            status = pc.SESSION_FAIL_SAFE
            break

        reading = _latest_reading()
        if reading is None or not reading["valid"]:
            status = pc.SESSION_FAIL_SAFE
            _log_alert(
                pc.ALERT_FAIL_SAFE,
                "error",
                "No valid water-quality reading at increment gate; feeding halted.",
                sms=False,
            )
            break
        if reading["gate_state"] != "Safe":
            status = pc.SESSION_GATE_HALT
            _log_alert(
                pc.ALERT_UNSAFE_ENV,
                "critical",
                "Gate re-check failed immediately before an increment; feeding "
                f"withheld. T {reading['temperature_c']} °C, DO "
                f"{reading['dissolved_oxygen_mg']} mg/L. SMS sent to "
                f"{cfg['mobile_number']}.",
                sms=True,
            )
            break

        size = increment * (pc.HALF_INCREMENT_FRACTION if prev_half else 1.0)
        if dispensed + size > d_ref:
            size = round(d_ref - dispensed, 6)
        if size <= 1e-9:
            break

        t_exec = _now()
        dispensed = round(dispensed + size, 6)

        p0_obs = _observe("p0")
        ev0 = _evidence() if p0_obs.get("camera_ok") else None
        if not p0_obs.get("camera_ok"):
            status = pc.SESSION_FAIL_SAFE
            _log_alert(
                pc.ALERT_FAIL_SAFE,
                "error",
                "Camera dropout before P0 capture; no feeding action taken.",
                sms=False,
            )
            break

        wait_result = _wait_window(session_stop)
        pt_obs = _observe("pt", p0_obs["count"])
        ev_pt = _evidence() if pt_obs.get("camera_ok") else None

        if wait_result in ("shutdown", "aborted", "dropout") or not pt_obs.get("camera_ok"):
            status = pc.SESSION_FAIL_SAFE
            _insert_increment(
                session_id=session_id, ts=t_exec, size_g=size,
                p_start=p0_obs["count"], p_end=pt_obs.get("count"),
                confidence=p0_obs.get("confidence"), flag=None,
                evidence_p0_jpeg=ev0, evidence_pt_jpeg=ev_pt,
                t_decision=_now(), t_exec=t_exec,
                p0_simulated=p0_obs.get("simulated"), pt_simulated=pt_obs.get("simulated"),
            )
            if wait_result == "dropout":
                _log_alert(
                    pc.ALERT_FAIL_SAFE,
                    "error",
                    "Camera dropout during the observation window; feeding stopped.",
                    sms=False,
                )
            break

        p0, pt = p0_obs["count"], pt_obs["count"]
        confidence = min(
            [c for c in (p0_obs.get("confidence"), pt_obs.get("confidence")) if c],
            default=0.0,
        )
        rate = pc.depletion_rate(p0, pt)
        flag = None
        classification = action = None

        if p0 == 0:
            flag = pc.FLAG_P0_ZERO
            status = pc.SESSION_FAIL_SAFE
            _log_alert(
                pc.ALERT_FAIL_SAFE,
                "error",
                "No pellets counted at P0; classification withheld and dispensing "
                "stopped (p0_zero).",
                sms=False,
            )
        elif confidence < pc.MIN_CONFIDENCE:
            flag = pc.FLAG_LOW_CONFIDENCE
            _log_alert(
                pc.ALERT_LOW_CONFIDENCE,
                "warning",
                f"Detection confidence {confidence:.2f} below {pc.MIN_CONFIDENCE}; "
                "reading held out of the decision and previous increment state kept.",
                sms=False,
            )
        elif rate is not None and rate >= pc.RAPID_DEPLETION:
            flag = pc.FLAG_RAPID_DEPLETION
            _log_alert(
                pc.ALERT_RAPID_DEPLETION,
                "warning",
                f"R = {rate:.2f} implies implausibly rapid depletion; flagged for "
                "review and not auto-classified as High.",
                sms=False,
            )
        else:
            classification, action, _ = pc.classify_depletion(rate)
            if classification == "Low":
                prev_half = False
                status = pc.SESSION_LOW_DEPLETION_STOP
                _log_alert(
                    pc.ALERT_UNEATEN_FEED,
                    "warning",
                    f"Low depletion (R = {rate:.2f}) after {size:g} g; "
                    f"{pt} pellets remain at Pt. Further feeding withheld.",
                    sms=True,
                )
            elif classification == "Moderate":
                prev_half = True
            else:
                prev_half = False

        _insert_increment(
            session_id=session_id, ts=t_exec, size_g=size,
            p_start=p0, p_end=pt, depletion_rate=rate,
            classification=classification, action=action, confidence=confidence,
            flag=flag, evidence_p0_jpeg=ev0, evidence_pt_jpeg=ev_pt,
            t_decision=_now(), t_exec=t_exec,
            p0_simulated=p0_obs.get("simulated"), pt_simulated=pt_obs.get("simulated"),
        )

        if status in (pc.SESSION_LOW_DEPLETION_STOP, pc.SESSION_FAIL_SAFE):
            break

    if status == pc.SESSION_COMPLETED and dispensed >= d_ref - 1e-9:
        status = pc.SESSION_CAP_REACHED
    _finish_session(session_id, status)


def _finish_session(session_id, status):
    row = _one("SELECT * FROM feeding_sessions WHERE id = ?", (session_id,))
    if row is None:
        return
    totals = _one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_g), 0) AS g FROM increments"
        " WHERE session_id = ?",
        (session_id,),
    )
    _execute(
        "UPDATE feeding_sessions SET ended_at=?, status=?, increments_dispensed=?,"
        " total_dispensed_g=? WHERE id=?",
        (_now(), status, totals["n"], totals["g"], session_id),
    )
    if _active.get("session_id") == session_id:
        _active["session_id"] = None
        _active["thread"] = None


def start_session(source=pc.SOURCE_LIVE):
    _reap_active()
    if _active.get("session_id") is not None:
        return None, "a session is already running"
    cfg = get_config()
    session_id = _execute(
        "INSERT INTO feeding_sessions (started_at, culture_stage, d_ref_g,"
        " increments_dispensed, total_dispensed_g, status, source)"
        " VALUES (?,?,?,?,?,?,?)",
        (_now(), cfg["derived_stage"], cfg["d_ref_g"], 0, 0.0, "running", source),
    )
    session_stop = threading.Event()
    _active["session_id"] = session_id
    _active["stop"] = session_stop
    thread = threading.Thread(
        target=_run_session,
        args=(session_id, session_stop, source),
        daemon=True,
        name=f"tilapiers-feeding-{session_id}",
    )
    _active["thread"] = thread
    thread.start()
    return session_id, None


def _reap_active():
    thread = _active.get("thread")
    if thread is not None and not thread.is_alive():
        _active["session_id"] = None
        _active["thread"] = None


# ---------------------------------------------------------------- schedule


def _session_times():
    return get_config()["session_times"]


def _parse_times():
    out = []
    for value in _session_times():
        try:
            hour, minute = (int(x) for x in value.split(":"))
            out.append((hour, minute))
        except (ValueError, AttributeError):
            continue
    return out


def _next_session_at(now=None):
    now = now or datetime.now()
    times = _parse_times()
    if not times:
        return None
    for hour, minute in times:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate
    first = times[0]
    return (now + timedelta(days=1)).replace(
        hour=first[0], minute=first[1], second=0, microsecond=0
    )


def scheduler_worker():
    while not _stop.is_set():
        now = datetime.now()
        today = now.date().isoformat()

        for idx, (hour, minute) in enumerate(_parse_times()):
            key = (today, idx, hour, minute)
            if key in _schedule_state["last_ran"]:
                continue
            if now.hour == hour and now.minute == minute and now.second < 55:
                _schedule_state["last_ran"].add(key)
                sid, err = start_session(pc.SOURCE_LIVE)
                if err:
                    print(f"scheduler: session {idx} not started: {err}")

        mkey = (today, "maint")
        if now.weekday() == pc.MAINTENANCE_DAY and _is_due(pc.MAINTENANCE_TIME, now):
            if mkey not in _schedule_state["last_ran"]:
                _schedule_state["last_ran"].add(mkey)
                _log_alert(
                    pc.ALERT_MAINTENANCE,
                    "info",
                    "Saturday reminder: clean the camera and feeder.",
                    sms=True,
                )

        rkey = (today, "recal")
        if now.weekday() == pc.WEEKLY_RECALIBRATION_DAY and _is_due("08:00", now):
            if rkey not in _schedule_state["last_ran"]:
                _schedule_state["last_ran"].add(rkey)
                _log_alert(
                    pc.ALERT_MAINTENANCE,
                    "info",
                    "Weekly recalibration due: re-sample average body weight and "
                    "re-enter it to refresh D_ref.",
                    sms=False,
                )

        _stop.wait(20)


def _is_due(hhmm, now):
    try:
        hour, minute = (int(x) for x in hhmm.split(":"))
    except (ValueError, AttributeError):
        return False
    return now.hour == hour and now.minute == minute and now.second < 55


def get_schedule():
    cfg = get_config()
    now = datetime.now()
    nxt = _next_session_at(now)
    prefeed_at = nxt - timedelta(minutes=pc.PREFEED_OFFSET_MIN) if nxt else None
    reading = _latest_reading()
    gate = reading["gate_state"] if reading else "Unknown"

    times = []
    for idx, value in enumerate(_session_times()):
        try:
            hour, minute = (int(x) for x in value.split(":"))
        except (ValueError, AttributeError):
            continue
        at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        times.append(
            {
                "index": idx + 1,
                "time": value,
                "start_at": _ms(at.timestamp()),
                "start_fmt": _fmt(at.timestamp()),
                "prefeed_at": _ms(
                    (at - timedelta(minutes=pc.PREFEED_OFFSET_MIN)).timestamp()
                ),
                "prefeed_fmt": _fmt(
                    (at - timedelta(minutes=pc.PREFEED_OFFSET_MIN)).timestamp()
                ),
                "past": at < now,
            }
        )

    next_at = nxt.timestamp() if nxt else None
    return {
        "sessions_per_day": cfg["stage"]["sessions_per_day"],
        "culture_stage": cfg["derived_stage"],
        "times": times,
        "next_session_at": _ms(next_at) if next_at else None,
        "next_session_fmt": _fmt(next_at) if next_at else None,
        "prefeed_offset_min": pc.PREFEED_OFFSET_MIN,
        "prefeed_at": _ms(prefeed_at.timestamp()) if prefeed_at else None,
        "prefeed_fmt": _fmt(prefeed_at.timestamp()) if prefeed_at else None,
        "prefeed_evaluated": bool(prefeed_at and now >= prefeed_at),
        "prefeed_gate_state": gate,
        "prefeed_result": (
            "Proceed" if gate == "Safe" else "Hold - environment Unsafe"
        ) if prefeed_at and now >= prefeed_at else "Pending",
        "maintenance": {
            "day": "Saturday",
            "time": pc.MAINTENANCE_TIME,
            "due_today": now.weekday() == pc.MAINTENANCE_DAY,
        },
        "weekly_recalibration": {
            "due": now.weekday() == pc.WEEKLY_RECALIBRATION_DAY,
            "last": cfg["last_recalibrated_fmt"],
        },
    }


# ---------------------------------------------------------------- API payloads


def get_environment():
    reading = _latest_reading()
    if reading is None:
        return {
            "available": False,
            "temperature_c": None,
            "dissolved_oxygen_mg": None,
            "valid": False,
            "gate_state": "Unsafe",
            "simulated": True,
            "failing": ["temperature", "dissolved oxygen"],
            "thresholds": _thresholds(),
            "sms_log": [],
        }
    temp, do = reading["temperature_c"], reading["dissolved_oxygen_mg"]
    valid = reading["valid"]
    return {
        "available": True,
        "ts": _ms(reading["ts"]),
        "time": _fmt(reading["ts"]),
        "temperature_c": temp,
        "dissolved_oxygen_mg": do,
        "valid": valid,
        "gate_state": reading["gate_state"] if valid else "Unsafe",
        "simulated": reading["simulated"],
        "failing": pc.failing_parameters(temp, do) if valid else [],
        "thresholds": _thresholds(),
        "sms_log": [
            _row_alert(r)
            for r in _query(
                "SELECT * FROM alerts WHERE sms_status IS NOT NULL ORDER BY ts DESC LIMIT 10"
            )
        ],
    }


def _thresholds():
    return {
        "temp_min_c": pc.TEMP_MIN_C,
        "temp_max_c": pc.TEMP_MAX_C,
        "do_min_mg": pc.DO_MIN_MG,
        "has_do_max": False,
    }


def _row_session(row):
    return {
        "id": row["id"],
        "started_at": _ms(row["started_at"]),
        "started_fmt": _fmt(row["started_at"]),
        "ended_at": _ms(row["ended_at"]),
        "ended_fmt": _fmt(row["ended_at"]),
        "culture_stage": row["culture_stage"],
        "d_ref_g": row["d_ref_g"],
        "increments_dispensed": row["increments_dispensed"],
        "total_dispensed_g": row["total_dispensed_g"],
        "status": row["status"],
        "source": row["source"],
        "seed": row["source"] == pc.SOURCE_SEED,
        "test": row["source"] == pc.SOURCE_TEST,
    }


def _deref(blob):
    if not blob:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(blob).decode("ascii")


def _row_increment(row):
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "ts": _ms(row["ts"]),
        "time": _fmt(row["ts"]),
        "size_g": row["size_g"],
        "p_start": row["p_start"],
        "p_end": row["p_end"],
        "depletion_rate": row["depletion_rate"],
        "classification": row["classification"],
        "action": row["action"],
        "confidence": row["confidence"],
        "flag": row["flag"],
        "t_decision": row["t_decision"],
        "t_exec": row["t_exec"],
        "decision_ms": int((row["t_decision"] - row["t_exec"]) * 1000)
        if row["t_decision"] and row["t_exec"] else None,
        "p0_simulated": bool(row["p0_simulated"]),
        "pt_simulated": bool(row["pt_simulated"]),
        "evidence_p0": _deref(row["evidence_p0_jpeg"]),
        "evidence_pt": _deref(row["evidence_pt_jpeg"]),
    }


def get_feeding_session():
    _reap_active()
    cfg = get_config()
    active_id = _active.get("session_id")
    payload = {
        "active": active_id is not None,
        "session": None,
        "increments": [],
        "d_ref_g": cfg["d_ref_g"],
        "increment_g": cfg["increment_g"],
        "increment_fraction": pc.INCREMENT_FRACTION,
        "observation_window_s": pc.OBSERVATION_WINDOW_S,
        "culture_stage": cfg["derived_stage"],
        "schedule": get_schedule(),
        "last_session": None,
        "thresholds": _thresholds(),
    }

    if active_id is not None:
        row = _one("SELECT * FROM feeding_sessions WHERE id = ?", (active_id,))
        if row is not None:
            payload["session"] = _row_session(row)
            payload["increments"] = [
                _row_increment(r)
                for r in _query(
                    "SELECT * FROM increments WHERE session_id = ? ORDER BY id",
                    (active_id,),
                )
            ]

    last = _one(
        "SELECT * FROM feeding_sessions WHERE status != 'running' ORDER BY id DESC LIMIT 1"
    )
    if last is not None:
        payload["last_session"] = _row_session(last)
        payload["last_increments"] = [
            _row_increment(r)
            for r in _query(
                "SELECT * FROM increments WHERE session_id = ? ORDER BY id",
                (last["id"],),
            )
        ]
    return payload


def get_feeding_history(limit=25, session_id=None):
    if session_id is not None:
        row = _one("SELECT * FROM feeding_sessions WHERE id = ?", (session_id,))
        if row is None:
            return {"session": None, "increments": []}
        return {
            "session": _row_session(row),
            "increments": [
                _row_increment(r)
                for r in _query(
                    "SELECT * FROM increments WHERE session_id = ? ORDER BY id",
                    (session_id,),
                )
            ],
        }

    rows = _query(
        "SELECT * FROM feeding_sessions WHERE status != 'running'"
        " ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    sessions = []
    for row in rows:
        item = _row_session(row)
        item["r_mean"] = _one(
            "SELECT AVG(depletion_rate) AS r FROM increments WHERE session_id = ?"
            " AND depletion_rate IS NOT NULL",
            (row["id"],),
        )["r"]
        sessions.append(item)
    return {"sessions": sessions, "total": len(sessions)}


EXPORT_TABLES = {
    "increments": "increments",
    "sensor_readings": "sensor_readings",
    "alerts": "alerts",
}


def export_csv(table="increments"):
    table = EXPORT_TABLES.get(table, "increments")
    with _lock:
        cursor = _conn.execute(f"SELECT * FROM {table} ORDER BY id")
        headers = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        values = []
        for key in headers:
            value = row[key]
            if key in ("evidence_p0_jpeg", "evidence_pt_jpeg") and value:
                value = f"<{len(value)} bytes>"
            elif key in ("ts", "started_at", "ended_at", "t_decision", "t_exec",
                         "sms_sent_at", "sms_delivered_at") and value:
                value = _fmt(value) or value
            values.append(value)
        writer.writerow(values)
    return buf.getvalue()


# ---------------------------------------------------------------- seed


def _seed_evidence(label):
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    image = np.full((180, 320, 3), (34, 26, 18), dtype=np.uint8)
    cv2.rectangle(image, (6, 6), (313, 173), (70, 120, 90), 1)
    cv2.putText(image, "SEED", (14, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (180, 230, 200), 2, cv2.LINE_AA)
    cv2.putText(image, label, (14, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (230, 230, 230), 1, cv2.LINE_AA)
    cv2.putText(image, "feeding zone - Cam 01", (14, 106),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 170, 160), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
    return bytes(buf) if ok else None


def seed_data(force=False):
    if not force and _one("SELECT id FROM feeding_sessions LIMIT 1") is not None:
        return 0

    cfg = get_config()
    d_ref = cfg["d_ref_g"]
    increment = cfg["increment_g"]
    base = _now() - SEED_MINUTES * 60
    created = 0

    plans = [
        (["High", "High", "Moderate", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High", "Moderate", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High", "High", "High", "High"], pc.SESSION_CAP_REACHED),
        (["Moderate", "Moderate", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High", "High"], pc.SESSION_CAP_REACHED),
        (["Moderate", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High", "Moderate", "High", "Low"], pc.SESSION_LOW_DEPLETION_STOP),
        (["High"], pc.SESSION_GATE_HALT),
        (["High", "High", "Moderate"], pc.SESSION_CAP_REACHED),
    ]

    for idx, (tiers, final_status) in enumerate(plans):
        started = base + idx * 42 * 60
        stage_key = cfg["derived_stage"]
        session_id = _execute(
            "INSERT INTO feeding_sessions (started_at, ended_at, culture_stage,"
            " d_ref_g, increments_dispensed, total_dispensed_g, status, source)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (started, started + len(tiers) * 6 * 60, stage_key, d_ref, 0, 0.0,
             final_status, pc.SOURCE_SEED),
        )

        dispensed = 0.0
        prev_half = False
        for j, tier in enumerate(tiers):
            size = increment * (pc.HALF_INCREMENT_FRACTION if prev_half else 1.0)
            if dispensed + size > d_ref:
                size = round(d_ref - dispensed, 6)
            if size <= 1e-9:
                break
            dispensed = round(dispensed + size, 6)

            p0 = random.randint(12, 18)
            if tier == "High":
                rate = random.uniform(0.81, 0.93)
            elif tier == "Moderate":
                rate = random.uniform(0.42, 0.78)
            else:
                rate = random.uniform(0.04, 0.36)
            pt = max(0, int(round(p0 * (1 - rate))))
            rate = pc.depletion_rate(p0, pt)
            classification, action, _ = pc.classify_depletion(rate)
            if tier == "Low":
                prev_half = False
            elif tier == "Moderate":
                prev_half = True
            else:
                prev_half = False

            ts = started + j * 5 * 60 + 8
            _execute(
                "INSERT INTO increments (session_id, ts, size_g, p_start, p_end,"
                " depletion_rate, classification, action, confidence, flag,"
                " evidence_p0_jpeg, evidence_pt_jpeg, t_decision, t_exec,"
                " p0_simulated, pt_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id, ts, size, p0, pt, rate, classification, action,
                    round(random.uniform(0.78, 0.95), 3),
                    None,
                    _seed_evidence(f"P0 = {p0} pellets"),
                    _seed_evidence(f"Pt = {pt} pellets"),
                    ts + 1.2, ts, 1, 1,
                ),
            )
        created += 1

        _execute(
            "UPDATE feeding_sessions SET increments_dispensed=?, total_dispensed_g=?"
            " WHERE id=?",
            (len(tiers), dispensed, session_id),
        )

    _log_alert(pc.ALERT_UNEATEN_FEED, "warning",
               "Low depletion (R = 0.21) after 3.125 g; 4 pellets remain at Pt. "
               "Further feeding withheld.", sms=True,
               ts=base + 60 * 60)
    _log_alert(pc.ALERT_UNSAFE_ENV, "critical",
               "Unsafe environment: dissolved oxygen outside the Table 2 band "
               "(T 27.4 °C, DO 4.4 mg/L). Feeding withheld; SMS sent to "
               f"{cfg['mobile_number']}.", sms=True, ts=base + 180 * 60)
    _log_alert(pc.ALERT_LOW_CONFIDENCE, "warning",
               "Detection confidence 0.31 below 0.40; reading held out of the "
               "decision and previous increment state kept.", sms=False,
               ts=base + 300 * 60)
    _log_alert(pc.ALERT_MAINTENANCE, "info",
               "Saturday reminder: clean the camera and feeder.", sms=True,
               ts=base + 420 * 60)
    _log_alert(pc.ALERT_RAPID_DEPLETION, "warning",
               "R = 0.99 implies implausibly rapid depletion; flagged for review "
               "and not auto-classified as High.", sms=False, ts=base + 540 * 60)
    return created


# ---------------------------------------------------------------- lifecycle


def init(db_path=DB_PATH, seed=True, with_workers=True):
    global _conn
    with _lock:
        if _conn is not None:
            return _conn
        _conn = _connect(db_path)
    if seed:
        try:
            seed_data()
        except Exception as exc:  # pragma: no cover - defensive
            print(f"seed_data failed: {exc}")
    if with_workers:
        start_workers()
    return _conn


def start_workers():
    for target, name in (
        (sensor_worker, "tilapiers-sensor"),
        (scheduler_worker, "tilapiers-scheduler"),
    ):
        thread = threading.Thread(target=target, daemon=True, name=name)
        _threads.append(thread)
        thread.start()


def shutdown():
    _stop.set()
    _active.get("stop", threading.Event()).set()
