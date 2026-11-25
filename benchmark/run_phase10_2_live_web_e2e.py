"""Phase 10.2 Real Live Public-Source End-to-End Verification.

Executes the complete real internet pipeline WITHOUT dummy sources:
Query -> Live Search Result (Europe PMC / DOAJ / arXiv) -> Browser/HTTP Extraction
-> Full-text -> Local Index -> Similarity Matching -> Report.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

OUT_JSON = ROOT / "benchmark" / "results" / "phase10_2_live_web_e2e.json"


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tmp = Path(td)
        db_url = "sqlite:///" + (tmp / "live_web_e2e.db").as_posix()
        os.environ["NG_DATABASE_URL"] = db_url
        os.environ["NG_STORAGE_DIR"] = str(tmp / "storage")
        os.environ["NG_API_TOKEN"] = ""
        os.environ["NG_HOST"] = "127.0.0.1"
        os.environ["NG_RATE_LIMIT_PER_MIN"] = "0"

        from app.config import get_settings
        from app.main import create_app, run_migrations
        from fastapi.testclient import TestClient

        get_settings.cache_clear()
        run_migrations(db_url)

        # Fetch one real public arXiv open-access article (title + abstract) via live search
        # so our submission contains an actual public passage that exists on the live internet!
        import re
        import xml.etree.ElementTree as ET
        import httpx

        with httpx.Client(timeout=25.0) as hc:
            r_arx = hc.get(
                "https://export.arxiv.org/api/query",
                params={"search_query": "all:plagiarism+detection+fingerprinting", "start": 0, "max_results": 3},
            )
            r_arx.raise_for_status()
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(r_arx.text)
            entry = root.find("atom:entry", ns)
            assert entry is not None, "No arXiv entry returned"
            target_title = re.sub(r"\s+", " ", (entry.findtext("atom:title", "", ns) or "")).strip()
            target_id = (entry.findtext("atom:id", "", ns) or "").strip()
            clean_abst = re.sub(r"\s+", " ", (entry.findtext("atom:summary", "", ns) or "")).strip()
            excerpt = " ".join(clean_abst.split()[:55])
            target_pmcid = target_id

        # Build submission containing that real open-access passage + original commentary (ZERO local corpus seeded!)
        submission_text = (
            f"{target_title}\n\n"
            f"Pendahuluan dan Tinjauan Pustaka\n\n"
            f"{excerpt}\n\n"
            "Dalam pemeriksaan live end-to-end ini, korpus lokal dikosongkan sepenuhnya sehingga seluruh sumber "
            "pembanding dan kecocokan teks wajib ditemukan, diunduh teks penuhnya, diindeks ke SQLite, dan "
            "dicocokkan secara langsung dari internet publik."
        )

        app = create_app()
        t0 = time.perf_counter()
        with TestClient(app) as client:
            r_doc = client.post(
                "/api/documents",
                files={"file": ("live_public_test.txt", submission_text.encode("utf-8"), "text/plain")},
                data={"title": target_title},
            )
            assert r_doc.status_code == 201, r_doc.text
            doc_id = r_doc.json()["id"]

            r_chk = client.post(
                "/api/checks",
                json={
                    "document_id": doc_id,
                    "settings": {
                        "check_mode": "PLAGIARISM_ONLY",
                        "include_local_corpus": True,
                        "use_external_sources": True,
                        "enable_academic_search": True,
                        "enable_web_search": False,
                        "enable_fulltext_download": True,
                        "enable_browser_crawler": True,
                        "external_providers": ["arxiv", "doaj"],
                        "search_intensity": "QUICK",
                        "max_search_queries": 3,
                        "max_crawled_urls": 5,
                        "min_match_words": 6,
                    },
                },
            )
            assert r_chk.status_code == 202, r_chk.text
            cid = r_chk.json()["check_id"]

            status_data = None
            for _ in range(180):
                status_data = client.get(f"/api/checks/{cid}").json()
                if status_data["status"] in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(0.5)

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            assert status_data is not None and status_data["status"] == "COMPLETED", status_data
            rep = client.get(f"/api/checks/{cid}/report").json()

            out = {
                "mode": "real_live_public_source_e2e",
                "seed_local_corpus_docs": 0,
                "target_public_article": {
                    "title": target_title,
                    "pmcid": target_pmcid,
                },
                "check_status": rep["status"],
                "elapsed_ms": elapsed_ms,
                "similarity_index_pct": rep["metrics"]["similarity_index"],
                "matched_words": rep["metrics"]["matched_words"],
                "eligible_words": rep["metrics"]["eligible_words"],
                "search_coverage": rep["coverage"].get("search_coverage", {}),
                "verified_matching_sources": [
                    {
                        "rank": s["rank"],
                        "title": s["title"],
                        "provider": s["provider"],
                        "url": s["url"],
                        "doi": s["doi"],
                        "contribution_pct": s["contribution_pct"],
                        "matched_words_exclusive": s["matched_words_exclusive"],
                    }
                    for s in rep.get("sources", [])
                ],
                "acquisitions_count": len(rep.get("acquisitions", [])),
                "acquisitions_sample": [
                    {
                        "provider": a["provider"],
                        "status": a["status"],
                        "title": a["title"][:120],
                        "source_url": a["source_url"],
                        "used_playwright": a["used_playwright"],
                    }
                    for a in rep.get("acquisitions", [])[:8]
                ],
            }

        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
