"""Audit logging helper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        actor=actor[:128],
        action=action[:64],
        target_type=target_type[:32],
        target_id=target_id[:64] if target_id else None,
        details=details or {},
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
