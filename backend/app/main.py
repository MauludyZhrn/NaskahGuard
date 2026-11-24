"""FastAPI application entry point for NaskahGuard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, checks, config, corpus, dashboard, documents, health, providers, reports, settings as settings_api
from app.config import BASE_DIR, get_settings
from app.db import Base, dispose_engine, init_db
from app.security import validate_startup_security
from app.worker import start_worker, stop_worker


def run_migrations(database_url: str) -> None:
    if database_url.startswith("sqlite:///:memory:"):
        engine = init_db(database_url)
        Base.metadata.create_all(bind=engine)
        return

    alembic_ini = Path(BASE_DIR) / "alembic.ini"
    cfg = AlembicConfig(str(alembic_ini))
    cfg.set_main_option("script_location", str(Path(BASE_DIR) / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    init_db(database_url)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cfg = get_settings()
    validate_startup_security(cfg)
    cfg.storage_path.mkdir(parents=True, exist_ok=True)
    run_migrations(cfg.DATABASE_URL)
    start_worker()
    try:
        yield
    finally:
        stop_worker()
        dispose_engine()


def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title=cfg.APP_NAME,
        version=cfg.APP_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    for router in (
        health.router,
        config.router,
        documents.router,
        corpus.router,
        checks.router,
        reports.router,
        dashboard.router,
        providers.router,
        settings_api.router,
        audit.router,
    ):
        app.include_router(router, prefix="/api")

    return app


app = create_app()
