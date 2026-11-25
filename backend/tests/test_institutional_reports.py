"""Tests for institutional PDF/HTML/Web report redesign, integrity flags, and source colors."""

from __future__ import annotations

import time
import fitz
from fastapi.testclient import TestClient

from app.main import create_app
from app.reports.integrity_flags import (
    classify_source_category,
    color_for_rank,
    compute_source_category_summary,
    detect_integrity_flags,
    extract_active_filters,
)


def _poll_check(client: TestClient, check_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/checks/{check_id}")
        assert res.status_code == 200
        data = res.json()
        if data["status"] in {"COMPLETED", "FAILED"}:
            return data
        time.sleep(0.12)
    raise AssertionError(f"Check {check_id} did not finish within {timeout}s")


def _make_sample_pdf_bytes(paragraphs: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    y = 72
    page.insert_text((72, y), "Kajian Awal Waktu Salat Idain dalam Perspektif Ilmu Falak", fontsize=14, fontname="helv")
    y += 30
    for para in paragraphs:
        rect = fitz.Rect(72, y, 523, y + 120)
        page.insert_textbox(rect, para, fontsize=10.5, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
        y += 126
    out = doc.tobytes()
    doc.close()
    return out


def test_integrity_flags_homoglyphs_and_arabic_safety():
    # Legitimate Arabic text mixed with Indonesian must NOT trigger homoglyph flag
    clean_arabic = (
        "Pandangan Imam al-Syafi'i dalam kitab al-Umm (الإمام الشافعي في كتاب الأم) "
        "menjelaskan awal waktu salat Idain ketika matahari telah terbit setinggi tombak."
    )
    assert detect_integrity_flags(clean_arabic, [{"number": 1, "char_start": 0, "char_end": len(clean_arabic)}]) == []

    # Cyrillic 'а' (\u0430) and 'е' (\u0435) disguised inside Latin words MUST trigger flag
    suspicious = (
        "P\u0435nelitian ini m\u0435nggunakan metod\u0435 komparatif pada s\u0430mpel naskah akademik "
        "dan menyisipkan k\u200ba\u200bt\u200ba tersembunyi di tengah paragraf."
    )
    flags = detect_integrity_flags(suspicious, [{"number": 2, "char_start": 0, "char_end": len(suspicious)}])
    codes = {f["code"] for f in flags}
    assert "REPLACED_CHARACTERS" in codes
    assert "HIDDEN_CHARACTERS" in codes
    rep_flag = next(f for f in flags if f["code"] == "REPLACED_CHARACTERS")
    assert rep_flag["count"] == 4
    assert rep_flag["pages_count"] == 1


def test_source_palette_categories_and_filters():
    c1 = color_for_rank(1)
    c2 = color_for_rank(2)
    assert c1["badge"] == "#6E1F2F"
    assert c2["badge"] != c1["badge"]

    assert classify_source_category("journal", "openalex") == ("publication", "Publikasi")
    assert classify_source_category("web_page", "web_search") == ("internet", "Internet")
    assert classify_source_category("local_corpus", "local_corpus") == ("local", "Korpus Lokal")

    summary = compute_source_category_summary(
        [
            {"source_type": "journal", "provider": "openalex", "contribution_pct": 8.4},
            {"source_type": "web", "provider": "web_search", "contribution_pct": 3.2},
            {"source_type": "local", "provider": "local_corpus", "contribution_pct": 2.5},
        ]
    )
    assert summary["publication_pct"] == 8.4
    assert summary["internet_pct"] == 3.2
    assert summary["local_pct"] == 2.5
    assert summary["counts"] == {"internet": 1, "publication": 1, "local": 1}

    filters = extract_active_filters({"exclude_bibliography": True, "exclude_quotes": True, "exclude_citations": False})
    assert filters == ["Daftar Pustaka", "Kutipan Langsung"]


def test_e2e_institutional_pdf_and_html_report_for_pdf_and_txt(isolated_env):
    app = create_app()
    with TestClient(app) as client:
        shared_text = (
            "Perhitungan awal waktu salat Idain dalam ilmu falak klasik menggunakan ketinggian matahari "
            "sekitar empat sampai enam derajat di atas ufuk timur sebagai padanan tinggi satu tombak."
        )
        r_corp = client.post(
            "/api/corpus",
            files={"file": ("kitab_falak_ref.txt", shared_text.encode("utf-8"), "text/plain")},
            data={"title": "Rujukan Ilmu Falak Nusantara", "authors": "A. Hakim", "year": "2024"},
        )
        assert r_corp.status_code == 201

        # 1. Real PDF upload (triggers PyMuPDF original-page annotation + front-matter merge)
        pdf_bytes = _make_sample_pdf_bytes(
            [
                shared_text + " Pendekatan ini banyak dirujuk oleh lembaga hisab di Indonesia.",
                "Selain itu, p\u0435ngamatan empiris dilakukan pada halaman kedua naskah uji untuk memastikan "
                "ketepatan penandaan integritas karakter dan tata letak laporan resmi NaskahGuard.",
            ]
        )
        r_pdf = client.post(
            "/api/documents",
            files={"file": ("naskah_falak.pdf", pdf_bytes, "application/pdf")},
        )
        assert r_pdf.status_code == 201
        pdf_doc_id = r_pdf.json()["id"]

        r_chk = client.post(
            "/api/checks",
            json={
                "document_id": pdf_doc_id,
                "settings": {
                    "check_mode": "COMBINED",
                    "exclude_bibliography": True,
                    "exclude_quotes": True,
                    "use_external_sources": False,
                    "min_match_words": 5,
                },
            },
        )
        assert r_chk.status_code == 202
        check_id = r_chk.json()["check_id"]
        finished = _poll_check(client, check_id)
        assert finished["status"] == "COMPLETED"

        # Verify report JSON payload
        rep_res = client.get(f"/api/checks/{check_id}/report")
        assert rep_res.status_code == 200
        rep = rep_res.json()
        assert "Daftar Pustaka" in rep["active_filters"]
        assert "Kutipan Langsung" in rep["active_filters"]
        assert rep["source_categories"]["counts"]["local"] >= 1
        assert len(rep["sources"]) >= 1
        assert rep["sources"][0]["color_hex"] == "#6E1F2F"
        assert rep["sources"][0]["category_label"] == "Korpus Lokal"
        assert rep["ai_report"] is not None

        # Verify viewer payload carries source_rank & source_color
        vw_res = client.get(f"/api/checks/{check_id}/viewer")
        assert vw_res.status_code == 200
        vw = vw_res.json()
        assert any(seg.get("source_rank") == 1 and seg.get("source_color") == "#6E1F2F" for seg in vw["segments"])

        # Verify HTML export
        html_res = client.get(f"/api/checks/{check_id}/export.html")
        assert html_res.status_code == 200
        html_body = html_res.text
        assert "NaskahGuard" in html_body
        assert "Daftar Sumber Utama" in html_body
        assert "Naskah Berpenanda" in html_body
        assert "#6E1F2F" in html_body

        # Verify PDF export (front matter + annotated original PDF page merged with uniform headers/footers)
        pdf_exp = client.get(f"/api/checks/{check_id}/export.pdf")
        assert pdf_exp.status_code == 200
        assert pdf_exp.content.startswith(b"%PDF")
        rendered = fitz.open(stream=pdf_exp.content, filetype="pdf")
        assert rendered.page_count >= 4
        p1_txt = rendered[0].get_text()
        p2_txt = rendered[1].get_text()
        p3_txt = rendered[2].get_text()
        all_text = "\n".join(rendered[i].get_text() for i in range(rendered.page_count))
        assert "Halaman 1 dari" in p1_txt and "Sampul Laporan" in p1_txt
        assert "Halaman 2 dari" in p2_txt and "Ringkasan Integritas" in p2_txt
        assert "Halaman 3 dari" in p3_txt and "Daftar Sumber Utama" in p3_txt
        assert "Naskah Berpenanda" in all_text
        assert f"Halaman {rendered.page_count} dari {rendered.page_count}" in all_text
        rendered.close()

        # 2. TXT upload with Cyrillic homoglyph (verifies integrity flag E2E + ReportLab annotated-paragraph fallback path)
        r_txt = client.post(
            "/api/documents",
            files={
                "file": (
                    "naskah_teks.txt",
                    (shared_text + "\n\nParagraf asli p\u0435nulis s\u0435ndiri untuk uji tanda integritas.").encode("utf-8"),
                    "text/plain",
                )
            },
        )
        assert r_txt.status_code == 201
        r_chk2 = client.post(
            "/api/checks",
            json={
                "document_id": r_txt.json()["id"],
                "settings": {"check_mode": "PLAGIARISM_ONLY", "use_external_sources": False, "min_match_words": 5},
            },
        )
        assert r_chk2.status_code == 202
        cid2 = r_chk2.json()["check_id"]
        assert _poll_check(client, cid2)["status"] == "COMPLETED"
        rep2 = client.get(f"/api/checks/{cid2}/report").json()
        assert any(f["code"] == "REPLACED_CHARACTERS" for f in rep2["integrity_flags"])
        pdf_exp2 = client.get(f"/api/checks/{cid2}/export.pdf")
        assert pdf_exp2.status_code == 200
        rendered2 = fitz.open(stream=pdf_exp2.content, filetype="pdf")
        assert rendered2.page_count >= 3
        rendered2.close()
