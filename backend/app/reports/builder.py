"""Single source of truth for building interactive report payloads and viewer segments."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.exclusions import build_exclusion_mask
from app.ingestion.service import load_extracted_payload
from app.models import Check, CheckSource, Document, Match, ProviderQuery, Segment
from app.schemas import CheckSettingsSchema

LAYER_PRIORITY = {
    "EXACT": 0,
    "NEAR_EXACT": 1,
    "LEXICAL": 2,
    "SEMANTIC": 3,
    "EXCLUDED": 4,
}


def build_full_report(db: Session, check_id: str) -> dict[str, Any]:
    check = db.query(Check).filter(Check.id == check_id).first()
    if check is None:
        raise HTTPException(status_code=404, detail="Pemeriksaan tidak ditemukan.")
    doc = db.query(Document).filter(Document.id == check.document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen pemeriksaan tidak ditemukan.")

    sources_rows = (
        db.query(CheckSource, Document)
        .join(Document, CheckSource.source_document_id == Document.id)
        .filter(CheckSource.check_id == check.id)
        .order_by(CheckSource.rank.asc())
        .all()
    )
    matches = (
        db.query(Match)
        .filter(Match.check_id == check.id)
        .order_by(Match.sub_char_start.asc(), Match.id.asc())
        .all()
    )
    segments = (
        db.query(Segment)
        .filter(Segment.document_id == doc.id)
        .order_by(Segment.sentence_number.asc())
        .all()
    )
    provider_queries = (
        db.query(ProviderQuery)
        .filter(ProviderQuery.check_id == check.id)
        .order_by(ProviderQuery.started_at.asc())
        .all()
    )

    doc_map = {d.id: d for _, d in sources_rows}
    missing_src_ids = {m.source_document_id for m in matches if m.source_document_id not in doc_map}
    if missing_src_ids:
        for extra_doc in db.query(Document).filter(Document.id.in_(list(missing_src_ids))).all():
            doc_map[extra_doc.id] = extra_doc

    sources_out = []
    for cs, sdoc in sources_rows:
        sources_out.append(
            {
                "rank": cs.rank,
                "source_document_id": sdoc.id,
                "title": sdoc.title or sdoc.filename,
                "filename": sdoc.filename,
                "authors": sdoc.authors or [],
                "year": sdoc.year,
                "doi": sdoc.doi,
                "url": sdoc.url,
                "source_type": sdoc.source_type,
                "access_status": sdoc.access_status,
                "provider": sdoc.provider or "local_corpus",
                "matched_words_exclusive": cs.matched_words_exclusive,
                "matched_words_total": cs.matched_words_total,
                "contribution_pct": cs.contribution_pct,
                "layers": cs.layers or {},
                "can_download_file": sdoc.role in {"CORPUS", "EXTERNAL"},
            }
        )

    matches_out = []
    for m in matches:
        sdoc = doc_map.get(m.source_document_id)
        matches_out.append(
            {
                "id": m.id,
                "source_document_id": m.source_document_id,
                "source_title": (sdoc.title or sdoc.filename) if sdoc else "Sumber",
                "layer": m.layer,
                "sub_token_start": m.sub_token_start,
                "sub_token_end": m.sub_token_end,
                "sub_char_start": m.sub_char_start,
                "sub_char_end": m.sub_char_end,
                "src_token_start": m.src_token_start,
                "src_token_end": m.src_token_end,
                "src_char_start": m.src_char_start,
                "src_char_end": m.src_char_end,
                "src_page": m.src_page,
                "matched_words": m.matched_words,
                "score": m.score,
                "sub_excerpt": m.sub_excerpt,
                "src_excerpt": m.src_excerpt,
                "excluded_reason": m.excluded_reason,
                "counted": m.counted,
            }
        )

    # Compute chapter & page distribution from actual token coverage
    counted_matches = [m for m in matches if m.counted]
    matched_token_set: set[int] = set()
    for m in counted_matches:
        matched_token_set.update(range(m.sub_token_start, m.sub_token_end))

    chapter_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total_words": 0, "matched_words": 0})
    page_stats: dict[int, dict[str, int]] = defaultdict(lambda: {"total_words": 0, "matched_words": 0})
    for seg in segments:
        lbl = seg.section_label or "Umum"
        tok_range = range(seg.token_start, seg.token_end)
        tot = len(tok_range)
        mat = sum(1 for t in tok_range if t in matched_token_set)
        chapter_stats[lbl]["total_words"] += tot
        chapter_stats[lbl]["matched_words"] += mat
        if seg.page_number is not None:
            page_stats[seg.page_number]["total_words"] += tot
            page_stats[seg.page_number]["matched_words"] += mat

    chapter_dist = [
        {
            "chapter": ch,
            "total_words": st["total_words"],
            "matched_words": st["matched_words"],
            "similarity_pct": round((st["matched_words"] / st["total_words"]) * 100.0, 2) if st["total_words"] else 0.0,
        }
        for ch, st in chapter_stats.items()
        if st["total_words"] > 0
    ]
    page_dist = [
        {
            "page": pg,
            "total_words": st["total_words"],
            "matched_words": st["matched_words"],
            "similarity_pct": round((st["matched_words"] / st["total_words"]) * 100.0, 2) if st["total_words"] else 0.0,
        }
        for pg, st in sorted(page_stats.items())
        if st["total_words"] > 0
    ]

    duration_sec = None
    if check.started_at and check.finished_at:
        duration_sec = round((check.finished_at - check.started_at).total_seconds(), 2)

    settings = get_settings()
    return {
        "app_name": settings.APP_NAME,
        "check_id": check.id,
        "report_number": check.report_number,
        "status": check.status,
        "stage": check.stage,
        "created_at": check.created_at.isoformat() if check.created_at else None,
        "started_at": check.started_at.isoformat() if check.started_at else None,
        "finished_at": check.finished_at.isoformat() if check.finished_at else None,
        "duration_seconds": duration_sec,
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "file_type": doc.file_type,
            "language": doc.language,
            "page_count": doc.page_count,
            "word_count": doc.word_count,
            "extraction_method": doc.extraction_method,
            "extraction_confidence": doc.extraction_confidence,
            "ocr_pages": doc.ocr_pages or [],
            "extra": doc.extra or {},
        },
        "settings": check.settings or {},
        "metrics": check.metrics or {},
        "coverage": check.coverage or {},
        "stage_counts": check.stage_counts or {},
        "sources": sources_out,
        "matches": matches_out,
        "analytics": {
            "by_chapter": chapter_dist,
            "by_page": page_dist,
        },
        "provider_queries": [
            {
                "provider": pq.provider,
                "query": pq.query,
                "status": pq.status,
                "result_count": pq.result_count,
                "http_status": pq.http_status,
                "error": pq.error,
                "duration_ms": pq.duration_ms,
            }
            for pq in provider_queries
        ],
    }


def build_viewer_payload(db: Session, check_id: str) -> dict[str, Any]:
    """Compute non-overlapping colored spans over original submission text with priority EXACT > NEAR_EXACT > LEXICAL > SEMANTIC > EXCLUDED."""
    check = db.query(Check).filter(Check.id == check_id).first()
    if check is None:
        raise HTTPException(status_code=404, detail="Pemeriksaan tidak ditemukan.")
    doc = db.query(Document).filter(Document.id == check.document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

    payload = load_extracted_payload(doc.id)
    text: str = payload["text"]
    tokens_meta: list[list[Any]] = payload["tokens"]
    pages = payload.get("pages", [])
    segments = (
        db.query(Segment)
        .filter(Segment.document_id == doc.id)
        .order_by(Segment.sentence_number.asc())
        .all()
    )
    matches = db.query(Match).filter(Match.check_id == check.id).all()

    cfg = CheckSettingsSchema(**(check.settings or {}))
    token_mask = build_exclusion_mask(text, tokens_meta, segments, cfg)

    # Map each character index using priority intervals via sweep-line over boundary points
    spans: list[tuple[int, int, str, int | None, str | None]] = []

    # Add excluded spans from contiguous token mask runs
    run_start: int | None = None
    run_reason: str | None = None
    for idx, reason in enumerate(token_mask):
        if reason is not None:
            if run_start is None:
                run_start = idx
                run_reason = reason
            elif reason != run_reason:
                cs = tokens_meta[run_start][1]
                ce = tokens_meta[idx - 1][2]
                spans.append((cs, ce, "EXCLUDED", None, run_reason))
                run_start = idx
                run_reason = reason
        else:
            if run_start is not None:
                cs = tokens_meta[run_start][1]
                ce = tokens_meta[idx - 1][2]
                spans.append((cs, ce, "EXCLUDED", None, run_reason))
                run_start = None
                run_reason = None
    if run_start is not None and tokens_meta:
        cs = tokens_meta[run_start][1]
        ce = tokens_meta[len(token_mask) - 1][2]
        spans.append((cs, ce, "EXCLUDED", None, run_reason))

    for m in matches:
        cat = "EXCLUDED" if m.excluded_reason else m.layer
        cs = max(0, min(m.sub_char_start, len(text)))
        ce = max(cs, min(m.sub_char_end, len(text)))
        if ce > cs:
            spans.append((cs, ce, cat, m.id, m.excluded_reason))

    if not text:
        return {"document_id": doc.id, "text": "", "pages": pages, "segments": []}

    boundaries = sorted({0, len(text)} | {s[0] for s in spans} | {s[1] for s in spans})
    out_segments: list[dict[str, Any]] = []

    for i in range(len(boundaries) - 1):
        b0, b1 = boundaries[i], boundaries[i + 1]
        if b1 <= b0:
            continue
        active = [s for s in spans if s[0] <= b0 and s[1] >= b1]
        if not active:
            cat = "PLAIN"
            match_ids: list[int] = []
            excl_reason = None
        else:
            active.sort(key=lambda s: LAYER_PRIORITY.get(s[2], 99))
            cat = active[0][2]
            excl_reason = active[0][4]
            match_ids = sorted({s[3] for s in active if s[3] is not None})

        # Coalesce adjacent segments with identical category and match_ids
        if (
            out_segments
            and out_segments[-1]["category"] == cat
            and out_segments[-1]["match_ids"] == match_ids
            and out_segments[-1]["excluded_reason"] == excl_reason
        ):
            out_segments[-1]["char_end"] = b1
            out_segments[-1]["text"] = text[out_segments[-1]["char_start"] : b1]
        else:
            out_segments.append(
                {
                    "char_start": b0,
                    "char_end": b1,
                    "text": text[b0:b1],
                    "category": cat,
                    "match_ids": match_ids,
                    "excluded_reason": excl_reason,
                }
            )

    return {
        "document_id": doc.id,
        "text": text,
        "pages": pages,
        "segments": out_segments,
    }


def build_source_viewer_payload(db: Session, check_id: str, source_id: str) -> dict[str, Any]:
    check = db.query(Check).filter(Check.id == check_id).first()
    if check is None:
        raise HTTPException(status_code=404, detail="Pemeriksaan tidak ditemukan.")
    src_doc = db.query(Document).filter(Document.id == source_id).first()
    if src_doc is None:
        raise HTTPException(status_code=404, detail="Dokumen sumber tidak ditemukan.")

    payload = load_extracted_payload(src_doc.id)
    matches = (
        db.query(Match)
        .filter(Match.check_id == check.id, Match.source_document_id == src_doc.id)
        .order_by(Match.src_char_start.asc())
        .all()
    )
    return {
        "source_document_id": src_doc.id,
        "title": src_doc.title or src_doc.filename,
        "authors": src_doc.authors or [],
        "year": src_doc.year,
        "doi": src_doc.doi,
        "url": src_doc.url,
        "text": payload["text"],
        "pages": payload.get("pages", []),
        "highlights": [
            {
                "match_id": m.id,
                "layer": m.layer,
                "src_char_start": m.src_char_start,
                "src_char_end": m.src_char_end,
                "sub_char_start": m.sub_char_start,
                "sub_char_end": m.sub_char_end,
                "src_page": m.src_page,
                "counted": m.counted,
            }
            for m in matches
        ],
    }
