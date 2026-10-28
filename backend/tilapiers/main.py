"""Application factory.

Run:  uvicorn tilapiers.main:app   (from backend/)
Nothing loads the model or touches the database at import time; startup happens
in the lifespan handler so tests can build isolated apps.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .auth import Sessions
from .config import Settings
from .db import Database
from .services import Services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app(settings=None, screener=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        from .vision.screening import Screener, load_seg

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings.db_path)
        services = Services(db, settings, screener or Screener(settings.yolo_weights), load_seg(settings.seg_weights))
        from .seed import seed_base

        seed_base(services, demo=settings.demo)
        app.state.settings = settings
        app.state.services = services
        app.state.sessions = Sessions(settings.secret_key)
        yield
        db.close()

    app = FastAPI(title="Tilapiers", version="3.0.0", lifespan=lifespan)
    app.include_router(router)

    dist = settings.frontend_dist
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return HTMLResponse("Not found", status_code=404)
        static = dist / path
        if path and static.is_file() and dist.resolve() in static.resolve().parents:
            return FileResponse(static)
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse(
            "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in <code>frontend/</code>, "
            "or use the Vite dev server on port 5173.</p>")

    return app


app = create_app()
