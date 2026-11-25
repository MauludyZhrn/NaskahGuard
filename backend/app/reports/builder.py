"""Single source of truth for building interactive report payloads and viewer segments."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.exclusions import build_exclusion_mask
from app.ingestion.service import load_extracted_payload
from app.models import Check, CheckSource, Document, Match, ProviderQuery, Segment, SourceAcquisition
from app.reports.integrity_flags import (
    classify_source_category,
    color_for_rank,
    compute_source_category_summary,
    detect_integrity_flags,
    extract_active_filters,
)
from app.schemas import CheckSettingsSchema

LAYER_PRIORITY = {
    "EXCLUDED": 0,
    "EXACT": 1,
    "NEAR_EXACT": 2,
    "LEXICAL": 3,
    "SEMANTIC": 4,
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
    acquisitions = (
        db.query(SourceAcquisition)
        .filter(SourceAcquisition.check_id == check.id)
        .order_by(SourceAcquisition.id.asc())
        .all()
    )

    doc_map = {d.id: d for _, d in sources_rows}
    missing_src_ids = {m.source_document_id for m in matches if m.source_document_id not in doc_map}
    if missing_src_ids:
        for extra_doc in db.query(Document).filter(Document.id.in_(list(missing_src_ids))).all():
            doc_map[extra_doc.id] = extra_doc

    sources_out = []
    rank_by_source_id: dict[str, int] = {}
    color_by_source_id: dict[str, dict[str, str]] = {}
    for cs, sdoc in sources_rows:
        palette = color_for_rank(cs.rank)
        cat_key, cat_label = classify_source_category(sdoc.source_type, sdoc.provider)
        rank_by_source_id[sdoc.id] = cs.rank
        color_by_source_id[sdoc.id] = palette
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
                "canonical_url": sdoc.canonical_url or sdoc.url,
                "alternate_urls": sdoc.alternate_urls or [],
                "license": sdoc.license,
                "indexing_status": sdoc.indexing_status,
                "source_type": sdoc.source_type,
                "category_key": cat_key,
                "category_label": cat_label,
                "color_hex": palette["badge"],
                "highlight_hex": palette["highlight"],
                "chip_bg_hex": palette["chip_bg"],
                "chip_text_hex": palette["chip_text"],
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
        s_rank = rank_by_source_id.get(m.source_document_id)
        s_pal = color_by_source_id.get(m.source_document_id)
        matches_out.append(
            {
                "id": m.id,
                "source_document_id": m.source_document_id,
                "source_rank": s_rank,
                "source_color": s_pal["badge"] if s_pal else None,
                "source_highlight": s_pal["highlight"] if s_pal else None,
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
    metrics = check.metrics or {}
    coverage = check.coverage or {}
    mode = check.mode or "PLAGIARISM_ONLY"
    ai_rep = check.ai_report
    si = float(metrics.get("similarity_index", 0.0))
    matched_w = int(metrics.get("matched_words", 0))
    eligible_w = int(metrics.get("eligible_words", doc.word_count or 0))
    fulltext_cnt = int((coverage.get("source_metrics") or {}).get("fulltext_compared", coverage.get("total_sources_compared", 0)) or 0)

    if mode == "AI_ONLY":
        sim_q = "Mode Deteksi Tulisan AI tidak menjalankan perbandingan kemiripan plagiasi."
        src_q = "Tidak mencari sumber kemiripan karena fokus pemeriksaan adalah pola tulisan AI."
        cov_q = "Pemeriksaan difokuskan pada analisis gaya bahasa dan entropi teks secara lokal."
    else:
        sim_q = f"Indeks kemiripan sebesar {si:.1f}% ({matched_w:,} dari {eligible_w:,} kata yang diperiksa cocok dengan sumber)."
        src_q = (
            f"Ditemukan {len(sources_out)} sumber yang memiliki kecocokan terverifikasi."
            if sources_out
            else "Tidak ditemukan sumber dengan kecocokan teks pada korpus yang diperiksa."
        )
        cov_q = f"Sebanyak {fulltext_cnt} dokumen pembanding berteks lengkap dibandingkan terhadap naskah."

    if ai_rep:
        cls_label = str(ai_rep.get("classification_label") or "Tidak Diketahui")
        ai_pct = ai_rep.get("ai_likelihood_pct")
        ai_q = (
            f"{cls_label} (indikasi pola AI sekitar {ai_pct:.1f}% — bersifat probabilistik, bukan vonis)."
            if ai_pct is not None
            else str(ai_rep.get("summary_id") or "Teks terlalu singkat untuk disimpulkan.")
        )
    else:
        ai_q = "Deteksi tulisan AI tidak dijalankan pada mode pemeriksaan ini."

    review_q = (
        f"Periksa {len(matches_out)} bagian teks yang ditandai"
        + (f" serta {len(ai_rep.get('highlights', []))} paragraf terindikasi pola AI." if ai_rep and ai_rep.get("highlights") else ".")
    )

    try:
        ext_payload = load_extracted_payload(doc.id)
        raw_text = str(ext_payload.get("text") or "")
        raw_pages = ext_payload.get("pages") or []
    except Exception:
        raw_text = ""
        raw_pages = []

    integrity_flags = detect_integrity_flags(raw_text, raw_pages)
    source_categories = compute_source_category_summary(sources_out)
    active_filters = extract_active_filters(check.settings)

    return {
        "app_name": settings.APP_NAME,
        "check_id": check.id,
        "report_number": check.report_number,
        "status": check.status,
        "mode": mode,
        "stage": check.stage,
        "created_at": check.created_at.isoformat() if check.created_at else None,
        "started_at": check.started_at.isoformat() if check.started_at else None,
        "finished_at": check.finished_at.isoformat() if check.finished_at else None,
        "duration_seconds": duration_sec,
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "stored_name": doc.stored_name,
            "title": doc.title or doc.filename,
            "authors": doc.authors or [],
            "file_type": doc.file_type,
            "size_bytes": doc.size_bytes,
            "language": doc.language,
            "page_count": doc.page_count,
            "word_count": doc.word_count,
            "character_count": len(raw_text),
            "extraction_method": doc.extraction_method,
            "extraction_confidence": doc.extraction_confidence,
            "ocr_pages": doc.ocr_pages or [],
            "extra": doc.extra or {},
        },
        "settings": check.settings or {},
        "active_filters": active_filters,
        "source_categories": source_categories,
        "integrity_flags": integrity_flags,
        "metrics": metrics,
        "coverage": coverage,
        "ai_report": ai_rep,
        "plain_summary": {
            "similarity_answer": sim_q,
            "sources_answer": src_q,
            "ai_answer": ai_q,
            "review_answer": review_q,
            "coverage_answer": cov_q,
        },
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
        "acquisitions": [
            {
                "id": acq.id,
                "provider": acq.provider,
                "query": acq.query,
                "title": acq.title,
                "authors": acq.authors or [],
                "year": acq.year,
                "doi": acq.doi,
                "source_url": acq.source_url,
                "canonical_url": acq.canonical_url,
                "source_type": acq.source_type,
                "file_type": acq.file_type,
                "license": acq.license,
                "status": acq.status,
                "used_playwright": acq.used_playwright,
                "document_id": acq.document_id,
                "error": acq.error,
                "duration_ms": acq.duration_ms,
            }
            for acq in acquisitions
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
    check_sources = db.query(CheckSource).filter(CheckSource.check_id == check.id).all()
    rank_map = {cs.source_document_id: cs.rank for cs in check_sources}
    match_rank_map = {m.id: rank_map.get(m.source_document_id) for m in matches}

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
            primary_rank = None
            primary_color = None
            primary_highlight = None
            for mid in match_ids:
                r = match_rank_map.get(mid)
                if r is not None:
                    primary_rank = r
                    pal = color_for_rank(r)
                    primary_color = pal["badge"]
                    primary_highlight = pal["highlight"]
                    break
            out_segments.append(
                {
                    "char_start": b0,
                    "char_end": b1,
                    "text": text[b0:b1],
                    "category": cat,
                    "match_ids": match_ids,
                    "excluded_reason": excl_reason,
                    "source_rank": primary_rank,
                    "source_color": primary_color,
                    "source_highlight": primary_highlight,
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
