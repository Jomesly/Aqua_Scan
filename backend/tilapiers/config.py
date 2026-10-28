"""Runtime configuration from environment variables (see backend/.env.example)."""

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


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


@dataclass
class Settings:
    data_dir: Path
    db_path: Path
    uploads_dir: Path
    frontend_dist: Path
    demo: bool
    sensor_mode: str  # auto | serial | simulate | off
    serial_port: str | None
    serial_pond_id: int
    log_interval_s: float
    ingest_token: str | None
    notify_channel: str  # none | email | sms
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_starttls: bool
    yolo_weights: str | None

    @classmethod
    def from_env(cls, **overrides):
        _load_dotenv(BACKEND_DIR / ".env")
        data_dir = Path(os.environ.get("TILAPIERS_DATA_DIR", BACKEND_DIR / "data"))
        demo = _bool("TILAPIERS_DEMO")
        values = dict(
            data_dir=data_dir,
            db_path=data_dir / "tilapiers.db",
            uploads_dir=data_dir / "uploads",
            frontend_dist=REPO_DIR / "frontend" / "dist",
            demo=demo,
            sensor_mode=os.environ.get("TILAPIERS_SENSOR", "simulate" if demo else "auto").lower(),
            serial_port=os.environ.get("TILAPIERS_SERIAL_PORT") or None,
            serial_pond_id=int(os.environ.get("TILAPIERS_SERIAL_POND", "1")),
            log_interval_s=float(os.environ.get("TILAPIERS_LOG_INTERVAL_S", "10")),
            ingest_token=os.environ.get("TILAPIERS_INGEST_TOKEN") or None,
            notify_channel=os.environ.get("TILAPIERS_NOTIFY_CHANNEL", "none").lower(),
            smtp_host=os.environ.get("SMTP_HOST") or None,
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER") or None,
            smtp_password=os.environ.get("SMTP_PASSWORD") or None,
            smtp_from=os.environ.get("SMTP_FROM") or None,
            smtp_starttls=_bool("SMTP_STARTTLS", True),
            yolo_weights=os.environ.get("TILAPIERS_YOLO_WEIGHTS") or None,
        )
        if "data_dir" in overrides:
            values["db_path"] = Path(overrides["data_dir"]) / "tilapiers.db"
            values["uploads_dir"] = Path(overrides["data_dir"]) / "uploads"
        values.update(overrides)
        return cls(**values)
