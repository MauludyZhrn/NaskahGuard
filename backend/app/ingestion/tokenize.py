"""Unicode word tokenizer preserving exact character offsets into original text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.normalize import normalize_token

WORD_TOKEN_RE = re.compile(r"\w+(?:[-'’]\w+)*", re.UNICODE)


@dataclass(frozen=True)
class TokenSpan:
    index: int
    original: str
    norm: str
    char_start: int
    char_end: int


def tokenize_with_offsets(original_text: str) -> list[TokenSpan]:
    """Tokenize original_text without mutating it; offsets always point into original_text."""
    spans: list[TokenSpan] = []
    idx = 0
    for match in WORD_TOKEN_RE.finditer(original_text):
        raw_tok = match.group(0)
        norm_tok = normalize_token(raw_tok)
        if not norm_tok:
            continue
        spans.append(
            TokenSpan(
                index=idx,
                original=raw_tok,
                norm=norm_tok,
                char_start=match.start(),
                char_end=match.end(),
            )
        )
        idx += 1
    return spans
