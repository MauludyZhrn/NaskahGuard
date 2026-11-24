"""Phase 9 Explicit Live Internet Provider & End-to-End Discovery Verification.

Runs ONLY with public non-private academic test queries ("winnowing document fingerprinting")
to verify real internet reachability of:
- OpenAlex
- Crossref
- Europe PMC
- DOAJ
- arXiv
- SearXNG (reports NOT_CONFIGURED cleanly if NG_SEARXNG_BASE_URL is unset)
- Official Web API (reports NOT_CONFIGURED cleanly if unset)
- Isolated Playwright Chromium BrowserExtractor
- Full end-to-end discovery + full-text acquisition + local SQLite indexing + similarity matching
  on a synthetic 3-sentence public test snippet!
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import dispose_engine, get_session_factory, init_db
from app.engine.pipeline import run_check_pipeline
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.main import run_migrations
from app.models import Check
from app.schemas import CheckSettingsSchema
from app.sources.arxiv import ArxivProvider
from app.sources.browser_extractor import IsolatedPlaywrightExtractor
from app.sources.crossref import CrossrefProvider
from app.sources.doaj import DOAJProvider
from app.sources.europe_pmc import EuropePMCProvider
from app.sources.openalex import OpenAlexProvider
from app.sources.web_search import OfficialWebSearchAPIProvider, SearXNGWebSearchProvider


def main() -> None:
    started_ts = datetime.now(timezone.utc).isoformat()
    public_query = "winnowing document fingerprinting"
    provider_logs = []

    providers = [
        ("openalex", OpenAlexProvider()),
        ("crossref", CrossrefProvider()),
        ("europe_pmc", EuropePMCProvider()),
        ("doaj", DOAJProvider()),
        ("arxiv", ArxivProvider()),
        ("searxng", SearXNGWebSearchProvider()),
        ("web_api", OfficialWebSearchAPIProvider()),
    ]

    for name, inst in providers:
        configured = inst.is_configured() if hasattr(inst, "is_configured") else True
        if not configured:
            provider_logs.append(
                {
                    "provider": name,
                    "configured": False,
                    "reachable": False,
                    "status": "NOT_CONFIGURED",
                    "query_count": 0,
                    "candidate_count": 0,
                    "url_count": 0,
                    "latency_ms": 0,
                    "error": None,
                }
            )
            continue

        t0 = time.perf_counter()
        recs = inst.search(public_query)
        ms = int((time.perf_counter() - t0) * 1000)
        err = getattr(inst, "last_error", None)
        urls = [u for r in recs for u in ([r.url, r.oa_pdf_url] + list(r.candidate_urls or [])) if u]
        provider_logs.append(
            {
                "provider": name,
                "configured": True,
                "reachable": err is None,
                "status": "OK" if err is None else "ERROR",
                "query_count": 1,
                "candidate_count": len(recs),
                "url_count": len(set(urls)),
                "latency_ms": ms,
                "error": err,
            }
        )

    # BrowserExtractor isolated health check
    pw_health = IsolatedPlaywrightExtractor().health_check_sync()

    # Live End-to-End check on temporary SQLite DB if at least 1 academic provider is reachable
    any_reachable = any(p["reachable"] and p["candidate_count"] > 0 for p in provider_logs)
    e2e_summary = {"executed": False}
    if any_reachable:
        with tempfile.TemporaryDirectory(prefix="ng_live_e2e_") as tmpdir:
            tmp = Path(tmpdir)
            db_url = f"sqlite:///{(tmp / 'live.db').as_posix()}"
            run_migrations(db_url)
            init_db(db_url)
            db = get_session_factory()()
            try:
                sample_public_txt = (
                    "Document Fingerprinting and Winnowing Open Access Verification\n\n"
                    "CHAPTER 1 INTRODUCTION\n\n"
                    "Winnowing is a local document fingerprinting algorithm for selecting hashes of k-grams within a sliding window "
                    "to guarantee detection of exact substring matches above a configurable threshold in academic text analysis.\n"
                ).encode("utf-8")
                up = validate_local_bytes("public_probe.txt", sample_public_txt, 5 * 1024 * 1024)
                doc = ingest_validated_upload(db, up, role="SUBMISSION", title="Winnowing Local Algorithms for Document Fingerprinting")
                cfg = CheckSettingsSchema(
                    use_external_sources=True,
                    enable_academic_search=True,
                    enable_web_search=False,
                    enable_fulltext_download=True,
                    enable_browser_crawler=True,
                    search_intensity="QUICK",
                    max_search_queries=3,
                    max_crawled_urls=4,
                    external_providers=["openalex", "europe_pmc", "doaj", "arxiv", "crossref"],
                )
                chk = Check(
                    report_number="NG-LIVE-TEST",
                    document_id=doc.id,
                    status="QUEUED",
                    stage="Antrean",
                    progress=0,
                    settings=cfg.model_dump(),
                )
                db.add(chk)
                db.commit()
                db.refresh(chk)

                t_e2e = time.perf_counter()
                run_check_pipeline(db, chk.id)
                e2e_ms = int((time.perf_counter() - t_e2e) * 1000)
                db.refresh(chk)
                scov = (chk.coverage or {}).get("search_coverage", {})
                e2e_summary = {
                    "executed": True,
                    "check_status": chk.status,
                    "queries_executed": scov.get("total_search_queries", 0),
                    "provider_responses": scov.get("total_provider_responses", 0),
                    "unique_urls_found": scov.get("total_unique_urls_found", 0),
                    "fulltext_fetched": scov.get("total_fulltext_fetched", 0),
                    "fulltext_indexed": scov.get("total_fulltext_indexed", 0),
                    "metadata_only": scov.get("total_metadata_only", 0),
                    "similarity_index_pct": (chk.metrics or {}).get("similarity_index", 0.0),
                    "stage_timings_ms": (chk.metrics or {}).get("stage_timings_ms", {}),
                    "total_elapsed_ms": e2e_ms,
                }
            finally:
                db.close()
                dispose_engine()

    result = {
        "mode": "live_internet_provider_verification",
        "timestamp": started_ts,
        "public_test_query": public_query,
        "playwright_isolated_browser": pw_health,
        "providers": provider_logs,
        "live_end_to_end_examination": e2e_summary,
    }
    out = ROOT / "benchmark" / "results" / "phase9_live_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
