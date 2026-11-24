"""Tests for PDF/DOCX/TXT extraction, token offset invariants, and structure zones."""

from __future__ import annotations

from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.ingestion.docx_extractor import extract_docx
from app.ingestion.pdf import extract_pdf
from app.ingestion.segment import segment_document
from app.ingestion.structure import annotate_structure
from app.ingestion.tokenize import tokenize_with_offsets
from app.ingestion.txt import extract_txt


def test_pdf_extraction_and_offset_invariant(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "SKRIPSI PENELITIAN\n\nHalaman Sampul Universitas")
    page2 = doc.new_page()
    page2.insert_text(
        (72, 72),
        "BAB I PENDAHULUAN\n\nSistem pendeteksian kemiripan dokumen akademik sangat penting bagi integritas ilmiah.\n\n"
        "Daftar Pustaka\n\nSchleimer, S. (2003). Winnowing: Local Algorithms for Document Fingerprinting.",
    )
    doc.save(str(pdf_path))
    doc.close()

    extracted = extract_pdf(pdf_path)
    assert extracted.extraction_method == "TEXT"
    assert len(extracted.pages) == 2

    tokens = tokenize_with_offsets(extracted.text)
    assert len(tokens) > 10
    for tok in tokens:
        assert extracted.text[tok.char_start : tok.char_end] == tok.original

    segs = segment_document(extracted.text, extracted.pages, tokens)
    annotate_structure(extracted.text, extracted.pages, segs)
    zones = {s.zone for s in segs}
    assert "COVER" in zones
    assert "BODY" in zones
    assert "BIBLIOGRAPHY" in zones


def test_docx_and_txt_extraction(tmp_path: Path):
    docx_path = tmp_path / "sample.docx"
    d = DocxDocument()
    d.add_paragraph("Pendahuluan Penelitian")
    d.add_paragraph("Pembelajaran mesin mendukung analisis teks bahasa Indonesia secara efektif.")
    d.save(str(docx_path))

    ext_docx = extract_docx(docx_path)
    assert "Pembelajaran mesin" in ext_docx.text
    assert ext_docx.extra.get("page_number_estimated") is True

    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("Paragraf pertama tentang kecerdasan buatan.\n\nParagraf kedua tentang evaluasi.", encoding="utf-8")
    ext_txt = extract_txt(txt_path)
    assert "kecerdasan buatan" in ext_txt.text
