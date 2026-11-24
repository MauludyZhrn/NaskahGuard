"""Audit log query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog
from app.security import require_auth

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_auth)])


@router.get("")
def list_audit_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    rows = db.query(AuditLog).order_by(AuditLog.ts.desc()).limit(safe_limit).all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "actor": r.actor,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "details": r.details or {},
        }
        for r in rows
    ]
