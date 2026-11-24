"""Submission document management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import get_settings
from app.db import get_db
from app.engine.minhash_lsh import invalidate_lsh_cache
from app.ingestion.service import ingest_validated_upload, load_extracted_payload
from app.ingestion.validators import read_and_validate_upload, resolve_safe_storage_path
from app.models import Document, Segment
from app.schemas import DocumentOut
from app.security import enforce_rate_limit, require_auth
from app.worker import delete_document_artifacts

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> Document:
    settings = get_settings()
    validated = await read_and_validate_upload(file, settings.max_upload_bytes)
    doc = ingest_validated_upload(db, validated, role="SUBMISSION")
    log_audit(
        db,
        actor=actor,
        action="UPLOAD_DOCUMENT",
        target_type="document",
        target_id=doc.id,
        details={"filename": doc.filename, "word_count": doc.word_count, "file_type": doc.file_type},
    )
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    role: str | None = "SUBMISSION",
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[Document]:
    q = db.query(Document)
    if role:
        q = q.filter(Document.role == role.upper())
    return q.order_by(Document.created_at.desc()).all()


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str,
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    return doc


@router.get("/{doc_id}/text")
def get_document_text(
    doc_id: str,
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    payload = load_extracted_payload(doc.id)
    segs = (
        db.query(Segment)
        .filter(Segment.document_id == doc.id)
        .order_by(Segment.sentence_number.asc())
        .all()
    )
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "text": payload["text"],
        "pages": payload["pages"],
        "segments": [
            {
                "id": s.id,
                "page_number": s.page_number,
                "paragraph_number": s.paragraph_number,
                "sentence_number": s.sentence_number,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "section_label": s.section_label,
                "zone": s.zone,
            }
            for s in segs
        ],
    }


@router.get("/{doc_id}/file")
def download_document_file(
    doc_id: str,
    _actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    settings = get_settings()
    path = resolve_safe_storage_path(settings.storage_path, "uploads", doc.stored_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Berkas fisik dokumen tidak tersedia.")
    return FileResponse(
        path=str(path),
        media_type=doc.mime,
        filename=doc.filename,
    )


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
    fname = doc.filename
    role = doc.role
    delete_document_artifacts(doc)
    db.delete(doc)
    db.commit()
    invalidate_lsh_cache()
    log_audit(
        db,
        actor=actor,
        action="DELETE_DOCUMENT",
        target_type="document",
        target_id=doc_id,
        details={"filename": fname, "role": role},
    )
    return {"deleted": True, "document_id": doc_id}
