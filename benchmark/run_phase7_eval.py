"""Phase 7 realistic multi-stage evaluation benchmark (Retrieval, Crawling, Extraction, Matching)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import fitz
import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT))

from app import config, db as db_mod  # noqa: E402
from app.engine.pipeline import run_check_pipeline  # noqa: E402
from app.ingestion.service import ingest_validated_upload  # noqa: E402
from app.ingestion.validators import validate_local_bytes  # noqa: E402
from app.main import run_migrations  # noqa: E402
from app.models import Check, Match, Segment, SourceAcquisition  # noqa: E402
from app.schemas import CheckSettingsSchema  # noqa: E402
from app.sources.openalex import OpenAlexProvider  # noqa: E402
from app.sources.registry import discover_external_sources  # noqa: E402


def _make_oa_pdf(text: str) -> bytes:
    doc = fitz.open()
    p = doc.new_page()
    p.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b


def main() -> int:
    # Realistic open-access style academic benchmark pairs covering all 12 Phase 7 evaluation types
    oa_paper_1_txt = (
        "Open-Access Research Paper: Winnowing Fingerprints for Academic Similarity Detection.\n\n"
        "Abstract\n\n"
        "Document fingerprinting selects representative k-gram hashes using a sliding window minimum rule. "
        "This enables scalable candidate retrieval across institutional repositories and open-access journals.\n\n"
        "Methodology\n\n"
        "Seed-and-extend alignment refines candidate overlaps into exact character intervals without double counting "
        "tokens shared across multiple mirrored repository locations."
    )
    oa_paper_2_html = (
        "<html><head><title>Deteksi Kemiripan Teks Akademik Indonesia</title>"
        "<link rel='canonical' href='https://jurnal.terbuka.id/artikel/22'/></head>"
        "<body><nav>Navigasi Jurnal</nav><article>"
        "<h1>Deteksi Kemiripan Teks Akademik Indonesia</h1>"
        "<p>Pencocokan berbasis n-gram kata dan indeks TF-IDF karakter membantu mengidentifikasi kemiripan leksikal "
        "serta penyalinan antar artikel ilmiah berbahasa Indonesia.</p>"
        "</article><footer>Footer</footer></body></html>"
    )

    with tempfile.TemporaryDirectory(prefix="ng_p7_eval_") as tmp_dir:
        tmp = Path(tmp_dir)
        db_url = f"sqlite:///{(tmp / 'p7_eval.db').as_posix()}"
        os.environ["NG_DATABASE_URL"] = db_url
        os.environ["NG_STORAGE_DIR"] = str(tmp / "storage")
        config.get_settings.cache_clear()
        run_migrations(db_url)
        db = db_mod.get_session_factory()()

        try:
            pdf1 = _make_oa_pdf(oa_paper_1_txt)
            html2 = oa_paper_2_html.encode("utf-8")

            def mock_oa(req: httpx.Request) -> httpx.Response:
                u = str(req.url)
                if "robots.txt" in u:
                    return httpx.Response(200, text="User-agent: *\nAllow: /")
                if "api.openalex.org/works" in u:
                    return httpx.Response(
                        200,
                        json={
                            "results": [
                                {
                                    "id": "https://openalex.org/W101",
                                    "display_name": "Winnowing Fingerprints for Academic Similarity Detection",
                                    "publication_year": 2025,
                                    "doi": "https://doi.org/10.1000/eval.101",
                                    "has_fulltext": True,
                                    "open_access": {"is_oa": True},
                                    "best_oa_location": {
                                        "is_oa": True,
                                        "pdf_url": "https://oa.eval.org/paper101.pdf",
                                        "landing_page_url": "https://oa.eval.org/paper101",
                                    },
                                    "locations": [
                                        {"is_oa": True, "pdf_url": "https://mirror.eval.org/paper101.pdf"}
                                    ],
                                },
                                {
                                    "id": "https://openalex.org/W102",
                                    "display_name": "Deteksi Kemiripan Teks Akademik Indonesia",
                                    "publication_year": 2025,
                                    "doi": "https://doi.org/10.1000/eval.102",
                                    "has_fulltext": True,
                                    "open_access": {"is_oa": True},
                                    "best_oa_location": {
                                        "is_oa": True,
                                        "landing_page_url": "https://jurnal.terbuka.id/artikel/22",
                                    },
                                    "locations": [],
                                },
                                {
                                    "id": "https://openalex.org/W103",
                                    "display_name": "Closed Paywalled Paper",
                                    "publication_year": 2024,
                                    "doi": "https://doi.org/10.1000/eval.103",
                                    "has_fulltext": False,
                                    "open_access": {"is_oa": False},
                                    "best_oa_location": {},
                                    "locations": [],
                                },
                                {
                                    "id": "https://openalex.org/W104",
                                    "display_name": "Inaccessible Server Paper",
                                    "publication_year": 2024,
                                    "doi": "https://doi.org/10.1000/eval.104",
                                    "has_fulltext": True,
                                    "open_access": {"is_oa": True},
                                    "best_oa_location": {
                                        "is_oa": True,
                                        "pdf_url": "https://denied.eval.org/403.pdf",
                                    },
                                    "locations": [],
                                },
                            ]
                        },
                    )
                if "paper101.pdf" in u:
                    return httpx.Response(200, content=pdf1, headers={"Content-Type": "application/pdf"})
                if "jurnal.terbuka.id/artikel/22" in u:
                    return httpx.Response(200, content=html2, headers={"Content-Type": "text/html"})
                if "403.pdf" in u:
                    return httpx.Response(403, text="Forbidden")
                return httpx.Response(404)

            sub_text = (
                "BAB I PENDAHULUAN\n\n"
                "Document fingerprinting selects representative k-gram hashes using a sliding window minimum rule. "
                "This enables scalable candidate retrieval across institutional repositories and open-access journals.\n\n"
                "Seed-and-extend alignment refines candidate overlaps into accurate character intervals without double counting "
                "tokens shared across several mirrored repository locations.\n\n"
                "Pencocokan berbasis n-gram kata dan indeks TF-IDF karakter membantu mengidentifikasi kemiripan leksikal "
                "serta penyalinan antar artikel ilmiah berbahasa Indonesia.\n\n"
                "Original conclusion written independently by the author for this evaluation benchmark."
            )
            v_sub = validate_local_bytes("eval_sub.txt", sub_text.encode("utf-8"), 5_000_000)
            sub_doc = ingest_validated_upload(db, v_sub, role="SUBMISSION", title="Evaluation Manuscript")
            sub_segs = db.query(Segment).filter(Segment.document_id == sub_doc.id).all()

            chk = Check(
                report_number="NG-P7-EVAL-01",
                document_id=sub_doc.id,
                status="PROCESSING",
                stage="Penemuan Sumber",
                progress=20,
                settings={},
            )
            db.add(chk)
            db.commit()

            t_search0 = time.perf_counter()
            oa_prov = OpenAlexProvider(client=httpx.Client(transport=httpx.MockTransport(mock_oa)))
            cfg = CheckSettingsSchema(
                use_external_sources=True,
                enable_academic_search=True,
                enable_web_search=False,
                enable_fulltext_download=True,
                max_search_queries=1,
                external_providers=["openalex"],
            )
            disc = discover_external_sources(
                db,
                check_id=chk.id,
                submission_doc=sub_doc,
                submission_segments=sub_segs,
                check_settings=cfg,
                providers_override={"openalex": oa_prov},
                resolve_dns=False,
            )
            search_latency_ms = round((time.perf_counter() - t_search0) * 1000.0, 2)

            t_match0 = time.perf_counter()
            chk.settings = CheckSettingsSchema(use_external_sources=False).model_dump()
            db.commit()
            run_check_pipeline(db, chk.id)
            match_time_ms = round((time.perf_counter() - t_match0) * 1000.0, 2)

            db.refresh(chk)
            acqs = db.query(SourceAcquisition).filter(SourceAcquisition.check_id == chk.id).all()
            matches = db.query(Match).filter(Match.check_id == chk.id).all()

            relevant_retrieved = len(disc.external_fulltext_doc_ids)
            total_accessible_expected = 2  # W101 (PDF) + W102 (HTML)
            source_retrieval_precision = round(relevant_retrieved / max(1, len(acqs)), 4)
            fulltext_acq_success = round(relevant_retrieved / total_accessible_expected, 4)

            summary = {
                "search_retrieval": {
                    "queries_executed": disc.queries_executed,
                    "candidate_records": len(acqs),
                    "source_retrieval_precision": source_retrieval_precision,
                    "search_and_acquisition_latency_ms": search_latency_ms,
                },
                "crawling_and_extraction": {
                    "fulltext_indexed": relevant_retrieved,
                    "fulltext_acquisition_success_rate": fulltext_acq_success,
                    "metadata_only_count": len(disc.metadata_only_records),
                    "access_denied_count": disc.access_denied_count,
                },
                "similarity_matching": {
                    "similarity_index": chk.metrics["similarity_index"],
                    "exact_match_pct": chk.metrics["exact_match_pct"],
                    "near_exact_match_pct": chk.metrics["near_exact_match_pct"],
                    "sources_matched": chk.metrics["sources_found"],
                    "total_matches": len(matches),
                    "matching_processing_time_ms": match_time_ms,
                },
            }

            out_dir = ROOT / "benchmark" / "results"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "phase7_eval.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print("=== Phase 7 Realistic Evaluation ===")
            print(json.dumps(summary, indent=2))
            return 0
        finally:
            db.close()
            db_mod.dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
