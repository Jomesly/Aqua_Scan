"""SQLite storage. One connection shared across threads behind a lock (WAL mode)."""

import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL CHECK (role IN ('caretaker', 'technician', 'admin')),
    pw_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ponds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    setup TEXT,
    stocked_at TEXT,
    stocked_count INTEGER,
    archived INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'real',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS threshold_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    user TEXT,
    changes_json TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS weight_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    created_by TEXT,
    kind TEXT NOT NULL,
    model_json TEXT NOT NULL,
    fit_json TEXT,
    includes_demo INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pond_id INTEGER NOT NULL REFERENCES ponds(id),
    sampled_at TEXT NOT NULL,
    days_of_culture REAL,
    fish_count_n INTEGER,
    board_mode INTEGER NOT NULL DEFAULT 1,
    capture_condition TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    snapshot_json TEXT,
    completed_at REAL,
    tech_health TEXT,
    tech_readiness TEXT,
    tech_by TEXT,
    created_by TEXT,
    source TEXT NOT NULL DEFAULT 'real',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS fish (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    scale_weight_g REAL,
    ruler_length_cm REAL,
    cls TEXT,
    conf REAL,
    sides INTEGER NOT NULL DEFAULT 0,
    length_cm REAL,
    area_cm2 REAL,
    est_weight_g REAL,
    k REAL,
    status TEXT,
    reasons_json TEXT,
    tech_signs TEXT,
    tech_note TEXT,
    reviewed_by TEXT,
    reviewed_at REAL,
    source TEXT NOT NULL DEFAULT 'real',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fish_id INTEGER NOT NULL REFERENCES fish(id) ON DELETE CASCADE,
    side TEXT NOT NULL,
    path TEXT NOT NULL,
    annotated_path TEXT,
    ok INTEGER NOT NULL,
    current INTEGER NOT NULL DEFAULT 1,
    result_json TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fish_round ON fish(round_id);
CREATE INDEX IF NOT EXISTS idx_photos_fish ON photos(fish_id);
CREATE TABLE IF NOT EXISTS content (key TEXT PRIMARY KEY, title TEXT, body_md TEXT, updated_at REAL);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def all(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def run(self, sql, params=()):
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    def insert(self, table, values):
        values = {"created_at": time.time(), **values} if table not in ("settings", "content", "threshold_history") \
            else values
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        return self.run(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))

    def update(self, table, row_id, values):
        if not values:
            return
        sets = ", ".join(f"{k} = ?" for k in values)
        self.run(f"UPDATE {table} SET {sets} WHERE id = ?", (*values.values(), row_id))

    def get_setting(self, key, default=None):
        row = self.one("SELECT value_json FROM settings WHERE key = ?", (key,))
        return json.loads(row["value_json"]) if row else default

    def set_setting(self, key, value):
        self.run("INSERT INTO settings (key, value_json) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json", (key, json.dumps(value)))

    def close(self):
        with self._lock:
            self.conn.close()
