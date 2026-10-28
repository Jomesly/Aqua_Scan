"""SQLite storage. One connection shared across threads behind a lock (WAL mode)."""

import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS ponds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    area_m2 REAL,
    stocked_at REAL NOT NULL,
    stocked_count INTEGER,
    feeding_regime TEXT,
    notes TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pond_id INTEGER NOT NULL REFERENCES ponds(id),
    ts REAL NOT NULL,
    temperature_c REAL NOT NULL,
    source TEXT NOT NULL            -- probe-serial | probe-http | simulated | seed
);
CREATE INDEX IF NOT EXISTS idx_temp_pond_ts ON temperature_readings(pond_id, ts);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pond_id INTEGER NOT NULL REFERENCES ponds(id),
    ts REAL NOT NULL,
    algae_seen INTEGER NOT NULL,
    do_ppm REAL,
    ph REAL,
    ammonia_ppm REAL,
    nitrate_ppm REAL,
    notes TEXT,
    recorded_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_pond_ts ON observations(pond_id, ts);

CREATE TABLE IF NOT EXISTS sampling_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pond_id INTEGER NOT NULL REFERENCES ponds(id),
    sampled_at REAL NOT NULL,
    days_of_culture REAL,
    capture_condition TEXT,         -- open sunlight | shade | overcast
    time_of_day TEXT,
    weather TEXT,
    phone_model TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    completed_at REAL,
    snapshot_json TEXT,
    technician_health TEXT,
    technician_readiness TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_round_pond ON sampling_rounds(pond_id, sampled_at);

CREATE TABLE IF NOT EXISTS fish (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES sampling_rounds(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    weight_g REAL,
    length_cm REAL,
    photo_path TEXT,
    image_length_cm REAL,
    condition_factor REAL,
    gill_color_index REAL,
    skin_color_index REAL,
    fin_integrity REAL,
    eye_clarity REAL,
    body_shape REAL,
    fci REAL,
    flagged INTEGER NOT NULL DEFAULT 0,
    technician_score REAL,
    quality_json TEXT,
    detection_json TEXT,
    analysis_source TEXT NOT NULL,  -- photo | manual | seed
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fish_round ON fish(round_id);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    pond_id INTEGER,
    kind TEXT NOT NULL,             -- environment | probe | health | harvest
    severity TEXT NOT NULL,         -- critical | warning | info
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    deliveries_json TEXT NOT NULL,  -- [{channel, status, detail, at}]
    acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notif_ts ON notifications(ts);

CREATE TABLE IF NOT EXISTS probe_calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pond_id INTEGER,
    ts REAL NOT NULL,
    probe_c REAL NOT NULL,
    reference_c REAL NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS env_state (
    pond_id INTEGER PRIMARY KEY,
    state TEXT NOT NULL,
    since_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql, params=()):
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return row[0] if row else None

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def executemany(self, sql, rows):
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def insert(self, table, values):
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        return self.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))

    def update(self, table, row_id, values):
        if not values:
            return
        sets = ", ".join(f"{k}=?" for k in values)
        self.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*values.values(), row_id))

    # settings ---------------------------------------------------------------
    def get_setting(self, key, default=None):
        row = self.one("SELECT value_json FROM settings WHERE key=?", (key,))
        return json.loads(row["value_json"]) if row else default

    def set_setting(self, key, value):
        self.execute(
            "INSERT INTO settings (key, value_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (key, json.dumps(value), time.time()),
        )

    def close(self):
        with self._lock:
            self._conn.close()
