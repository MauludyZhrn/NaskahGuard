"""DOCX extractor using python-docx with explicit page break estimation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from docx.oxml.ns import qn

from app.ingestion.pdf import ExtractedDocument, _join_pages


def _paragraph_has_page_break(paragraph) -> bool:
    for elem in paragraph._element.iter():
        if elem.tag == qn("w:br") and elem.get(qn("w:type")) == "page":
            return True
        if elem.tag == qn("w:lastRenderedPageBreak"):
            return True
    return False


def extract_docx(file_path: Path) -> ExtractedDocument:
    doc = DocxDocument(str(file_path))
    props = doc.core_properties
    title = (props.title or "").strip() or None
    author_raw = (props.author or "").strip()
    authors = [a.strip() for a in author_raw.split(";") if a.strip()] if author_raw else []

    pages_buf: list[list[str]] = [[]]
    has_explicit_breaks = False

    # Walk body children in order (paragraphs and tables)
    body = doc.element.body
    para_map = {p._element: p for p in doc.paragraphs}
    table_map = {t._element: t for t in doc.tables}

    for child in body:
        if child in para_map:
            p = para_map[child]
            if _paragraph_has_page_break(p) and pages_buf[-1]:
                pages_buf.append([])
                has_explicit_breaks = True
            txt = p.text.strip()
            if txt:
                pages_buf[-1].append(txt)
        elif child in table_map:
            tbl = table_map[child]
            for row in tbl.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    pages_buf[-1].append(" | ".join(row_cells))

    page_items: list[tuple[int, str, bool, float | None]] = []
    for idx, para_list in enumerate(pages_buf, start=1):
        page_items.append((idx, "\n\n".join(para_list), False, None))

    full_text, pages = _join_pages(page_items)
    extra: dict[str, Any] = {
        "page_number_estimated": True,
        "explicit_page_breaks_found": has_explicit_breaks,
        "page_note": (
            "Nomor halaman pada berkas DOCX diestimasi berdasarkan pemisah halaman eksplisit "
            "(DOCX tidak menyimpan tata letak halaman tetap tanpa mesin rendering)."
        ),
    }

    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=title,
        authors=authors,
        extraction_method="TEXT",
        extraction_confidence=1.0,
        ocr_pages=[],
        extra=extra,
    )
