"""End-to-end multi-layer check execution pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.exact import RawMatch, find_exact_matches
from app.engine.exclusions import build_exclusion_mask
from app.engine.lexical import find_bm25_candidates, find_lexical_matches
from app.engine.minhash_lsh import query_minhash_candidates
from app.engine.near_exact import find_near_exact_matches
from app.engine.scoring import compute_scores
from app.engine.semantic import find_semantic_candidates, get_semantic_status
from app.engine.winnowing import retrieve_winnowing_candidates, winnow_tokens
from app.ingestion.service import index_document_for_corpus, load_extracted_payload
from app.models import AppSetting, Check, CheckSource, Document, Match, Segment
from app.schemas import CheckSettingsSchema
from app.sources.local_corpus import LocalCorpusProvider
from app.sources.registry import discover_external_sources


def _page_for_char(char_pos: int, pages: list[dict[str, Any]]) -> int | None:
    for p in pages:
        if p["char_start"] <= char_pos <= p["char_end"]:
            return int(p["number"])
    return int(pages[-1]["number"]) if pages else None


def _load_thresholds(db: Session) -> tuple[float, float]:
    settings = get_settings()
    row = db.query(AppSetting).filter(AppSetting.key == "app_defaults").first()
    if row and isinstance(row.value, dict):
        low = float(row.value.get("threshold_low", settings.THRESHOLD_LOW))
        high = float(row.value.get("threshold_high", settings.THRESHOLD_HIGH))
        return low, high
    return settings.THRESHOLD_LOW, settings.THRESHOLD_HIGH


def _update_progress(db: Session, check: Check, stage: str, progress: int, stage_counts: dict[str, Any]) -> None:
    check.stage = stage
    check.progress = progress
    check.stage_counts = dict(stage_counts)
    db.commit()


def run_check_pipeline(db: Session, check_id: str) -> None:
    """Execute full 12-stage check pipeline synchronously inside a worker session."""
    check = db.query(Check).filter(Check.id == check_id).first()
    if check is None:
        return

    doc = db.query(Document).filter(Document.id == check.document_id).first()
    if doc is None:
        check.status = "FAILED"
        check.error = "Dokumen submission tidak ditemukan."
        check.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    try:
        check.status = "PROCESSING"
        check.started_at = datetime.now(timezone.utc)
        cfg = CheckSettingsSchema(**(check.settings or {}))

        sub_payload = load_extracted_payload(doc.id)
        sub_text: str = sub_payload["text"]
        sub_tokens_meta: list[list[Any]] = sub_payload["tokens"]
        sub_norm_tokens = [t[0] for t in sub_tokens_meta]
        sub_segments = (
            db.query(Segment)
            .filter(Segment.document_id == doc.id)
            .order_by(Segment.sentence_number)
            .all()
        )

        stage_counts: dict[str, Any] = {
            "upload": {"filename": doc.filename, "size_bytes": doc.size_bytes},
            "validation": {"file_type": doc.file_type, "file_hash": doc.file_hash[:12]},
            "extraction": {
                "pages": doc.page_count,
                "chars": len(sub_text),
                "ocr_pages": len(doc.ocr_pages or []),
            },
            "normalization": {"tokens": len(sub_norm_tokens)},
            "segmentation": {
                "paragraphs": int(sub_payload.get("paragraphs_count", 0)),
                "sentences": len(sub_segments),
            },
        }
        _update_progress(db, check, "Penemuan Sumber", 25, stage_counts)

        # Stage 6: Source Discovery
        local_provider = LocalCorpusProvider(
            db,
            include_submissions=cfg.compare_with_previous_submissions,
            exclude_doc_id=doc.id,
        )
        local_doc_ids = local_provider.list_eligible_doc_ids()
        all_source_ids = set(local_doc_ids)

        ext_queries = 0
        ext_results = 0
        ext_meta_records = []
        ext_denied = 0
        ext_failed = 0
        if cfg.use_external_sources and cfg.external_providers:
            ext_summary = discover_external_sources(
                db,
                check_id=check.id,
                submission_doc=doc,
                submission_segments=sub_segments,
                provider_names=cfg.external_providers,
            )
            all_source_ids.update(ext_summary.external_fulltext_doc_ids)
            ext_queries = ext_summary.queries_executed
            ext_meta_records = ext_summary.metadata_only_records
            ext_results = len(ext_summary.external_fulltext_doc_ids) + len(ext_meta_records)
            ext_denied = ext_summary.access_denied_count
            ext_failed = ext_summary.fetch_failed_count

        stage_counts["source_discovery"] = {
            "local_docs": len(local_doc_ids),
            "external_queries": ext_queries,
            "external_results": ext_results,
            "full_text_docs": len(all_source_ids),
            "metadata_only": len(ext_meta_records),
        }
        _update_progress(db, check, "Retrieval Kandidat", 45, stage_counts)

        # Stage 7: Candidate Retrieval (Winnowing + MinHash LSH + BM25)
        sub_fps = winnow_tokens(sub_norm_tokens)
        win_hits = retrieve_winnowing_candidates(db, sub_fps, allowed_doc_ids=all_source_ids)
        mh_hits = query_minhash_candidates(db, sub_norm_tokens, allowed_doc_ids=all_source_ids)

        candidate_ids_ordered: list[str] = []
        seen_cands: set[str] = set()
        for cid, _ in win_hits:
            if cid not in seen_cands:
                seen_cands.add(cid)
                candidate_ids_ordered.append(cid)
        for cid, _ in mh_hits:
            if cid not in seen_cands:
                seen_cands.add(cid)
                candidate_ids_ordered.append(cid)

        bm25_hits = find_bm25_candidates(
            db,
            sub_norm_tokens,
            all_source_ids,
            exclude_doc_ids=seen_cands,
            top_k=5,
        )
        for cid in bm25_hits:
            if cid not in seen_cands:
                seen_cands.add(cid)
                candidate_ids_ordered.append(cid)

        # Guarantee small local corpora (<= 10 docs) are never missed by fingerprint length edge cases
        if len(all_source_ids) <= 10:
            for cid in sorted(all_source_ids):
                if cid not in seen_cands:
                    seen_cands.add(cid)
                    candidate_ids_ordered.append(cid)

        stage_counts["candidate_retrieval"] = {
            "candidates": len(candidate_ids_ordered),
            "winnowing": len(win_hits),
            "minhash": len(mh_hits),
            "bm25": len(bm25_hits),
        }
        _update_progress(db, check, "Pencocokan & Alignment", 65, stage_counts)

        # Stage 8 & 9: Multi-layer Matching & Passage Alignment
        exact_matches_all: list[RawMatch] = []
        near_matches_all: list[RawMatch] = []
        src_payloads: dict[str, dict[str, Any]] = {}

        for src_id in candidate_ids_ordered:
            try:
                src_payload = load_extracted_payload(src_id)
            except Exception:
                continue
            src_payloads[src_id] = src_payload
            src_tokens = [t[0] for t in src_payload["tokens"]]
            if not src_tokens:
                continue

            em = find_exact_matches(
                sub_norm_tokens,
                src_tokens,
                src_id,
                min_match_words=cfg.min_match_words,
            )
            exact_matches_all.extend(em)

            nm = find_near_exact_matches(
                sub_norm_tokens,
                src_tokens,
                src_id,
                em,
                min_match_words=cfg.min_match_words,
            )
            near_matches_all.extend(nm)

        exact_near_covered: set[int] = set()
        for m in exact_matches_all + near_matches_all:
            exact_near_covered.update(m.counted_token_indices)

        cand_segments = (
            db.query(Segment)
            .filter(Segment.document_id.in_(candidate_ids_ordered))
            .all()
            if candidate_ids_ordered
            else []
        )
        lexical_matches = find_lexical_matches(sub_segments, cand_segments, exact_near_covered)
        semantic_matches, semantic_status = find_semantic_candidates(
            sub_segments, cand_segments, exact_near_covered
        )

        all_raw_matches = exact_matches_all + near_matches_all + lexical_matches + semantic_matches
        stage_counts["similarity_matching"] = {
            "exact_raw": len(exact_matches_all),
            "near_exact_raw": len(near_matches_all),
            "lexical_raw": len(lexical_matches),
            "semantic_raw": len(semantic_matches),
        }
        stage_counts["passage_alignment"] = {
            "aligned_passages": len(all_raw_matches),
        }
        _update_progress(db, check, "Penghapusan Overlap & Skor", 85, stage_counts)

        # Stage 10 & 11: Exclusion Mask, Overlap Removal, and Scoring
        token_mask = build_exclusion_mask(sub_text, sub_tokens_meta, sub_segments, cfg)
        threshold_low, threshold_high = _load_thresholds(db)

        scoring = compute_scores(
            all_matches=all_raw_matches,
            token_mask=token_mask,
            settings=cfg,
            threshold_low=threshold_low,
            threshold_high=threshold_high,
            full_text_sources_compared=len(all_source_ids),
            metadata_only_sources=len(ext_meta_records),
            access_denied_sources=ext_denied,
            fetch_failed_sources=ext_failed,
            semantic_status_msg=semantic_status.message,
        )

        # Calculate duplicate overlap tokens removed
        counted_raw_token_sum = sum(
            len(m.counted_token_indices)
            for idx, m in enumerate(all_raw_matches)
            if scoring.counted_match_flags[idx][0]
        )
        duplicate_removed = max(0, counted_raw_token_sum - scoring.metrics["matched_words"])

        stage_counts["overlap_removal"] = {
            "passages_before": len(all_raw_matches),
            "verified_passages": sum(1 for c, _ in scoring.counted_match_flags if c),
            "duplicate_tokens_removed": duplicate_removed,
        }
        stage_counts["score_calculation"] = {
            "matched_words": scoring.metrics["matched_words"],
            "eligible_words": scoring.metrics["eligible_words"],
            "similarity_index": scoring.metrics["similarity_index"],
        }

        # Persist Matches & CheckSources (clear previous if re-run)
        db.query(Match).filter(Match.check_id == check.id).delete()
        db.query(CheckSource).filter(CheckSource.check_id == check.id).delete()

        match_rows: list[dict[str, Any]] = []
        for idx, m in enumerate(all_raw_matches):
            if m.sub_token_start >= len(sub_tokens_meta) or m.sub_token_end <= 0:
                continue
            src_payload = src_payloads.get(m.source_document_id)
            if not src_payload:
                continue
            src_tokens_meta = src_payload["tokens"]
            if m.src_token_start >= len(src_tokens_meta) or m.src_token_end <= 0:
                continue

            sub_cs = sub_tokens_meta[m.sub_token_start][1]
            sub_ce = sub_tokens_meta[min(m.sub_token_end, len(sub_tokens_meta)) - 1][2]
            src_cs = src_tokens_meta[m.src_token_start][1]
            src_ce = src_tokens_meta[min(m.src_token_end, len(src_tokens_meta)) - 1][2]
            src_page = _page_for_char(src_cs, src_payload.get("pages", []))
            counted, excl_reason = scoring.counted_match_flags[idx]

            match_rows.append(
                {
                    "check_id": check.id,
                    "source_document_id": m.source_document_id,
                    "layer": m.layer,
                    "sub_token_start": m.sub_token_start,
                    "sub_token_end": m.sub_token_end,
                    "sub_char_start": sub_cs,
                    "sub_char_end": sub_ce,
                    "src_token_start": m.src_token_start,
                    "src_token_end": m.src_token_end,
                    "src_char_start": src_cs,
                    "src_char_end": src_ce,
                    "src_page": src_page,
                    "matched_words": m.matched_words,
                    "score": m.score,
                    "sub_excerpt": sub_text[sub_cs:sub_ce][:600],
                    "src_excerpt": src_payload["text"][src_cs:src_ce][:600],
                    "excluded_reason": excl_reason,
                    "counted": counted,
                }
            )

        if match_rows:
            db.bulk_insert_mappings(Match, match_rows)

        if scoring.source_summaries:
            db.bulk_insert_mappings(
                CheckSource,
                [
                    {
                        "check_id": check.id,
                        "source_document_id": s.source_document_id,
                        "rank": s.rank,
                        "matched_words_exclusive": s.matched_words_exclusive,
                        "matched_words_total": s.matched_words_total,
                        "contribution_pct": s.contribution_pct,
                        "layers": s.layers,
                    }
                    for s in scoring.source_summaries
                ],
            )

        # Store metadata-only records summary in coverage for transparency
        coverage = dict(scoring.coverage)
        coverage["metadata_only_items"] = [
            {
                "provider": r.provider,
                "external_id": r.external_id,
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "doi": r.doi,
                "url": r.url,
                "access_status": r.access_status,
            }
            for r in ext_meta_records[:25]
        ]

        stage_counts["report"] = {
            "sources": len(scoring.source_summaries),
            "report_number": check.report_number,
        }

        check.metrics = scoring.metrics
        check.coverage = coverage
        check.stage_counts = stage_counts
        check.stage = "Selesai"
        check.progress = 100
        check.status = "COMPLETED"
        check.finished_at = datetime.now(timezone.utc)
        check.error = None

        # Optional: index submission into local corpus after check
        if cfg.add_to_corpus_after_check and doc.role == "SUBMISSION":
            # Keep original SUBMISSION record intact, or index if requested? Better: index fingerprints on copy or skip duplicate role
            # Only index if no CORPUS doc with same hash exists
            existing_corpus = (
                db.query(Document)
                .filter(Document.file_hash == doc.file_hash, Document.role == "CORPUS")
                .first()
            )
            if existing_corpus is None:
                index_document_for_corpus(db, doc, sub_norm_tokens)
                doc.role = "CORPUS"

        db.commit()
    except Exception as exc:
        db.rollback()
        failed = db.query(Check).filter(Check.id == check_id).first()
        if failed is not None:
            failed.status = "FAILED"
            failed.stage = "Gagal"
            failed.error = f"Terjadi kesalahan saat pemeriksaan: {exc}"
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
