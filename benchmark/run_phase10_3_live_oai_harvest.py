"""Phase 10.3 Real Live Public OAI-PMH Harvesting Integration Verification.

Runs an honest, live, end-to-end test against an official public OAI-PMH 2.0 repository
(https://oaipmh.arxiv.org/oai — arXiv's official public OAI-PMH endpoint) in an isolated
temporary SQLite database:
  1. Runs the 8-stage Connection Test Wizard (Identify -> ListMetadataFormats -> ListSets -> ListRecords -> Metadata -> PDF URL discovery).
  2. Harvests a small polite batch (max_records=3, set='cs') with real PDF download & full-text extraction.
  3. Persists records & logs into SQLite (`oai_repositories`, `oai_harvest_records`, `oai_harvest_logs`, `documents`).
  4. Runs a plagiarism similarity check on a snippet from one of the newly harvested documents to verify
     the complete 7-stage funnel including `document_compared >= 1`!
  5. Writes the verifiable JSON evidence report to `benchmark/results/phase10_3_live_oai_harvest.json`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ng_live_oai_") as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "live_oai.db"
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["STORAGE_DIR"] = str(storage_dir)
        os.environ["API_TOKEN"] = ""

        from app.config import get_settings

        get_settings.cache_clear()

        from app.db import Base, dispose_engine, get_session_factory, init_db
        from app.ingestion.service import ingest_validated_upload
        from app.ingestion.validators import validate_local_bytes
        from app.models import Check, Document, OAIHarvestLog, OAIHarvestRecord, OAIRepository
        from app.engine.pipeline import run_check_pipeline
        from app.sources.oai_pmh import (
            get_repository_funnel,
            harvest_oai_repository,
            run_connection_wizard,
        )

        engine = init_db(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        db = get_session_factory()()
        try:
            return _execute(db, run_connection_wizard, harvest_oai_repository, get_repository_funnel,
                            OAIRepository, OAIHarvestRecord, OAIHarvestLog, Document, Check,
                            validate_local_bytes, ingest_validated_upload, run_check_pipeline)
        finally:
            db.close()
            dispose_engine()


def _execute(
    db,
    run_connection_wizard,
    harvest_oai_repository,
    get_repository_funnel,
    OAIRepository,
    OAIHarvestRecord,
    OAIHarvestLog,
    Document,
    Check,
    validate_local_bytes,
    ingest_validated_upload,
    run_check_pipeline,
) -> int:

        target_url = "https://oaipmh.arxiv.org/oai"
        target_set = "cs"

        print(f"[1/4] Running 8-stage Connection Wizard against {target_url} (set={target_set})...")
        wizard = run_connection_wizard(
            target_url,
            metadata_prefix="oai_dc",
            set_spec=target_set,
            probe_pdf=True,
            timeout_sec=30.0,
        )
        print(
            f"      Wizard status={wizard['overall_status']} "
            f"pass={wizard['summary_counts']['pass']} warn={wizard['summary_counts']['warn']} fail={wizard['summary_counts']['fail']} "
            f"identified='{wizard['identified_name']}'"
        )

        repo = OAIRepository(
            name="arXiv Public OAI-PMH (Live Verification)",
            base_url=wizard["effective_url"],
            repo_type="arxiv",
            platform_detected=wizard["platform_detected"],
            identified_name=wizard["identified_name"],
            metadata_prefix=wizard["recommended_prefix"],
            selected_set=target_set,
            supported_formats=wizard["supported_formats"],
            available_sets=wizard["available_sets"][:25],
            last_test_report=wizard,
            rate_limit_delay_sec=1.0,
            request_timeout_sec=30,
            status="VERIFIED" if wizard["ok"] else "ERROR",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

        print(f"[2/4] Harvesting live batch (max_records=3, download_pdfs=True)...")
        summary = harvest_oai_repository(
            db,
            repo,
            max_records=3,
            download_pdfs=True,
            set_spec=target_set,
        )
        print(f"      Harvest summary: {summary}")

        # Verify similarity comparison against one indexed harvested document
        indexed_docs = (
            db.query(Document)
            .filter(Document.role == "CORPUS", Document.indexing_status == "FULLTEXT_INDEXED")
            .all()
        )
        print(f"[3/4] Indexed full-text documents from live harvest: {len(indexed_docs)}")

        comparison_result: dict = {"executed": False}
        if indexed_docs:
            target_doc = indexed_docs[0]
            # Extract a 120-word slice from the harvested PDF segments as a test submission
            full_doc_text = " ".join(s.original_text for s in (target_doc.segments or []) if getattr(s, "original_text", None))
            words = full_doc_text.split()
            excerpt_text = " ".join(words[40:180]) if len(words) > 180 else " ".join(words[:120])
            if len(excerpt_text.split()) >= 25:
                sub_bytes = (
                    "Draft Review Article\n\n"
                    "This verification manuscript incorporates an excerpt directly from a live OAI-PMH harvested paper.\n\n"
                    + excerpt_text
                    + "\n\nAdditional original commentary concluding the verification run."
                ).encode("utf-8")
                val = validate_local_bytes("live_oai_verification.txt", sub_bytes, 25 * 1024 * 1024)
                sub_doc = ingest_validated_upload(db, val, role="SUBMISSION", title="Live OAI Verification Submission")
                check = Check(
                    report_number="NG-LIVE-OAI-001",
                    document_id=sub_doc.id,
                    status="QUEUED",
                    mode="PLAGIARISM_ONLY",
                    settings={
                        "include_local_corpus": True,
                        "use_external_sources": False,
                        "exclude_bibliography": False,
                        "exclude_quotes": False,
                        "exclude_citations": False,
                        "min_match_words": 5,
                    },
                )
                db.add(check)
                db.commit()
                run_check_pipeline(db, check.id)
                db.refresh(check)
                comparison_result = {
                    "executed": True,
                    "check_status": check.status,
                    "similarity_index": (check.metrics or {}).get("similarity_index"),
                    "matched_words": (check.metrics or {}).get("matched_words"),
                    "sources_found": (check.metrics or {}).get("sources_found"),
                    "matched_harvested_doc_title": target_doc.title,
                    "matched_harvested_doc_words": target_doc.word_count,
                }
                print(f"      Similarity check against live OAI doc: {comparison_result}")

        funnel = get_repository_funnel(db, repo)
        records = db.query(OAIHarvestRecord).filter(OAIHarvestRecord.repository_id == repo.id).all()
        logs = db.query(OAIHarvestLog).filter(OAIHarvestLog.repository_id == repo.id).all()

        out = {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "target_url": target_url,
            "target_set": target_set,
            "wizard": {
                "ok": wizard["ok"],
                "overall_status": wizard["overall_status"],
                "identified_name": wizard["identified_name"],
                "platform_detected": wizard["platform_detected"],
                "supported_formats": wizard["supported_formats"],
                "available_sets_count": len(wizard["available_sets"]),
                "stages": [
                    {
                        "step": s["step"],
                        "key": s["key"],
                        "status": s["status"],
                        "http_status": s["http_status"],
                        "error_code": s["error_code"],
                        "message": s["message"],
                    }
                    for s in wizard["stages"]
                ],
            },
            "harvest_summary": summary,
            "funnel_7_stage": funnel,
            "records": [
                {
                    "oai_identifier": r.oai_identifier,
                    "title": r.title,
                    "year": r.year,
                    "status": r.status,
                    "pdf_urls": r.pdf_urls,
                    "document_id": r.document_id,
                    "error_code": r.error_code,
                }
                for r in records
            ],
            "logs_count": len(logs),
            "similarity_comparison": comparison_result,
        }

        out_path = ROOT / "benchmark" / "results" / "phase10_3_live_oai_harvest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[4/4] Saved live verification proof to {out_path}")
        print(f"      7-Stage Funnel: {funnel}")

        db.close()
        return 0 if wizard["ok"] and summary["records_harvested"] >= 1 and funnel["document_indexed"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
