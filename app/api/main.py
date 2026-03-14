from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.erase import router as erase_router
from app.api.routes.ocr import router as ocr_router
from app.api.routes.process import router as process_router
from app.api.routes.render import router as render_router


def create_app() -> FastAPI:
    app = FastAPI(title="Local Image Translation Engine", version="0.1.0")
    app.include_router(health_router)
    app.include_router(process_router)
    app.include_router(ocr_router)
    app.include_router(erase_router)
    app.include_router(render_router)
    return app


app = create_app()
