"""Dashboard real-data aggregation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Check, Document, Fingerprint
from app.security import require_auth

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])


@router.get("")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    completed_checks = (
        db.query(Check, Document)
        .join(Document, Check.document_id == Document.id)
        .filter(Check.status == "COMPLETED")
        .order_by(Check.finished_at.desc())
        .all()
    )

    total_checked = len(completed_checks)
    si_values = [
        float(chk.metrics.get("similarity_index", 0.0))
        for chk, _ in completed_checks
        if isinstance(chk.metrics, dict) and "similarity_index" in chk.metrics
    ]
    avg_si = round(sum(si_values) / len(si_values), 2) if si_values else None

    recent_reports = [
        {
            "check_id": chk.id,
            "report_number": chk.report_number,
            "document_id": doc.id,
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "similarity_index": float(chk.metrics.get("similarity_index", 0.0)),
            "matched_words": int(chk.metrics.get("matched_words", 0)),
            "eligible_words": int(chk.metrics.get("eligible_words", 0)),
            "finished_at": chk.finished_at.isoformat() if chk.finished_at else None,
        }
        for chk, doc in completed_checks[:8]
    ]

    corpus_docs = db.query(Document).filter(Document.role.in_(["CORPUS", "EXTERNAL"])).all()
    fp_count = db.query(func.count(Fingerprint.id)).scalar() or 0
    total_corpus_words = sum(d.word_count for d in corpus_docs)

    submission_count = db.query(func.count(Document.id)).filter(Document.role == "SUBMISSION").scalar() or 0

    audits = db.query(AuditLog).order_by(AuditLog.ts.desc()).limit(12).all()
    recent_activity = [
        {
            "id": a.id,
            "ts": a.ts.isoformat() if a.ts else None,
            "actor": a.actor,
            "action": a.action,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "details": a.details or {},
        }
        for a in audits
    ]

    return {
        "total_documents_checked": total_checked,
        "total_submissions": submission_count,
        "average_similarity": avg_si,
        "recent_reports": recent_reports,
        "recent_activity": recent_activity,
        "corpus_stats": {
            "total_documents": len(corpus_docs),
            "total_words": total_corpus_words,
            "total_fingerprints": fp_count,
        },
    }
