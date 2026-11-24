"""Paragraph and sentence segmentation preserving original character and token offsets."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from app.ingestion.pdf import PageSpan
from app.ingestion.tokenize import TokenSpan

_ABBREVS = {
    "dkk", "hlm", "dll", "dsb", "dr", "prof", "ir", "no", "vol", "hal",
    "fig", "tab", "bab", "pp", "ed", "eds", "al", "e.g", "i.e", "etc",
    "vs", "mr", "mrs", "ms", "st", "s.kom", "m.kom", "s.si", "m.sc", "ph.d",
}

_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")
_SENT_END_RE = re.compile(r"([.!?]+)(\s+|$)")


@dataclass
class SegmentSpan:
    page_number: int | None
    paragraph_number: int
    sentence_number: int
    char_start: int
    char_end: int
    token_start: int
    token_end: int
    original_text: str
    normalized_text: str
    section_label: str | None = None
    zone: str = "BODY"


def _page_for_offset(char_pos: int, pages: list[PageSpan]) -> int | None:
    for p in pages:
        if p.char_start <= char_pos <= p.char_end:
            return p.number
    return pages[-1].number if pages else None


def _split_sentences_with_offsets(para_text: str, base_offset: int) -> list[tuple[int, int, str]]:
    """Split paragraph text into sentences while protecting abbreviations."""
    results: list[tuple[int, int, str]] = []
    start = 0
    for match in _SENT_END_RE.finditer(para_text):
        punct_end = match.end(1)
        # Check word immediately preceding punctuation
        prefix = para_text[start:match.start(1)].rstrip()
        last_word = prefix.split()[-1].lower().strip("\"'()[]") if prefix.split() else ""
        if match.group(1) == "." and (last_word in _ABBREVS or (len(last_word) == 1 and last_word.isalpha())):
            continue
        seg = para_text[start:punct_end].strip()
        if seg:
            lead_trim = len(para_text[start:punct_end]) - len(para_text[start:punct_end].lstrip())
            trail_trim = len(para_text[start:punct_end]) - len(para_text[start:punct_end].rstrip())
            cs = base_offset + start + lead_trim
            ce = base_offset + punct_end - trail_trim
            results.append((cs, ce, seg))
        start = match.end()

    tail = para_text[start:].strip()
    if tail:
        lead_trim = len(para_text[start:]) - len(para_text[start:].lstrip())
        trail_trim = len(para_text[start:]) - len(para_text[start:].rstrip())
        cs = base_offset + start + lead_trim
        ce = base_offset + len(para_text) - trail_trim
        results.append((cs, ce, tail))

    return results


def segment_document(
    original_text: str,
    pages: list[PageSpan],
    tokens: list[TokenSpan],
) -> list[SegmentSpan]:
    """Segment original_text into paragraphs and sentences aligned to tokens and pages."""
    if not original_text.strip():
        return []

    token_starts = [t.char_start for t in tokens]
    segments: list[SegmentSpan] = []

    para_boundaries: list[tuple[int, int]] = []
    last = 0
    for m in _PARA_SPLIT_RE.finditer(original_text):
        if m.start() > last:
            para_boundaries.append((last, m.start()))
        last = m.end()
    if last < len(original_text):
        para_boundaries.append((last, len(original_text)))

    sent_seq = 0
    for para_idx, (p_start, p_end) in enumerate(para_boundaries, start=1):
        para_raw = original_text[p_start:p_end]
        if not para_raw.strip():
            continue
        sentences = _split_sentences_with_offsets(para_raw, p_start)
        if not sentences:
            sentences = [(p_start, p_end, para_raw.strip())]

        for cs, ce, sent_orig in sentences:
            sent_seq += 1
            t_start = bisect.bisect_left(token_starts, cs)
            t_end = bisect.bisect_left(token_starts, ce)
            # Ensure token_end covers any token whose char_start < ce
            norm_slice = " ".join(tokens[i].norm for i in range(t_start, t_end))
            page_num = _page_for_offset(cs, pages)
            segments.append(
                SegmentSpan(
                    page_number=page_num,
                    paragraph_number=para_idx,
                    sentence_number=sent_seq,
                    char_start=cs,
                    char_end=ce,
                    token_start=t_start,
                    token_end=t_end,
                    original_text=sent_orig,
                    normalized_text=norm_slice,
                )
            )

    return segments
