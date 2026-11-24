"""End-to-end API tests via FastAPI TestClient including auth, exports, and deletion."""

from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.security import validate_startup_security


def test_non_loopback_host_without_token_rejected():
    cfg = config.Settings(HOST="0.0.0.0", API_TOKEN="")
    with pytest.raises(RuntimeError):
        validate_startup_security(cfg)


def test_e2e_corpus_check_exports_and_delete(isolated_env):
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/config").json()["app_name"] == "NaskahGuard"

        corpus_text = (
            "Pendekatan berbasis winnowing dan indeks n-gram kata sangat efektif dalam mendeteksi "
            "penyalinan teks verbatim pada naskah skripsi dan artikel jurnal ilmiah Indonesia."
        )
        r_corp = client.post(
            "/api/corpus",
            files={"file": ("referensi.txt", corpus_text.encode("utf-8"), "text/plain")},
            data={"title": "Studi Winnowing", "authors": "Ahmad, Dewi", "year": "2024"},
        )
        assert r_corp.status_code == 201
        corp_id = r_corp.json()["id"]

        sub_text = (
            f"Bab Pendahuluan.\n\n{corpus_text}\n\n"
            "Bagian kesimpulan ini ditulis secara mandiri oleh penulis tanpa menyalin sumber."
        )
        r_sub = client.post(
            "/api/documents",
            files={"file": ("skripsi_uji.txt", sub_text.encode("utf-8"), "text/plain")},
        )
        assert r_sub.status_code == 201
        sub_id = r_sub.json()["id"]

        r_chk = client.post("/api/checks", json={"document_id": sub_id})
        assert r_chk.status_code == 202
        check_id = r_chk.json()["check_id"]

        # Poll until COMPLETED
        status_data = None
        for _ in range(40):
            res = client.get(f"/api/checks/{check_id}")
            assert res.status_code == 200
            status_data = res.json()
            if status_data["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.1)

        assert status_data is not None
        assert status_data["status"] == "COMPLETED"
        assert status_data["metrics"]["similarity_index"] > 40.0

        # Report & Viewer
        rep = client.get(f"/api/checks/{check_id}/report")
        assert rep.status_code == 200
        assert len(rep.json()["sources"]) == 1

        viewer = client.get(f"/api/checks/{check_id}/viewer")
        assert viewer.status_code == 200
        assert any(seg["category"] == "EXACT" for seg in viewer.json()["segments"])

        src_viewer = client.get(f"/api/checks/{check_id}/sources/{corp_id}/viewer")
        assert src_viewer.status_code == 200
        assert len(src_viewer.json()["highlights"]) >= 1

        # Exports (PDF, HTML, JSON)
        pdf_res = client.get(f"/api/checks/{check_id}/export.pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF")

        html_res = client.get(f"/api/checks/{check_id}/export.html")
        assert html_res.status_code == 200
        assert "NaskahGuard" in html_res.text

        json_res = client.get(f"/api/checks/{check_id}/export.json")
        assert json_res.status_code == 200
        assert json_res.json()["check_id"] == check_id

        # Dashboard reflects real checked data
        dash = client.get("/api/dashboard").json()
        assert dash["total_documents_checked"] >= 1

        # Delete submission removes document & check
        del_res = client.delete(f"/api/documents/{sub_id}")
        assert del_res.status_code == 200
        assert client.get(f"/api/documents/{sub_id}").status_code == 404
        assert client.get(f"/api/checks/{check_id}").status_code == 404


def test_api_token_enforced_when_configured(isolated_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NG_API_TOKEN", "rahasia-123")
    config.get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/config").status_code == 401
        assert client.get("/api/config", headers={"Authorization": "Bearer salah"}).status_code == 403
        assert client.get("/api/config", headers={"Authorization": "Bearer rahasia-123"}).status_code == 200
