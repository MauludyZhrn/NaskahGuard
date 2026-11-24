"""Layer 1: Exact n-gram word matching with maximal forward extension."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.engine.hashing import hash_ngram


@dataclass
class RawMatch:
    source_document_id: str
    layer: str  # EXACT | NEAR_EXACT | LEXICAL | SEMANTIC
    sub_token_start: int
    sub_token_end: int
    src_token_start: int
    src_token_end: int
    matched_words: int
    score: float
    counted_token_indices: set[int] = field(default_factory=set)


def find_exact_matches(
    sub_tokens: list[str],
    src_tokens: list[str],
    source_document_id: str,
    *,
    min_match_words: int = 8,
) -> list[RawMatch]:
    """Find maximal verbatim word spans >= min_match_words between sub_tokens and src_tokens."""
    n = max(3, min_match_words)
    if len(sub_tokens) < n or len(src_tokens) < n:
        return []

    src_index: dict[int, list[int]] = defaultdict(list)
    for j in range(len(src_tokens) - n + 1):
        src_index[hash_ngram(src_tokens[j : j + n])].append(j)

    candidates: list[RawMatch] = []
    for i in range(len(sub_tokens) - n + 1):
        h = hash_ngram(sub_tokens[i : i + n])
        positions = src_index.get(h)
        if not positions:
            continue
        for j in positions:
            # Skip non-maximal continuations along the same diagonal
            if i > 0 and j > 0 and sub_tokens[i - 1] == src_tokens[j - 1]:
                continue
            # Collision check on initial n-gram
            if sub_tokens[i : i + n] != src_tokens[j : j + n]:
                continue

            length = n
            max_len = min(len(sub_tokens) - i, len(src_tokens) - j)
            while length < max_len and sub_tokens[i + length] == src_tokens[j + length]:
                length += 1

            candidates.append(
                RawMatch(
                    source_document_id=source_document_id,
                    layer="EXACT",
                    sub_token_start=i,
                    sub_token_end=i + length,
                    src_token_start=j,
                    src_token_end=j + length,
                    matched_words=length,
                    score=1.0,
                    counted_token_indices=set(range(i, i + length)),
                )
            )

    # Deduplicate per source: keep longest span per overlapping submission region
    candidates.sort(key=lambda m: (-m.matched_words, m.sub_token_start))
    kept: list[RawMatch] = []
    occupied: set[int] = set()
    for m in candidates:
        span_set = set(range(m.sub_token_start, m.sub_token_end))
        overlap = len(span_set & occupied)
        if overlap == 0 or overlap < len(span_set) * 0.5:
            kept.append(m)
            occupied.update(span_set)

    kept.sort(key=lambda m: m.sub_token_start)
    return kept
