"""PDF extractor supporting PyMuPDF (AGPL-3.0) and pypdf (BSD-3-Clause fallback)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ingestion.ocr import get_ocr_status, ocr_png_bytes


@dataclass
class PageSpan:
    number: int
    char_start: int
    char_end: int
    used_ocr: bool = False
    ocr_confidence: float | None = None


@dataclass
class ExtractedDocument:
    text: str
    pages: list[PageSpan]
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    extraction_method: str = "TEXT"  # TEXT | OCR | MIXED | OCR_UNAVAILABLE
    extraction_confidence: float = 1.0
    ocr_pages: list[int] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def _join_pages(page_texts: list[tuple[int, str, bool, float | None]]) -> tuple[str, list[PageSpan]]:
    parts: list[str] = []
    pages: list[PageSpan] = []
    cursor = 0
    for idx, (page_num, page_text, used_ocr, conf) in enumerate(page_texts):
        if idx > 0:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(page_text)
        cursor += len(page_text)
        pages.append(
            PageSpan(
                number=page_num,
                char_start=start,
                char_end=cursor,
                used_ocr=used_ocr,
                ocr_confidence=conf,
            )
        )
    return "".join(parts), pages


def extract_pdf(file_path: Path) -> ExtractedDocument:
    settings = get_settings()
    if settings.PDF_BACKEND == "pypdf":
        return _extract_with_pypdf(file_path)
    return _extract_with_pymupdf(file_path)


def _extract_with_pymupdf(file_path: Path) -> ExtractedDocument:
    import fitz  # PyMuPDF

    ocr_status = get_ocr_status()
    page_items: list[tuple[int, str, bool, float | None]] = []
    ocr_pages: list[int] = []
    ocr_confs: list[float] = []
    text_pages = 0
    ocr_unavailable_pages: list[int] = []

    with fitz.open(str(file_path)) as doc:
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip() or None
        author_raw = (meta.get("author") or "").strip()
        authors = [a.strip() for a in author_raw.split(";") if a.strip()] if author_raw else []

        for page_idx, page in enumerate(doc, start=1):
            raw_text = (page.get_text("text") or "").replace("\r\n", "\n").strip()
            non_ws = len("".join(raw_text.split()))
            if non_ws < 20:
                if ocr_status.available:
                    pix = page.get_pixmap(dpi=300)
                    ocr_txt, conf = ocr_png_bytes(pix.tobytes("png"))
                    raw_text = ocr_txt.strip()
                    ocr_pages.append(page_idx)
                    ocr_confs.append(conf)
                    page_items.append((page_idx, raw_text, True, conf))
                    continue
                else:
                    ocr_unavailable_pages.append(page_idx)
            else:
                text_pages += 1
            page_items.append((page_idx, raw_text, False, None))

    full_text, pages = _join_pages(page_items)
    if ocr_pages and text_pages > 0:
        method = "MIXED"
        conf = round(sum(ocr_confs) / len(ocr_confs), 4)
    elif ocr_pages:
        method = "OCR"
        conf = round(sum(ocr_confs) / len(ocr_confs), 4)
    elif ocr_unavailable_pages and text_pages == 0:
        method = "OCR_UNAVAILABLE"
        conf = 0.0
    else:
        method = "TEXT"
        conf = 1.0

    extra: dict[str, Any] = {"pdf_backend": "pymupdf"}
    if ocr_unavailable_pages:
        extra["ocr_warning"] = (
            f"Halaman {ocr_unavailable_pages} memiliki teks sangat sedikit (diduga hasil pindaian), "
            f"namun OCR lokal tidak tersedia: {ocr_status.message}"
        )

    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=title,
        authors=authors,
        extraction_method=method,
        extraction_confidence=conf,
        ocr_pages=ocr_pages,
        extra=extra,
    )


def _extract_with_pypdf(file_path: Path) -> ExtractedDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    meta = reader.metadata or {}
    title = str(meta.get("/Title") or "").strip() or None
    author_raw = str(meta.get("/Author") or "").strip()
    authors = [a.strip() for a in author_raw.split(";") if a.strip()] if author_raw else []

    page_items: list[tuple[int, str, bool, float | None]] = []
    low_text_pages: list[int] = []
    for idx, page in enumerate(reader.pages, start=1):
        txt = (page.extract_text() or "").replace("\r\n", "\n").strip()
        if len("".join(txt.split())) < 20:
            low_text_pages.append(idx)
        page_items.append((idx, txt, False, None))

    full_text, pages = _join_pages(page_items)
    extra: dict[str, Any] = {"pdf_backend": "pypdf"}
    method = "TEXT"
    conf = 1.0
    if low_text_pages and len(low_text_pages) == len(page_items):
        method = "OCR_UNAVAILABLE"
        conf = 0.0
        extra["ocr_warning"] = "PDF tampak berbasis gambar/pindaian dan backend pypdf tidak menjalankan OCR."

    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=title,
        authors=authors,
        extraction_method=method,
        extraction_confidence=conf,
        ocr_pages=[],
        extra=extra,
    )
