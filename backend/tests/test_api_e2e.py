"""End-to-end API tests via FastAPI TestClient including auth, exports, and deletion."""

from __future__ import annotations

import io
import time
import fitz
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.security import validate_startup_security


def _build_pdf_bytes(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


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


def test_e2e_pdf_and_docx_upload_corpus_detection_highlights_and_percentage(isolated_env):
    """End-to-end integration test uploading real PDF corpus and DOCX submission (and vice versa)."""
    app = create_app()

    exact_para = (
        "Algoritma winnowing memilih nilai hash minimum paling kanan pada setiap jendela geser "
        "sehingga mampu mendeteksi penyalinan teks akademik secara efisien dan deterministik."
    )
    near_src = (
        "Pendekatan penyelarasan urutan kata berbasis bibit tiga-gram menemukan modifikasi ringan "
        "berupa penggantian beberapa kata penghubung di dalam paragraf ilmiah."
    )
    near_sub = (
        "Pendekatan penyelarasan urutan kata berbasis bibit tiga-gram menemukan perubahan ringan "
        "berupa penggantian beberapa kata sambung di dalam paragraf ilmiah."
    )
    bib_entry = "Schleimer, S., Wilkerson, D. S., & Aiken, A. (2003). Winnowing: Local Algorithms for Document Fingerprinting."

    corpus_pdf = _build_pdf_bytes(
        [
            f"Artikel Referensi Utama\n\n{exact_para}\n\n{near_src}",
            f"Daftar Pustaka\n\n{bib_entry}",
        ]
    )
    sub_docx = _build_docx_bytes(
        [
            "BAB I PENDAHULUAN",
            "Paragraf pembuka ini ditulis secara mandiri oleh peneliti tanpa menyalin sumber lain.",
            exact_para,
            near_sub,
            "Daftar Pustaka",
            bib_entry,
        ]
    )

    with TestClient(app) as client:
        r_corp = client.post(
            "/api/corpus",
            files={"file": ("referensi.pdf", corpus_pdf, "application/pdf")},
            data={"title": "Referensi PDF", "authors": "Peneliti Uji", "year": "2025"},
        )
        assert r_corp.status_code == 201, r_corp.text
        corp_id = r_corp.json()["id"]
        assert r_corp.json()["file_type"] == "pdf"
        assert r_corp.json()["page_count"] == 2

        r_sub = client.post(
            "/api/documents",
            files={
                "file": (
                    "naskah_uji.docx",
                    sub_docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert r_sub.status_code == 201, r_sub.text
        sub_id = r_sub.json()["id"]
        assert r_sub.json()["file_type"] == "docx"

        r_chk = client.post(
            "/api/checks",
            json={"document_id": sub_id, "settings": {"exclude_bibliography": True, "min_match_words": 8}},
        )
        assert r_chk.status_code == 202, r_chk.text
        check_id = r_chk.json()["check_id"]

        status_data = None
        for _ in range(50):
            res = client.get(f"/api/checks/{check_id}")
            status_data = res.json()
            if status_data["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.1)

        assert status_data is not None and status_data["status"] == "COMPLETED", status_data
        metrics = status_data["metrics"]
        assert metrics["similarity_index"] > 30.0
        assert metrics["exact_match_pct"] > 0.0
        assert metrics["near_exact_match_pct"] > 0.0
        assert metrics["raw_similarity"] > metrics["adjusted_similarity"]

        viewer = client.get(f"/api/checks/{check_id}/viewer").json()
        categories = {s["category"] for s in viewer["segments"]}
        assert "EXACT" in categories
        assert "NEAR_EXACT" in categories
        assert "EXCLUDED" in categories
        for seg in viewer["segments"]:
            assert viewer["text"][seg["char_start"] : seg["char_end"]] == seg["text"]

        src_viewer = client.get(f"/api/checks/{check_id}/sources/{corp_id}/viewer").json()
        assert len(src_viewer["highlights"]) >= 2

        pdf_export = client.get(f"/api/checks/{check_id}/export.pdf")
        assert pdf_export.status_code == 200
        assert pdf_export.content.startswith(b"%PDF")

        # Also test PDF submission against DOCX corpus
        corpus_docx = _build_docx_bytes([exact_para])
        sub_pdf = _build_pdf_bytes([f"BAB I\n\n{exact_para}\n\nKalimat penutup yang asli dan unik."])
        rc2 = client.post(
            "/api/corpus",
            files={
                "file": (
                    "sumber.docx",
                    corpus_docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"title": "Sumber DOCX"},
        )
        assert rc2.status_code == 201
        rs2 = client.post(
            "/api/documents",
            files={"file": ("uji.pdf", sub_pdf, "application/pdf")},
        )
        assert rs2.status_code == 201
        rk2 = client.post("/api/checks", json={"document_id": rs2.json()["id"]})
        assert rk2.status_code == 202
        cid2 = rk2.json()["check_id"]
        st2 = None
        for _ in range(50):
            st2 = client.get(f"/api/checks/{cid2}").json()
            if st2["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.1)
        assert st2 and st2["status"] == "COMPLETED"
        assert st2["metrics"]["exact_match_pct"] > 50.0
