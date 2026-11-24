"""Health check endpoint (accessible without Bearer token)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.db import check_db_connection
from app.engine.noplag_adapter import NoplagAdapter
from app.engine.semantic import get_semantic_status
from app.ingestion.ocr import get_ocr_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    ocr = get_ocr_status()
    sem = get_semantic_status()
    noplag = NoplagAdapter().health()
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "error",
        "pdf_backend": settings.PDF_BACKEND,
        "ocr": {"available": ocr.available, "message": ocr.message},
        "semantic": {"enabled": sem.enabled, "available": sem.available, "message": sem.message},
        "noplag": noplag,
    }
