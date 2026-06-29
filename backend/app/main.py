from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, UnknownDatabaseError
from app.core.middleware import SecurityHeadersMiddleware


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="PostgreSQL backup, restore, and validation API",
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    @app.exception_handler(UnknownDatabaseError)
    async def unknown_database_handler(_request: Request, exc: UnknownDatabaseError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConfigurationError)
    async def configuration_handler(_request: Request, exc: ConfigurationError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    app.include_router(api_router)

    frontend_dist = settings.base_dir.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
