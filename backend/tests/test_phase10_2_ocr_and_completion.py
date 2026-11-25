"""Phase 10.2 tests: Local Tesseract OCR (5 scenarios), strict AI model check, and Combined E2E."""

from __future__ import annotations

import io
import random
import time
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import get_settings
from app.ingestion.ocr import get_ocr_status
from app.ingestion.pdf import extract_pdf
from app.main import create_app


def _load_readable_font(size: int = 34):
    for cand in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(cand).is_file():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def _render_text_image(lines: list[str], *, degrade: bool = False) -> bytes:
    img = Image.new("RGB", (1400, 520), color=(246, 244, 240) if degrade else (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _load_readable_font(36)
    y = 60
    ink = (70, 70, 70) if degrade else (15, 15, 15)
    for ln in lines:
        draw.text((70, y), ln, fill=ink, font=font)
        y += 62
    if degrade:
        rng = random.Random(42)
        px = img.load()
        for _ in range(4500):
            rx = rng.randint(0, img.width - 1)
            ry = rng.randint(0, img.height - 1)
            v = rng.randint(140, 225)
            px[rx, ry] = (v, v, v)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_scanned_pdf(path: Path, page_specs: list[tuple[str, object]]) -> Path:
    """Create PDF with ('image', png_bytes) or ('text', str) pages."""
    doc = fitz.open()
    for kind, payload in page_specs:
        page = doc.new_page(width=595.28, height=841.89)
        if kind == "image":
            page.insert_image(fitz.Rect(36, 72, 559, 290), stream=payload)
        else:
            page.insert_textbox(fitz.Rect(54, 72, 540, 500), str(payload), fontsize=12, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def test_local_ocr_five_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ocr_st = get_ocr_status()
    if not ocr_st.available:
        pytest.skip(f"Local Tesseract OCR not available: {ocr_st.message}")

    # 1. Scanned PDF — Bahasa Indonesia
    id_img = _render_text_image([
        "Penelitian kemiripan dokumen akademik",
        "berbasis korpus lokal di perguruan tinggi",
        "menjaga integritas karya ilmiah mahasiswa.",
    ])
    pdf_id = _make_scanned_pdf(tmp_path / "scan_id.pdf", [("image", id_img)])
    ext_id = extract_pdf(pdf_id)
    assert ext_id.extraction_method == "OCR"
    assert ext_id.ocr_pages == [1]
    assert ext_id.extraction_confidence >= 0.60
    low_id = ext_id.text.lower()
    assert "penelitian" in low_id and "akademik" in low_id

    # 2. Scanned PDF — Bahasa Inggris
    en_img = _render_text_image([
        "Academic integrity verification relies on",
        "transparent document comparison against",
        "open scholarly archives and local corpora.",
    ])
    pdf_en = _make_scanned_pdf(tmp_path / "scan_en.pdf", [("image", en_img)])
    ext_en = extract_pdf(pdf_en)
    assert ext_en.extraction_method == "OCR"
    assert ext_en.ocr_pages == [1]
    assert ext_en.extraction_confidence >= 0.60
    low_en = ext_en.text.lower()
    assert "academic" in low_en and "comparison" in low_en

    # 3. Mixed PDF (Page 1 native digital text + Page 2 scanned raster image)
    pdf_mix = _make_scanned_pdf(
        tmp_path / "mixed.pdf",
        [
            ("text", "Halaman pertama berisi teks digital asli tentang metode penelitian kuantitatif."),
            ("image", id_img),
        ],
    )
    ext_mix = extract_pdf(pdf_mix)
    assert ext_mix.extraction_method == "MIXED"
    assert ext_mix.ocr_pages == [2]
    assert "teks digital asli" in ext_mix.text.lower()
    assert "integritas" in ext_mix.text.lower()

    # 4. Low-quality degraded scan (blurred + speckled + low contrast)
    deg_img = _render_text_image(
        [
            "Evaluasi mutu arsip pindaian berkualitas rendah",
            "tetap terbaca menggunakan prapemrosesan gambar.",
        ],
        degrade=True,
    )
    pdf_deg = _make_scanned_pdf(tmp_path / "scan_lowq.pdf", [("image", deg_img)])
    ext_deg = extract_pdf(pdf_deg)
    assert ext_deg.extraction_method == "OCR"
    assert ext_deg.extraction_confidence > 0.0
    assert any(w in ext_deg.text.lower() for w in ("evaluasi", "arsip", "mutu", "gambar"))

    # 5. OCR disabled gracefully -> OCR_UNAVAILABLE without breaking digital PDF
    monkeypatch.setenv("NG_OCR_ENABLED", "false")
    get_settings.cache_clear()
    try:
        ext_off = extract_pdf(pdf_id)
        assert ext_off.extraction_method == "OCR_UNAVAILABLE"
        assert "ocr_warning" in ext_off.extra
        pdf_dig = _make_scanned_pdf(tmp_path / "digital_only.pdf", [("text", "Dokumen PDF teks digital murni tanpa pindaian.")])
        ext_dig = extract_pdf(pdf_dig)
        assert ext_dig.extraction_method == "TEXT"
        assert ext_dig.extraction_confidence == 1.0
    finally:
        monkeypatch.delenv("NG_OCR_ENABLED", raising=False)
        get_settings.cache_clear()


def test_combined_examination_and_ai_report_fields_and_model_guard(isolated_env):
    app = create_app()
    with TestClient(app) as client:
        copied = (
            "Pengukuran ketinggian matahari pada awal waktu salat Idain dalam kajian ilmu falak "
            "berpedoman pada ketinggian sekitar empat hingga enam derajat di atas ufuk timur."
        )
        r_corp = client.post(
            "/api/corpus",
            files={"file": ("sumber_falak.txt", copied.encode("utf-8"), "text/plain")},
            data={"title": "Rujukan Falak Klasik", "authors": "A. Hakim", "year": "2024"},
        )
        assert r_corp.status_code == 201

        doc_text = (
            f"{copied} Pengamatan kami di Gresik pada Mei 2023 mencatat jeda 19 menit sejak terbit.\n\n"
            "Di era modern saat ini, optimalisasi tata kelola layanan publik memainkan peran krusial dalam "
            "meningkatkan mutu kelembagaan secara berkelanjutan. Selain itu, pendekatan komprehensif dan sinergi "
            "antara berbagai pemangku kepentingan memberikan wawasan berharga guna merumuskan langkah strategis yang "
            "terukur secara konsisten, adaptif, dan transparan bagi seluruh masyarakat."
        )
        r_doc = client.post(
            "/api/documents",
            files={"file": ("naskah_gabungan.txt", doc_text.encode("utf-8"), "text/plain")},
            data={"title": "Uji Gabungan Phase 10.2"},
        )
        assert r_doc.status_code == 201
        doc_id = r_doc.json()["id"]

        # Uninstalled optional model must be rejected cleanly with 400
        r_bad = client.post(
            "/api/checks",
            json={
                "document_id": doc_id,
                "settings": {"check_mode": "COMBINED", "ai_model_id": "ng-fast-detect-curv-en"},
            },
        )
        assert r_bad.status_code == 400

        # Valid COMBINED check
        r_chk = client.post(
            "/api/checks",
            json={
                "document_id": doc_id,
                "settings": {
                    "check_mode": "COMBINED",
                    "use_external_sources": False,
                    "min_match_words": 5,
                },
            },
        )
        assert r_chk.status_code == 202
        cid = r_chk.json()["check_id"]
        for _ in range(80):
            st = client.get(f"/api/checks/{cid}").json()
            if st["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.1)
        assert st["status"] == "COMPLETED"

        rep = client.get(f"/api/checks/{cid}/report").json()
        assert rep["metrics"]["similarity_index"] > 0.0
        ai = rep["ai_report"]
        assert ai is not None
        assert ai["score_available"] is True
        assert rep["metrics"]["similarity_index"] != ai["ai_likelihood_pct"]
        assert ai["paragraph_summary"]["total_paragraphs"] == 2
        assert ai["calibration"]["calibrated"] is True
        assert ai["calibration"]["temperature"] == 1.3

        # PDF, HTML, JSON exports all succeed with isolated AI summary
        assert client.get(f"/api/checks/{cid}/export.json").status_code == 200
        html_txt = client.get(f"/api/checks/{cid}/export.html").text
        assert "Highlight Analisis per Paragraf" in html_txt
        assert "Total Paragraf" in html_txt
        pdf_bytes = client.get(f"/api/checks/{cid}/export.pdf").content
        assert pdf_bytes.startswith(b"%PDF")
