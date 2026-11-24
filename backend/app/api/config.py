"""Public runtime configuration endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.engine.semantic import get_semantic_status
from app.ingestion.ocr import get_ocr_status
from app.security import require_auth

router = APIRouter(tags=["config"], dependencies=[Depends(require_auth)])


@router.get("/config")
def get_public_config() -> dict:
    settings = get_settings()
    ocr = get_ocr_status()
    sem = get_semantic_status()
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "pdf_backend": settings.PDF_BACKEND,
        "ocr_available": ocr.available,
        "ocr_message": ocr.message,
        "semantic_enabled": sem.enabled,
        "semantic_available": sem.available,
        "semantic_message": sem.message,
        "retention_days": settings.RETENTION_DAYS,
        "threshold_low": settings.THRESHOLD_LOW,
        "threshold_high": settings.THRESHOLD_HIGH,
    }
