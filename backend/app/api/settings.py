"""Application default exclusions & operational thresholds settings endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import get_settings
from app.db import get_db
from app.engine.semantic import get_semantic_status
from app.ingestion.ocr import get_ocr_status
from app.models import AppSetting
from app.schemas import AppSettingsPayload, CheckSettingsSchema
from app.security import require_auth

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_auth)])


def _read_settings_payload(db: Session) -> dict:
    env_cfg = get_settings()
    row = db.query(AppSetting).filter(AppSetting.key == "app_defaults").first()
    if row and isinstance(row.value, dict):
        payload = AppSettingsPayload(
            default_exclusions=CheckSettingsSchema(**row.value.get("default_exclusions", {})),
            threshold_low=float(row.value.get("threshold_low", env_cfg.THRESHOLD_LOW)),
            threshold_high=float(row.value.get("threshold_high", env_cfg.THRESHOLD_HIGH)),
        )
    else:
        payload = AppSettingsPayload(
            default_exclusions=CheckSettingsSchema(),
            threshold_low=env_cfg.THRESHOLD_LOW,
            threshold_high=env_cfg.THRESHOLD_HIGH,
        )
    ocr = get_ocr_status()
    sem = get_semantic_status()
    data = payload.model_dump()
    data["system"] = {
        "app_name": env_cfg.APP_NAME,
        "pdf_backend": env_cfg.PDF_BACKEND,
        "retention_days": env_cfg.RETENTION_DAYS,
        "ocr_available": ocr.available,
        "ocr_message": ocr.message,
        "semantic_enabled": sem.enabled,
        "semantic_available": sem.available,
        "semantic_message": sem.message,
    }
    return data


@router.get("")
def get_app_settings(db: Session = Depends(get_db)) -> dict:
    return _read_settings_payload(db)


@router.put("")
def update_app_settings(
    body: AppSettingsPayload,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == "app_defaults").first()
    val = body.model_dump()
    now = datetime.now(timezone.utc)
    if row is None:
        row = AppSetting(key="app_defaults", value=val, updated_at=now)
        db.add(row)
    else:
        row.value = val
        row.updated_at = now
    db.commit()
    log_audit(db, actor=actor, action="UPDATE_SETTINGS", target_type="settings", target_id="app_defaults", details=val)
    return _read_settings_payload(db)
