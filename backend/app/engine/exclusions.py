"""Exclusion masks: bibliography, TOC, cover, direct quotes, in-text citations, and common phrases."""

from __future__ import annotations

import bisect
import re
from functools import lru_cache
from pathlib import Path

from app.config import BASE_DIR
from app.models import Segment
from app.schemas import CheckSettingsSchema

_QUOTE_RE = re.compile(r'(["“«])(.*?)(["”»])', re.DOTALL)
_PAREN_CIT_RE = re.compile(
    r"\(([A-Z][\w'’\-]+(?:\s+(?:et al\.|dkk\.?|&|dan)\s*[A-Z]?[\w'’\-]*)?,?\s*\d{4}[a-z]?"
    r"(?:\s*[:,]\s*(?:hlm\.|p\.|pp\.)?\s*\d+(?:-\d+)?)?(?:;\s*[^)]+)?)\)"
)
_BRACKET_CIT_RE = re.compile(r"\[\d+(?:\s*[,–\-]\s*\d+)*\]")


@lru_cache(maxsize=1)
def load_common_phrases() -> list[list[str]]:
    phrases: list[list[str]] = []
    for fname in ("common_phrases_id.txt", "common_phrases_en.txt"):
        path = Path(BASE_DIR) / "data" / fname
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                words = [w.strip().casefold() for w in line.strip().split() if w.strip()]
                if len(words) >= 3:
                    phrases.append(words)
    return phrases


def build_exclusion_mask(
    original_text: str,
    tokens: list[list],  # [[norm, char_start, char_end], ...]
    segments: list[Segment],
    settings: CheckSettingsSchema,
) -> list[str | None]:
    """Return a list of length len(tokens) mapping each token index to an exclusion reason or None."""
    n_tok = len(tokens)
    mask: list[str | None] = [None] * n_tok
    if n_tok == 0:
        return mask

    # 1. Zone-based exclusions (BIBLIOGRAPHY, TOC, COVER)
    for seg in segments:
        reason: str | None = None
        if seg.zone == "BIBLIOGRAPHY" and settings.exclude_bibliography:
            reason = "BIBLIOGRAPHY"
        elif seg.zone == "TOC" and settings.exclude_toc:
            reason = "TOC"
        elif seg.zone == "COVER" and settings.exclude_cover:
            reason = "COVER"
        if reason:
            for ti in range(max(0, seg.token_start), min(n_tok, seg.token_end)):
                if mask[ti] is None:
                    mask[ti] = reason

    token_starts = [t[1] for t in tokens]
    token_ends = [t[2] for t in tokens]

    def _mark_char_span(cs: int, ce: int, reason_label: str, min_words: int = 1) -> None:
        t_start = bisect.bisect_left(token_starts, cs)
        # Include any token that overlaps [cs, ce)
        if t_start > 0 and token_ends[t_start - 1] > cs:
            t_start -= 1
        t_end = bisect.bisect_left(token_starts, ce)
        if (t_end - t_start) < min_words:
            return
        for ti in range(max(0, t_start), min(n_tok, t_end)):
            if mask[ti] is None:
                mask[ti] = reason_label

    # 2. Direct quotes (>= 3 words inside quotation marks)
    if settings.exclude_quotes:
        for m in _QUOTE_RE.finditer(original_text):
            open_q, body, close_q = m.group(1), m.group(2), m.group(3)
            # Pair straight quotes only if reasonable length (< 1500 chars)
            if len(body) > 1500:
                continue
            if open_q == "“" and close_q != "”":
                continue
            if open_q == "«" and close_q != "»":
                continue
            _mark_char_span(m.start(), m.end(), "QUOTE", min_words=3)

    # 3. In-text citations
    if settings.exclude_citations:
        for m in _PAREN_CIT_RE.finditer(original_text):
            _mark_char_span(m.start(), m.end(), "CITATION", min_words=1)
        for m in _BRACKET_CIT_RE.finditer(original_text):
            _mark_char_span(m.start(), m.end(), "CITATION", min_words=1)

    # 4. Common academic phrases
    if settings.exclude_common_phrases:
        norm_tokens = [t[0] for t in tokens]
        phrases = load_common_phrases()
        by_len: dict[int, set[tuple[str, ...]]] = {}
        for p in phrases:
            by_len.setdefault(len(p), set()).add(tuple(p))
        for plen, pset in by_len.items():
            if n_tok < plen:
                continue
            for i in range(n_tok - plen + 1):
                if tuple(norm_tokens[i : i + plen]) in pset:
                    for ti in range(i, i + plen):
                        if mask[ti] is None:
                            mask[ti] = "COMMON_PHRASE"

    return mask
