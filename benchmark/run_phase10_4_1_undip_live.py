"""Phase 10.4.1 Real Live Integration Verification for UNDIP Institutional Repository (EPrints).

Tests the REAL live endpoints:
  - NEW (prioritized): https://eprints2.undip.ac.id/cgi/oai2
  - LEGACY (301 redirect audit): http://eprints.undip.ac.id/cgi/oai2
  - POLICY PAGE: https://eprints2.undip.ac.id/policies.html

Verifies:
  1. Identify, ListMetadataFormats, ListSets, ListRecords, GetRecord, ResumptionToken (page 2).
  2. Catalog preset workflow via FastAPI TestClient on isolated SQLite DB:
     GET /api/oai/catalog?q=UNDIP -> POST /catalog/{id}/test -> POST /catalog/{id}/add
  3. Metadata-only harvest (default policy mode: ZERO bulk robot PDF downloads, source attribution preserved).
  4. Writes real observed JSON evidence to benchmark/results/phase10_4_1_undip_live.json.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    new_url = "https://eprints2.undip.ac.id/cgi/oai2"
    legacy_url = "http://eprints.undip.ac.id/cgi/oai2"
    policy_url = "https://eprints2.undip.ac.id/policies.html"

    with tempfile.TemporaryDirectory(prefix="ng_undip_live_", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "undip_live.db"
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        os.environ["NG_DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["NG_STORAGE_DIR"] = str(storage_dir)
        os.environ["STORAGE_DIR"] = str(storage_dir)
        os.environ["NG_API_TOKEN"] = ""

        from app.config import get_settings

        get_settings.cache_clear()
        from app.db import dispose_engine
        from app.main import create_app
        from app.sources.oai_pmh import OAIPMHClient, run_connection_wizard

        report: dict = {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "new_endpoint": new_url,
            "legacy_endpoint": legacy_url,
            "policy_url": policy_url,
        }

        print(f"[1/5] Probing Legacy endpoint {legacy_url} & policies.html...")
        with httpx.Client(timeout=25.0, follow_redirects=False) as hc:
            leg_resp = hc.get(f"{legacy_url}?verb=Identify", headers={"User-Agent": "NaskahGuard-OAI/1.0"})
            pol_resp = hc.get(policy_url, headers={"User-Agent": "NaskahGuard-OAI/1.0"})
            report["legacy_probe"] = {
                "http_status": leg_resp.status_code,
                "location": leg_resp.headers.get("location"),
            }
            report["policy_probe"] = {
                "http_status": pol_resp.status_code,
                "contains_metadata_policy": "Metadata Policy" in pol_resp.text,
                "contains_robot_restriction": "must not be harvested by robots" in pol_resp.text,
            }

        print(f"[2/5] Running 8-stage Connection Wizard against NEW endpoint {new_url}...")
        wizard = run_connection_wizard(new_url, probe_pdf=False, timeout_sec=35.0)
        report["wizard"] = {
            "ok": wizard["ok"],
            "overall_status": wizard["overall_status"],
            "effective_url": wizard["effective_url"],
            "platform_detected": wizard["platform_detected"],
            "identified_name": wizard["identified_name"],
            "identify": wizard["identify"],
            "supported_formats": wizard["supported_formats"],
            "collections_count": len(wizard["available_sets"]),
            "record_count_estimate": wizard.get("record_count_estimate"),
            "stages": [
                {
                    "step": s["step"],
                    "key": s["key"],
                    "status": s["status"],
                    "http_status": s["http_status"],
                    "error_code": s["error_code"],
                    "error_category": s.get("error_category"),
                    "message": s["message"],
                }
                for s in wizard["stages"]
            ],
        }
        print(
            f"      Wizard={wizard['overall_status']} name='{wizard['identified_name']}' "
            f"formats={wizard['supported_formats']} sets={len(wizard['available_sets'])}"
        )

        print("[3/5] Verifying GetRecord & ResumptionToken page 2...")
        oai_client = OAIPMHClient(timeout_sec=90.0)
        recs_p1, tok1 = oai_client.list_records(new_url, metadata_prefix="oai_dc")
        sample_id = recs_p1[0].identifier if recs_p1 else "oai:eprints2.undip.ac.id:4"
        get_rec = oai_client.get_record(new_url, sample_id, metadata_prefix="oai_dc")
        recs_p2, tok2 = ([], None)
        if tok1:
            recs_p2, tok2 = oai_client.list_records(new_url, resumption_token=tok1)
        report["verbs_verification"] = {
            "list_records_p1_count": len(recs_p1),
            "resumption_token_p1": tok1,
            "get_record_identifier": get_rec.identifier if get_rec else None,
            "get_record_title": get_rec.title if get_rec else None,
            "get_record_landing_urls": get_rec.urls[:2] if get_rec else [],
            "get_record_pdf_urls": get_rec.pdf_urls[:2] if get_rec else [],
            "list_records_p2_count": len(recs_p2),
            "resumption_token_p2": tok2,
        }
        print(
            f"      P1={len(recs_p1)} recs, GetRecord='{sample_id}' ok={bool(get_rec)}, P2={len(recs_p2)} recs"
        )

        print("[4/5] Verifying Catalog Preset -> Uji Konektivitas -> Simpan -> Metadata-Only Harvest via API...")
        app = create_app()
        try:
            with TestClient(app) as tc:
                cat_res = tc.get("/api/oai/catalog?q=UNDIP")
                undip_entry = cat_res.json()["items"][0]
                assert undip_entry["oai_status"] == "UNVERIFIED"

                test_res = tc.post(f"/api/oai/catalog/{undip_entry['id']}/test")
                assert test_res.status_code == 200
                tested_entry = test_res.json()["entry"]
                assert tested_entry["oai_status"] in {"VERIFIED", "PARTIAL"}

                add_res = tc.post(f"/api/oai/catalog/{undip_entry['id']}/add")
                assert add_res.status_code == 200
                repo_obj = add_res.json()["repository"]
                assert repo_obj["default_download_pdfs"] is False
                assert repo_obj["harvesting_permission_status"] == "METADATA_ALLOWED_FULLTEXT_RESTRICTED"

                # Run bounded metadata-only harvest (max_records=5)
                harv_res = tc.post(
                    f"/api/oai/repositories/{repo_obj['id']}/harvest",
                    json={"max_records": 5},
                )
                assert harv_res.status_code == 200, harv_res.text
                h_data = harv_res.json()
                rec_list = tc.get(f"/api/oai/repositories/{repo_obj['id']}/records?limit=10").json()
                logs_list = tc.get(f"/api/oai/repositories/{repo_obj['id']}/logs?limit=20").json()

                report["api_e2e"] = {
                    "catalog_initial_status": undip_entry["oai_status"],
                    "catalog_tested_status": tested_entry["oai_status"],
                    "catalog_formats": tested_entry["supported_formats"],
                    "catalog_collections": tested_entry["collections_count"],
                    "personal_repo_status": h_data["repository"]["status"],
                    "fulltext_policy": h_data["repository"]["fulltext_policy"],
                    "harvesting_permission_status": h_data["repository"]["harvesting_permission_status"],
                    "harvest_summary": h_data["summary"],
                    "sample_saved_records": [
                        {
                            "oai_identifier": r["oai_identifier"],
                            "title": r["title"],
                            "status": r["status"],
                            "landing_urls": r["landing_urls"][:2],
                            "pdf_urls": r["pdf_urls"][:2],
                        }
                        for r in rec_list["items"][:5]
                    ],
                    "logs_count": len(logs_list),
                }
        finally:
            dispose_engine()

        out_path = ROOT / "benchmark" / "results" / "phase10_4_1_undip_live.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[5/5] Saved live UNDIP integration proof to {out_path}")
        return 0 if wizard["ok"] and len(recs_p2) > 0 and report["api_e2e"]["harvest_summary"]["fulltext_indexed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
