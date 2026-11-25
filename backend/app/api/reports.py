"""Report viewing and PDF/HTML/JSON export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.db import get_db
from app.reports.builder import build_full_report, build_source_viewer_payload, build_viewer_payload
from app.reports.html_report import render_html_bytes
from app.reports.json_report import render_json_bytes
from app.reports.pdf_report import render_pdf_bytes
from app.security import require_auth

router = APIRouter(prefix="/checks", tags=["reports"], dependencies=[Depends(require_auth)])


@router.get("/{check_id}/report")
def get_check_report(check_id: str, db: Session = Depends(get_db)) -> dict:
    return build_full_report(db, check_id)


@router.get("/{check_id}/viewer")
def get_check_viewer(check_id: str, db: Session = Depends(get_db)) -> dict:
    return build_viewer_payload(db, check_id)


@router.get("/{check_id}/sources/{source_id}/viewer")
def get_source_viewer(check_id: str, source_id: str, db: Session = Depends(get_db)) -> dict:
    return build_source_viewer_payload(db, check_id, source_id)


@router.get("/{check_id}/export.json")
def export_report_json(
    check_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    report = build_full_report(db, check_id)
    data = render_json_bytes(report)
    rnum = report["report_number"]
    log_audit(db, actor=actor, action="EXPORT_JSON", target_type="check", target_id=check_id)
    return Response(
        content=data,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{rnum}.json"'},
    )


@router.get("/{check_id}/export.html")
def export_report_html(
    check_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    report = build_full_report(db, check_id)
    try:
        viewer = build_viewer_payload(db, check_id)
    except Exception:
        viewer = None
    data = render_html_bytes(report, viewer=viewer)
    rnum = report["report_number"]
    log_audit(db, actor=actor, action="EXPORT_HTML", target_type="check", target_id=check_id)
    return Response(
        content=data,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{rnum}.html"'},
    )


@router.get("/{check_id}/export.pdf")
def export_report_pdf(
    check_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    report = build_full_report(db, check_id)
    try:
        viewer = build_viewer_payload(db, check_id)
    except Exception:
        viewer = None
    data = render_pdf_bytes(report, viewer=viewer)
    rnum = report["report_number"]
    log_audit(db, actor=actor, action="EXPORT_PDF", target_type="check", target_id=check_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{rnum}.pdf"'},
    )
