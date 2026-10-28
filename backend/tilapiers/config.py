"""Runtime configuration from environment variables (see backend/.env.example)."""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
MODELS_DIR = BACKEND_DIR / "models"


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _path(value):
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else BACKEND_DIR / p


@dataclass
class Settings:
    data_dir: Path
    db_path: Path
    uploads_dir: Path
    frontend_dist: Path
    demo: bool
    yolo_weights: Path | None
    seg_weights: Path | None
    secret_key: str
    benchmarks_dir: Path = MODELS_DIR / "benchmarks"

    @classmethod
    def from_env(cls, **overrides):
        _load_dotenv(BACKEND_DIR / ".env")
        data_dir = _path(os.environ.get("TILAPIERS_DATA_DIR")) or BACKEND_DIR / "data"
        values = dict(
            data_dir=data_dir,
            db_path=data_dir / "tilapiers.db",
            uploads_dir=data_dir / "uploads",
            frontend_dist=REPO_DIR / "frontend" / "dist",
            demo=_bool("TILAPIERS_DEMO"),
            yolo_weights=_path(os.environ.get("TILAPIERS_YOLO_WEIGHTS")) or MODELS_DIR / "yolov8s_best.pt",
            seg_weights=_path(os.environ.get("TILAPIERS_SEG_WEIGHTS")),
            # A random key means sessions end when the server restarts; set one in .env to keep them.
            secret_key=os.environ.get("TILAPIERS_SECRET_KEY") or secrets.token_hex(32),
        )
        if "data_dir" in overrides:
            values["db_path"] = Path(overrides["data_dir"]) / "tilapiers.db"
            values["uploads_dir"] = Path(overrides["data_dir"]) / "uploads"
        values.update(overrides)
        return cls(**values)
