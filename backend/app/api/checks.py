"""Check creation, status polling, and history endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import get_settings
from app.db import get_db
from app.models import AppSetting, Check, Document
from app.schemas import CheckCreateRequest, CheckSettingsSchema, CheckSummaryOut
from app.security import enforce_rate_limit, require_auth
from app.worker import enqueue_check

router = APIRouter(prefix="/checks", tags=["checks"])
_report_seq_lock = Lock()


def _next_report_number(db: Session) -> str:
    prefix = get_settings().REPORT_PREFIX
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    base = f"{prefix}-{today}-"
    with _report_seq_lock:
        existing = (
            db.query(Check.report_number)
            .filter(Check.report_number.like(f"{base}%"))
            .all()
        )
        max_seq = 0
        for (rnum,) in existing:
            tail = rnum.replace(base, "", 1)
            if tail.isdigit():
                max_seq = max(max_seq, int(tail))
        return f"{base}{max_seq + 1:04d}"


def _default_check_settings(db: Session) -> CheckSettingsSchema:
    row = db.query(AppSetting).filter(AppSetting.key == "app_defaults").first()
    if row and isinstance(row.value, dict) and isinstance(row.value.get("default_exclusions"), dict):
        return CheckSettingsSchema(**row.value["default_exclusions"])
    return CheckSettingsSchema()


def _to_summary(chk: Check, doc: Document | None) -> CheckSummaryOut:
    return CheckSummaryOut(
        id=chk.id,
        report_number=chk.report_number,
        document_id=chk.document_id,
        document_filename=doc.filename if doc else None,
        document_title=(doc.title or doc.filename) if doc else None,
        status=chk.status,
        mode=chk.mode or "PLAGIARISM_ONLY",
        stage=chk.stage,
        progress=chk.progress,
        settings=chk.settings or {},
        stage_counts=chk.stage_counts or {},
        metrics=chk.metrics or {},
        coverage=chk.coverage or {},
        ai_report=chk.ai_report,
        error=chk.error,
        created_at=chk.created_at,
        started_at=chk.started_at,
        finished_at=chk.finished_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_check(
    body: CheckCreateRequest,
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    doc = db.query(Document).filter(Document.id == body.document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen submission tidak ditemukan.")

    cfg = body.settings if body.settings is not None else _default_check_settings(db)
    report_num = _next_report_number(db)
    chk = Check(
        report_number=report_num,
        document_id=doc.id,
        status="QUEUED",
        mode=cfg.check_mode,
        stage="Antrean",
        progress=0,
        settings=cfg.model_dump(),
        stage_counts={},
        metrics={},
        coverage={},
    )
    db.add(chk)
    db.commit()
    db.refresh(chk)

    log_audit(
        db,
        actor=actor,
        action="START_CHECK",
        target_type="check",
        target_id=chk.id,
        details={
            "document_id": doc.id,
            "report_number": report_num,
            "check_mode": cfg.check_mode,
            "use_external_sources": cfg.use_external_sources,
        },
    )
    enqueue_check(chk.id)
    return {"check_id": chk.id, "report_number": chk.report_number, "status": chk.status, "mode": chk.mode}


@router.get("", response_model=list[CheckSummaryOut])
def list_checks(
    mode: str | None = None,
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[CheckSummaryOut]:
    query = (
        db.query(Check, Document)
        .outerjoin(Document, Check.document_id == Document.id)
    )
    if mode:
        query = query.filter(Check.mode == mode)
    rows = query.order_by(Check.created_at.desc()).all()
    return [_to_summary(chk, doc) for chk, doc in rows]


@router.get("/{check_id}", response_model=CheckSummaryOut)
def get_check_status(
    check_id: str,
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CheckSummaryOut:
    row = (
        db.query(Check, Document)
        .outerjoin(Document, Check.document_id == Document.id)
        .filter(Check.id == check_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Pemeriksaan tidak ditemukan.")
    return _to_summary(row[0], row[1])
