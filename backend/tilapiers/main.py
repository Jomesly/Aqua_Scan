"""Application factory.

Run:  uvicorn tilapiers.main:app --reload   (from backend/)
Nothing touches hardware or the database at import time; startup happens in the
lifespan handler so tests can build isolated apps.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import Settings
from .db import Database
from .monitor import Monitor
from .notify import Notifier
from .services import Services
from .vision.detector import load_detector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app(settings=None, start_monitor=True):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings.db_path)
        notifier = Notifier(db, settings)
        services = Services(db, settings, notifier, load_detector(settings.yolo_weights))
        if settings.demo and not services.list_ponds():
            from .seed import seed_demo

            seed_demo(services)
        app.state.settings = settings
        app.state.services = services
        app.state.monitor = None
        if start_monitor and settings.sensor_mode != "off":
            app.state.monitor = Monitor(services, settings)
            app.state.monitor.start()
        yield
        if app.state.monitor:
            app.state.monitor.stop()
        db.close()

    app = FastAPI(title="Tilapiers", version="2.0.0", lifespan=lifespan)
    app.include_router(router)

    dist = settings.frontend_dist
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return HTMLResponse("Not found", status_code=404)
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse(
            "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in <code>frontend/</code>, "
            "or use the Vite dev server on port 5173.</p>")

    return app


app = create_app()
