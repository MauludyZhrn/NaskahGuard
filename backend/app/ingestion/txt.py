"""Plain text (.txt) extractor supporting UTF-8-SIG and CP1252 fallback."""

from __future__ import annotations

from pathlib import Path

from app.ingestion.pdf import ExtractedDocument, _join_pages


def extract_txt(file_path: Path) -> ExtractedDocument:
    raw = file_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_pages = text.split("\f") if "\f" in text else [text]
    page_items = [(idx, p.strip(), False, None) for idx, p in enumerate(raw_pages, start=1)]
    full_text, pages = _join_pages(page_items)

    return ExtractedDocument(
        text=full_text,
        pages=pages,
        title=None,
        authors=[],
        extraction_method="TEXT",
        extraction_confidence=1.0,
        ocr_pages=[],
        extra={"encoding": "utf-8/cp1252"},
    )
