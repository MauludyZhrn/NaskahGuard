"""Dashboard real-data aggregation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Check, Document, Fingerprint, ProviderQuery, SourceAcquisition
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
        if chk.mode != "AI_ONLY" and isinstance(chk.metrics, dict) and "similarity_index" in chk.metrics
    ]
    avg_si = round(sum(si_values) / len(si_values), 2) if si_values else None

    ai_checks = [chk for chk, _ in completed_checks if isinstance(chk.ai_report, dict)]
    ai_scores = [
        float(chk.ai_report["ai_likelihood_pct"])
        for chk in ai_checks
        if chk.ai_report.get("ai_likelihood_pct") is not None
    ]
    avg_ai = round(sum(ai_scores) / len(ai_scores), 2) if ai_scores else None
    ai_class_counts: dict[str, int] = {}
    for chk in ai_checks:
        cls = str(chk.ai_report.get("classification") or "INSUFFICIENT_DATA")
        ai_class_counts[cls] = ai_class_counts.get(cls, 0) + 1

    recent_reports = [
        {
            "check_id": chk.id,
            "report_number": chk.report_number,
            "document_id": doc.id,
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "mode": chk.mode,
            "similarity_index": float(chk.metrics.get("similarity_index", 0.0)),
            "matched_words": int(chk.metrics.get("matched_words", 0)),
            "eligible_words": int(chk.metrics.get("eligible_words", 0)),
            "ai_likelihood_pct": chk.ai_report.get("ai_likelihood_pct") if isinstance(chk.ai_report, dict) else None,
            "ai_classification": chk.ai_report.get("classification") if isinstance(chk.ai_report, dict) else None,
            "ai_classification_label": chk.ai_report.get("classification_label") if isinstance(chk.ai_report, dict) else None,
            "finished_at": chk.finished_at.isoformat() if chk.finished_at else None,
        }
        for chk, doc in completed_checks[:12]
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

    total_queries = db.query(func.count(ProviderQuery.id)).scalar() or 0
    total_acquisitions = db.query(func.count(SourceAcquisition.id)).scalar() or 0
    trend = [
        {
            "report_number": chk.report_number,
            "mode": chk.mode,
            "similarity_index": float(chk.metrics.get("similarity_index", 0.0)),
            "ai_likelihood_pct": chk.ai_report.get("ai_likelihood_pct") if isinstance(chk.ai_report, dict) else None,
            "date": chk.finished_at.strftime("%d/%m") if chk.finished_at else "-",
        }
        for chk, _ in reversed(completed_checks[:12])
    ]

    return {
        "total_documents_checked": total_checked,
        "total_submissions": submission_count,
        "average_similarity": avg_si,
        "average_ai_likelihood": avg_ai,
        "ai_stats": {
            "total_ai_analyzed": len(ai_checks),
            "total_ai_only": sum(1 for chk, _ in completed_checks if chk.mode == "AI_ONLY"),
            "total_combined": sum(1 for chk, _ in completed_checks if chk.mode == "COMBINED"),
            "total_plagiarism_only": sum(1 for chk, _ in completed_checks if chk.mode == "PLAGIARISM_ONLY"),
            "classification_counts": ai_class_counts,
        },
        "recent_reports": recent_reports,
        "recent_activity": recent_activity,
        "trend": trend,
        "provider_stats": {
            "total_queries": total_queries,
            "total_acquisitions": total_acquisitions,
        },
        "corpus_stats": {
            "total_documents": len(corpus_docs),
            "fulltext_sources_available": sum(1 for d in corpus_docs if d.indexing_status in {"FULLTEXT_INDEXED", "MATCH_VERIFIED", "INDEXED"}),
            "total_words": total_corpus_words,
            "total_fingerprints": fp_count,
        },
    }
