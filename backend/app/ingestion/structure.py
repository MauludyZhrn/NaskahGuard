"""Document structure detection: zones (BODY, BIBLIOGRAPHY, TOC, COVER) and chapter labels."""

from __future__ import annotations

import re

from app.ingestion.pdf import PageSpan
from app.ingestion.segment import SegmentSpan

_BIB_HEADING_RE = re.compile(
    r"^(daftar\s+pustaka|daftar\s+rujukan|referensi|kepustakaan|bibliography|references)\s*:?\s*$",
    re.IGNORECASE,
)
_APPENDIX_HEADING_RE = re.compile(r"^(lampiran|appendix)\b", re.IGNORECASE)
_TOC_HEADING_RE = re.compile(r"^(daftar\s+isi|table\s+of\s+contents)\s*:?\s*$", re.IGNORECASE)
_TOC_LINE_RE = re.compile(r"\.{4,}\s*\d+\s*$", re.MULTILINE)
_BAB_RE = re.compile(r"^(BAB\s+[IVXLC\d]+(?:\s*[:\-–]\s*.+)?|CHAPTER\s+\d+(?:\s*[:\-–]\s*.+)?)", re.IGNORECASE)

_SECTION_KEYWORDS = [
    "abstrak",
    "abstract",
    "pendahuluan",
    "introduction",
    "tinjauan pustaka",
    "kajian pustaka",
    "landasan teori",
    "metode penelitian",
    "metodologi penelitian",
    "methods",
    "methodology",
    "hasil dan pembahasan",
    "results and discussion",
    "results",
    "discussion",
    "kesimpulan",
    "simpulan",
    "conclusion",
    "conclusions",
]


def _detect_toc_pages(original_text: str, pages: list[PageSpan]) -> set[int]:
    toc_pages: set[int] = set()
    for p in pages:
        chunk = original_text[p.char_start:p.char_end]
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        has_heading = any(_TOC_HEADING_RE.match(ln) for ln in lines[:5])
        dot_lines = len(_TOC_LINE_RE.findall(chunk))
        if has_heading or dot_lines >= 3:
            toc_pages.add(p.number)
    return toc_pages


def _extract_heading_label(text: str) -> str | None:
    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if not first_line or len(first_line) > 100:
        return None
    m_bab = _BAB_RE.match(first_line)
    if m_bab:
        return m_bab.group(1).strip()[:120]
    cleaned = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", first_line).strip(": ").lower()
    for kw in _SECTION_KEYWORDS:
        if cleaned == kw or cleaned.startswith(kw + " "):
            return first_line[:120]
    return None


def annotate_structure(
    original_text: str,
    pages: list[PageSpan],
    segments: list[SegmentSpan],
    *,
    is_docx_without_breaks: bool = False,
) -> list[SegmentSpan]:
    """Assign zone (BODY, BIBLIOGRAPHY, TOC, COVER) and section_label to each segment."""
    toc_pages = _detect_toc_pages(original_text, pages)
    page_count = len(pages)

    in_bibliography = False
    current_section: str | None = "Bagian Awal"

    for seg in segments:
        lines = [ln.strip() for ln in seg.original_text.splitlines() if ln.strip()]
        first_line = lines[0] if lines else ""

        # Check heading transitions
        if any(_BIB_HEADING_RE.match(ln) for ln in lines):
            in_bibliography = True
            current_section = "Daftar Pustaka"
        elif in_bibliography and any(_APPENDIX_HEADING_RE.match(ln) for ln in lines):
            in_bibliography = False
            current_section = "Lampiran"
        else:
            lbl = _extract_heading_label(seg.original_text)
            if lbl:
                current_section = lbl

        if in_bibliography:
            seg.zone = "BIBLIOGRAPHY"
        elif seg.page_number is not None and seg.page_number in toc_pages:
            seg.zone = "TOC"
        elif page_count > 1 and seg.page_number == 1 and not is_docx_without_breaks:
            seg.zone = "COVER"
        elif is_docx_without_breaks and page_count > 1 and seg.token_end <= 150:
            seg.zone = "COVER"
        elif _TOC_HEADING_RE.match(first_line):
            seg.zone = "TOC"
        else:
            seg.zone = "BODY"

        seg.section_label = current_section

    return segments
