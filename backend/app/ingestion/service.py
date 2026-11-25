"""High-level ingestion orchestrator: saves file, extracts text, tokenizes, segments, and indexes corpus."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.minhash_lsh import compute_minhash_bytes, invalidate_lsh_cache
from app.engine.winnowing import winnow_tokens
from app.ingestion.docx_extractor import extract_docx
from app.ingestion.html_extractor import extract_html
from app.ingestion.language import detect_language
from app.ingestion.pdf import ExtractedDocument, extract_pdf
from app.ingestion.segment import SegmentSpan, segment_document
from app.ingestion.structure import annotate_structure
from app.ingestion.tokenize import TokenSpan, tokenize_with_offsets
from app.ingestion.txt import extract_txt
from app.ingestion.validators import ValidatedUpload, resolve_safe_storage_path
from app.ingestion.xml_extractor import extract_xml
from app.models import Document, Fingerprint, Segment


@dataclass
class ExtractedPayload:
    text: str
    pages: list[dict[str, Any]]
    tokens: list[list[Any]]  # [norm, char_start, char_end]
    segments: list[SegmentSpan]


def _run_extractor(file_type: str, file_path: Path) -> ExtractedDocument:
    if file_type == "pdf":
        return extract_pdf(file_path)
    if file_type == "docx":
        return extract_docx(file_path)
    if file_type == "txt":
        return extract_txt(file_path)
    if file_type == "html":
        return extract_html(file_path)
    if file_type == "xml":
        return extract_xml(file_path)
    raise ValueError(f"Tipe file tidak dikenali: {file_type}")


def get_extracted_json_path(doc_id: str) -> Path:
    settings = get_settings()
    extracted_dir = resolve_safe_storage_path(settings.storage_path, "extracted")
    extracted_dir.mkdir(parents=True, exist_ok=True)
    return resolve_safe_storage_path(settings.storage_path, "extracted", f"{doc_id}.json")


def load_extracted_payload(doc_id: str) -> dict[str, Any]:
    path = get_extracted_json_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Data hasil ekstraksi dokumen tidak ditemukan.")
    return json.loads(path.read_text(encoding="utf-8"))


def index_document_for_corpus(
    db: Session,
    doc: Document,
    norm_tokens: list[str],
) -> int:
    """Compute and persist Winnowing fingerprints and MinHash signature for a corpus/external doc."""
    db.query(Fingerprint).filter(Fingerprint.document_id == doc.id).delete()
    fps = winnow_tokens(norm_tokens)
    if fps:
        db.bulk_insert_mappings(
            Fingerprint,
            [{"document_id": doc.id, "hash": h, "token_pos": pos} for h, pos in fps],
        )
    doc.minhash = compute_minhash_bytes(norm_tokens)
    invalidate_lsh_cache()
    return len(fps)


def normalize_title_key(title: str | None) -> str | None:
    if not title:
        return None
    cleaned = " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in title).split())
    return cleaned[:500] if cleaned else None


def ingest_validated_upload(
    db: Session,
    upload: ValidatedUpload,
    *,
    role: str,
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    url: str | None = None,
    canonical_url: str | None = None,
    license_name: str | None = None,
    indexing_status: str = "FULLTEXT_INDEXED",
    alternate_urls: list[str] | None = None,
    source_type: str = "local_document",
    access_status: str = "INDEXED_LOCALLY",
    provider: str | None = None,
    external_id: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> Document:
    """Persist upload to local storage, extract text/tokens/segments, and store DB records."""
    existing = (
        db.query(Document)
        .filter(Document.file_hash == upload.file_hash, Document.role == role)
        .first()
    )
    if existing is not None:
        return existing

    settings = get_settings()
    uploads_dir = resolve_safe_storage_path(settings.storage_path, "uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    ext = f".{upload.file_type}"
    stored_name = f"{doc_id}{ext}"
    stored_path = resolve_safe_storage_path(settings.storage_path, "uploads", stored_name)
    stored_path.write_bytes(upload.raw_bytes)

    try:
        extracted = _run_extractor(upload.file_type, stored_path)
    except Exception:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise

    tokens: list[TokenSpan] = tokenize_with_offsets(extracted.text)
    norm_tokens = [t.norm for t in tokens]
    language = detect_language(norm_tokens)

    segments = segment_document(extracted.text, extracted.pages, tokens)
    is_docx_no_breaks = upload.file_type == "docx" and not extracted.extra.get("explicit_page_breaks_found", False)
    annotate_structure(extracted.text, extracted.pages, segments, is_docx_without_breaks=is_docx_no_breaks)

    # Save immutable original text + token offsets to JSON
    extracted_payload = {
        "text": extracted.text,
        "pages": [
            {
                "number": p.number,
                "char_start": p.char_start,
                "char_end": p.char_end,
                "used_ocr": p.used_ocr,
                "ocr_confidence": p.ocr_confidence,
            }
            for p in extracted.pages
        ],
        "tokens": [[t.norm, t.char_start, t.char_end] for t in tokens],
        "paragraphs_count": max((s.paragraph_number for s in segments), default=0),
    }
    json_path = get_extracted_json_path(doc_id)
    json_path.write_text(json.dumps(extracted_payload, ensure_ascii=False), encoding="utf-8")

    resolved_title = (title.strip() if title else None) or extracted.title or upload.clean_filename
    resolved_doi = (doi.strip() if doi else None) or extracted.extra.get("doi")
    resolved_canon = (canonical_url.strip() if canonical_url else None) or extracted.extra.get("canonical_url") or url

    doc = Document(
        id=doc_id,
        role=role,
        filename=upload.clean_filename,
        stored_name=stored_name,
        file_hash=upload.file_hash,
        file_type=upload.file_type,
        mime=upload.mime,
        size_bytes=upload.size_bytes,
        language=language,
        page_count=max(1, len(extracted.pages)),
        word_count=len(tokens),
        title=resolved_title[:512] if resolved_title else None,
        normalized_title=normalize_title_key(resolved_title),
        authors=authors if authors is not None else extracted.authors,
        year=year,
        doi=resolved_doi[:255] if resolved_doi else None,
        url=url.strip() if url else None,
        canonical_url=resolved_canon[:1024] if resolved_canon else None,
        license=license_name[:255] if license_name else None,
        indexing_status=indexing_status,
        alternate_urls=alternate_urls or ([url.strip()] if url else []),
        source_type=source_type,
        access_status=access_status,
        extraction_method=extracted.extraction_method,
        extraction_confidence=extracted.extraction_confidence,
        ocr_pages=extracted.ocr_pages,
        provider=provider,
        external_id=external_id,
        retrieved_at=datetime.now(timezone.utc) if provider else None,
        extra={**dict(extracted.extra or {}), **dict(extra_metadata or {})},
    )
    db.add(doc)
    db.flush()

    if segments:
        db.bulk_insert_mappings(
            Segment,
            [
                {
                    "document_id": doc_id,
                    "page_number": s.page_number,
                    "paragraph_number": s.paragraph_number,
                    "sentence_number": s.sentence_number,
                    "char_start": s.char_start,
                    "char_end": s.char_end,
                    "token_start": s.token_start,
                    "token_end": s.token_end,
                    "original_text": s.original_text,
                    "normalized_text": s.normalized_text,
                    "section_label": s.section_label,
                    "zone": s.zone,
                }
                for s in segments
            ],
        )

    if role in {"CORPUS", "EXTERNAL"}:
        index_document_for_corpus(db, doc, norm_tokens)

    db.commit()
    db.refresh(doc)
    return doc
