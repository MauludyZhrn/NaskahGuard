"""Local source corpus management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import get_settings
from app.db import get_db
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import read_and_validate_upload
from app.models import Document, Fingerprint
from app.schemas import DocumentOut
from app.security import enforce_rate_limit, require_auth

router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_corpus_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    authors: str | None = Form(default=None),
    year: int | None = Form(default=None),
    doi: str | None = Form(default=None),
    url: str | None = Form(default=None),
    source_type: str = Form(default="local_document"),
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> Document:
    settings = get_settings()
    validated = await read_and_validate_upload(file, settings.max_upload_bytes)
    author_list = [a.strip() for a in authors.split(",") if a.strip()] if authors else None
    doc = ingest_validated_upload(
        db,
        validated,
        role="CORPUS",
        title=title,
        authors=author_list,
        year=year,
        doi=doi,
        url=url,
        source_type=source_type,
        access_status="INDEXED_LOCALLY",
    )
    log_audit(
        db,
        actor=actor,
        action="UPLOAD_CORPUS",
        target_type="document",
        target_id=doc.id,
        details={"filename": doc.filename, "title": doc.title, "word_count": doc.word_count},
    )
    return doc


@router.get("", response_model=list[DocumentOut])
def list_corpus(
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.role.in_(["CORPUS", "EXTERNAL"]))
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/stats")
def corpus_stats(
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    docs = db.query(Document).filter(Document.role.in_(["CORPUS", "EXTERNAL"])).all()
    fp_count = db.query(func.count(Fingerprint.id)).scalar() or 0
    by_lang: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total_words = 0
    for d in docs:
        total_words += d.word_count
        by_lang[d.language] = by_lang.get(d.language, 0) + 1
        by_type[d.source_type] = by_type.get(d.source_type, 0) + 1
    return {
        "total_documents": len(docs),
        "total_words": total_words,
        "total_fingerprints": fp_count,
        "by_language": by_lang,
        "by_source_type": by_type,
    }
