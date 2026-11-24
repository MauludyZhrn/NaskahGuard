"""End-to-end smoke test using synthetic sample files via FastAPI TestClient."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app import config  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    corpus_sample = ROOT / "samples" / "contoh_sumber_korpus.txt"
    sub_sample = ROOT / "samples" / "contoh_naskah_uji.txt"

    with tempfile.TemporaryDirectory(prefix="ng_smoke_") as tmp_dir:
        tmp = Path(tmp_dir)
        os.environ["NG_DATABASE_URL"] = f"sqlite:///{(tmp / 'smoke.db').as_posix()}"
        os.environ["NG_STORAGE_DIR"] = str(tmp / "storage")
        os.environ["NG_API_TOKEN"] = ""
        os.environ["NG_HOST"] = "127.0.0.1"
        config.get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            h = client.get("/api/health")
            assert h.status_code == 200, f"Health check failed: {h.text}"

            r_corp = client.post(
                "/api/corpus",
                files={"file": (corpus_sample.name, corpus_sample.read_bytes(), "text/plain")},
                data={"title": "Contoh Artikel Referensi (Sintetis)", "authors": "Tim Uji", "year": "2026"},
            )
            assert r_corp.status_code == 201, r_corp.text

            r_sub = client.post(
                "/api/documents",
                files={"file": (sub_sample.name, sub_sample.read_bytes(), "text/plain")},
            )
            assert r_sub.status_code == 201, r_sub.text
            sub_id = r_sub.json()["id"]

            r_chk = client.post("/api/checks", json={"document_id": sub_id})
            assert r_chk.status_code == 202, r_chk.text
            check_id = r_chk.json()["check_id"]

            status_data = None
            for _ in range(50):
                res = client.get(f"/api/checks/{check_id}")
                status_data = res.json()
                if status_data["status"] in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(0.1)

            assert status_data and status_data["status"] == "COMPLETED", status_data
            si = float(status_data["metrics"]["similarity_index"])
            assert si > 0.0, f"Expected SI > 0, got {si}"

            pdf_res = client.get(f"/api/checks/{check_id}/export.pdf")
            assert pdf_res.status_code == 200 and pdf_res.content.startswith(b"%PDF")

            print(
                f"[SMOKE OK] Report={status_data['report_number']} "
                f"SI={si:.2f}% MatchedWords={status_data['metrics']['matched_words']}/{status_data['metrics']['eligible_words']} "
                f"PDFBytes={len(pdf_res.content)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
