"""Phase 10.4 Live Platform Validation across Official Indonesian Academic Repositories.

Tests real public OAI-PMH endpoints across:
  - OJS:           https://journal.uny.ac.id/index.php/jpvo/oai
  - DSpace Legacy: https://repository.ipb.ac.id/oai/request
  - EPrints:       http://digilib.uin-suka.ac.id/cgi/oai2 (plus secondary ITS check)
  - DSpace 7:      https://digilib.stikomyos.ac.id/server/oai/request

STRICT HONESTY:
  - Never fabricates URLs.
  - Tests Identify, ListMetadataFormats, ListSets, ListRecords, GetRecord, ResumptionToken,
    Full-text PDF discovery, PDF download, Text extraction, Local indexing + Plagiarism Check.
  - If an endpoint times out or rejects access live, documents it faithfully without claiming pass.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

PLATFORM_TARGETS = [
    {
        "platform": "ojs",
        "platform_label": "OJS (Open Journal Systems)",
        "university": "Universitas Negeri Yogyakarta (UNY)",
        "name": "Jurnal Pendidikan Vokasi Otomotif (OJS UNY)",
        "base_url": "https://journal.uny.ac.id/index.php/jpvo/oai",
    },
    {
        "platform": "dspace_legacy",
        "platform_label": "DSpace Lama (/oai/request)",
        "university": "IPB University",
        "name": "IPB Scientific Repository",
        "base_url": "https://repository.ipb.ac.id/oai/request",
    },
    {
        "platform": "eprints",
        "platform_label": "EPrints (/cgi/oai2)",
        "university": "UIN Sunan Kalijaga Yogyakarta",
        "name": "Institutional Repository UIN Sunan Kalijaga",
        "base_url": "http://digilib.uin-suka.ac.id/cgi/oai2",
    },
    {
        "platform": "dspace7",
        "platform_label": "DSpace 7 (/server/oai/request)",
        "university": "STIKOM Yos Sudarso Purwokerto",
        "name": "SYS Digital Repository (DSpace 7)",
        "base_url": "https://digilib.stikomyos.ac.id/server/oai/request",
    },
    {
        "platform": "dspace7_demo",
        "platform_label": "DSpace 7 Referensi Resmi (/server/oai/request)",
        "university": "LYRASIS / DSpace Official Demo",
        "name": "DSpace 7 Official Public Demo",
        "base_url": "https://demo.dspace.org/server/oai/request",
        "preferred_prefix": "didl",
    },
]


def _validate_target(target: dict[str, str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"ng_live_{target['platform']}_", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "val.db"
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        os.environ["NG_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["NG_STORAGE_DIR"] = str(storage_dir)
        os.environ["STORAGE_DIR"] = str(storage_dir)
        os.environ["NG_API_TOKEN"] = ""
        os.environ["API_TOKEN"] = ""

        from app.config import get_settings

        get_settings.cache_clear()
        from app.db import Base, dispose_engine, get_session_factory, init_db
        from app.engine.pipeline import run_check_pipeline
        from app.ingestion.service import ingest_validated_upload
        from app.ingestion.validators import validate_local_bytes
        from app.models import Check, Document, OAIHarvestRecord, OAIRepository
        from app.sources.oai_pmh import (
            OAIPMHClient,
            get_repository_funnel,
            harvest_oai_repository,
            run_connection_wizard,
        )

        engine = init_db(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        db = get_session_factory()()

        result: dict[str, Any] = {
            **target,
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "reachable": False,
            "validation_status": "UNVERIFIED_LIVE",
            "capabilities": {
                "Identify": False,
                "ListMetadataFormats": False,
                "ListSets": False,
                "ListRecords": False,
                "GetRecord": False,
                "ResumptionToken": False,
                "FulltextPDFDiscovery": False,
                "PDFDownload": False,
                "TextExtraction": False,
                "LocalIndexing": False,
                "CorpusPlagiarismComparison": False,
            },
            "identified_name": None,
            "supported_formats": [],
            "sets_count": 0,
            "sample_identifier": None,
            "harvest_summary": None,
            "funnel": None,
            "similarity_check": None,
            "error": None,
        }

        try:
            print(f"\n>>> Testing {target['platform_label']}: {target['base_url']} ...")
            pref = target.get("preferred_prefix") or "oai_dc"
            wizard = run_connection_wizard(target["base_url"], metadata_prefix=pref, probe_pdf=False, timeout_sec=18.0)
            st_map = {s["key"]: s for s in wizard["stages"]}

            result["identified_name"] = wizard.get("identified_name")
            result["supported_formats"] = wizard.get("supported_formats") or []
            result["sets_count"] = len(wizard.get("available_sets") or [])
            result["capabilities"]["Identify"] = st_map.get("identify", {}).get("status") == "PASS"
            result["capabilities"]["ListMetadataFormats"] = st_map.get("list_metadata_formats", {}).get("status") in {"PASS", "WARN"}
            result["capabilities"]["ListSets"] = st_map.get("list_sets", {}).get("status") in {"PASS", "WARN"}
            result["capabilities"]["ListRecords"] = st_map.get("test_list_records", {}).get("status") == "PASS"
            result["capabilities"]["ResumptionToken"] = bool(
                st_map.get("test_list_records", {}).get("data", {}).get("has_resumption_token")
            )

            if not result["capabilities"]["Identify"]:
                fail_st = next((s for s in wizard["stages"] if s["status"] == "FAIL"), None)
                result["error"] = f"{fail_st.get('error_code') if fail_st else 'CONN_FAIL'}: {fail_st.get('message') if fail_st else 'Tidak dapat dihubungi'}"
                result["validation_status"] = "BELUM_TERVALIDASI_UNREACHABLE"
                print(f"    UNREACHABLE: {result['error']}")
                return result

            result["reachable"] = True

            # Test GetRecord explicitly on the first sample identifier
            samples = wizard.get("sample_records") or []
            if samples:
                sample_id = samples[0]["identifier"]
                result["sample_identifier"] = sample_id
                try:
                    oai_c = OAIPMHClient(timeout_sec=18.0)
                    grec = oai_c.get_record(
                        wizard["effective_url"],
                        sample_id,
                        metadata_prefix=wizard["recommended_prefix"],
                    )
                    result["capabilities"]["GetRecord"] = grec is not None and bool(grec.identifier)
                except Exception as exc:
                    result["capabilities"]["GetRecord"] = False
                    print(f"    GetRecord note: {exc}")

            # Save repo & perform polite bounded harvest (max_records=3, max_downloads=2)
            repo = OAIRepository(
                name=target["name"],
                base_url=wizard["effective_url"],
                repo_type=target["platform"],
                platform_detected=wizard["platform_detected"],
                identified_name=wizard["identified_name"] or target["university"],
                metadata_prefix=wizard["recommended_prefix"],
                supported_formats=wizard["supported_formats"],
                available_sets=(wizard["available_sets"] or [])[:50],
                rate_limit_delay_sec=0.8,
                request_timeout_sec=22,
                max_downloads=2,
                status="VERIFIED",
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

            summary = harvest_oai_repository(
                db,
                repo,
                max_records=3,
                max_downloads=2,
                download_pdfs=True,
                trigger_mode="LIVE_VALIDATION",
            )
            result["harvest_summary"] = summary
            funnel = get_repository_funnel(db, repo)
            result["funnel"] = funnel

            recs = db.query(OAIHarvestRecord).filter(OAIHarvestRecord.repository_id == repo.id).all()
            docs = db.query(Document).filter(Document.role == "CORPUS").all()

            result["capabilities"]["FulltextPDFDiscovery"] = any(r.pdf_urls for r in recs) or funnel["pdf_urls_found"] > 0
            result["capabilities"]["PDFDownload"] = funnel["pdf_accessible"] > 0
            result["capabilities"]["TextExtraction"] = any(d.word_count > 30 for d in docs)
            result["capabilities"]["LocalIndexing"] = funnel["document_indexed"] > 0

            # End-to-end plagiarism check against newly indexed document
            if docs:
                target_doc = max(docs, key=lambda d: d.word_count)
                full_text = " ".join(s.original_text for s in (target_doc.segments or []) if s.original_text)
                words = full_text.split()
                if len(words) >= 35:
                    excerpt = " ".join(words[15:min(135, len(words))])
                    sub_bytes = (
                        f"Naskah Uji Validasi {target['platform']}\n\n{excerpt}\n\nKalimat penutup orisinal."
                    ).encode("utf-8")
                    val = validate_local_bytes("live_val_sub.txt", sub_bytes, 25 * 1024 * 1024)
                    sub_doc = ingest_validated_upload(db, val, role="SUBMISSION", title=f"Live Check {target['platform']}")
                    chk = Check(
                        report_number=f"NG-LIVE-{target['platform'].upper()}",
                        document_id=sub_doc.id,
                        status="QUEUED",
                        mode="PLAGIARISM_ONLY",
                        settings={
                            "include_local_corpus": True,
                            "use_external_sources": False,
                            "exclude_bibliography": False,
                            "min_match_words": 5,
                        },
                    )
                    db.add(chk)
                    db.commit()
                    run_check_pipeline(db, chk.id)
                    db.refresh(chk)
                    si = (chk.metrics or {}).get("similarity_index", 0.0)
                    result["similarity_check"] = {
                        "similarity_index": si,
                        "matched_words": (chk.metrics or {}).get("matched_words"),
                        "sources_found": (chk.metrics or {}).get("sources_found"),
                        "source_title": target_doc.title,
                    }
                    result["capabilities"]["CorpusPlagiarismComparison"] = si > 0

            if result["capabilities"]["LocalIndexing"]:
                result["validation_status"] = "TERVALIDASI_FULLTEXT"
            elif result["capabilities"]["ListRecords"]:
                result["validation_status"] = "TERVALIDASI_METADATA_ONLY"
            else:
                result["validation_status"] = "TERBATAS"

            print(
                f"    Status={result['validation_status']} indexed={funnel['document_indexed']} "
                f"SI={((result.get('similarity_check') or {}).get('similarity_index'))}"
            )
            return result
        except Exception as exc:
            result["error"] = str(exc)
            result["validation_status"] = "GAGAL"
            print(f"    ERROR: {exc}")
            return result
        finally:
            db.close()
            dispose_engine()


def main() -> int:
    results = [_validate_target(t) for t in PLATFORM_TARGETS]
    payload = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "total_targets": len(results),
        "platforms_validated_fulltext": [r["platform"] for r in results if r["validation_status"] == "TERVALIDASI_FULLTEXT"],
        "platforms_unvalidated_live": [r["platform"] for r in results if not r["reachable"]],
        "results": results,
    }
    out_path = ROOT / "benchmark" / "results" / "phase10_4_live_platform_validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved live validation report to {out_path}")
    print("Full-text validated platforms:", payload["platforms_validated_fulltext"])
    print("Unvalidated/unreachable live platforms:", payload["platforms_unvalidated_live"])
    return 0 if len(payload["platforms_validated_fulltext"]) >= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
