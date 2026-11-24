"""Layer 2: Near-exact matching via 3-gram seeds, diagonal clustering, and conservative SequenceMatcher."""

from __future__ import annotations

import difflib
from collections import defaultdict

from app.engine.exact import RawMatch
from app.engine.hashing import hash_ngram

SEED_K = 3
MAX_GAP = 4


def find_near_exact_matches(
    sub_tokens: list[str],
    src_tokens: list[str],
    source_document_id: str,
    exact_matches: list[RawMatch],
    *,
    min_match_words: int = 8,
) -> list[RawMatch]:
    """Detect lightly edited / substituted passages using 3-gram seeds and conservative alignment."""
    if len(sub_tokens) < min_match_words or len(src_tokens) < SEED_K:
        return []

    exact_covered: set[int] = set()
    for em in exact_matches:
        exact_covered.update(range(em.sub_token_start, em.sub_token_end))

    src_seeds: dict[int, list[int]] = defaultdict(list)
    for j in range(len(src_tokens) - SEED_K + 1):
        src_seeds[hash_ngram(src_tokens[j : j + SEED_K])].append(j)

    seeds: list[tuple[int, int]] = []
    for i in range(len(sub_tokens) - SEED_K + 1):
        hits = src_seeds.get(hash_ngram(sub_tokens[i : i + SEED_K]))
        if not hits:
            continue
        for j in hits:
            if sub_tokens[i : i + SEED_K] == src_tokens[j : j + SEED_K]:
                seeds.append((i, j))

    if not seeds:
        return []

    # Sort seeds by diagonal (i - j) then submission position i
    seeds.sort(key=lambda s: (s[0] - s[1], s[0]))

    # Cluster seeds along close diagonals and small gaps
    clusters: list[list[tuple[int, int]]] = []
    for i, j in seeds:
        placed = False
        for cl in reversed(clusters):
            last_i, last_j = cl[-1]
            diag_diff = abs((i - j) - (last_i - last_j))
            gap_sub = i - (last_i + SEED_K)
            gap_src = j - (last_j + SEED_K)
            if diag_diff <= MAX_GAP and -SEED_K <= gap_sub <= MAX_GAP + 2 and -SEED_K <= gap_src <= MAX_GAP + 2:
                cl.append((i, j))
                placed = True
                break
        if not placed:
            clusters.append([(i, j)])

    results: list[RawMatch] = []
    for cl in clusters:
        sub_s = min(p[0] for p in cl)
        sub_e = max(p[0] for p in cl) + SEED_K
        src_s = min(p[1] for p in cl)
        src_e = max(p[1] for p in cl) + SEED_K

        region_len = sub_e - sub_s
        if region_len < min_match_words:
            continue

        # Seed density check on submission side
        seed_covered_tokens: set[int] = set()
        for si, _ in cl:
            seed_covered_tokens.update(range(si, si + SEED_K))
        density = len(seed_covered_tokens) / max(1, region_len)
        if density < 0.45:
            continue

        # Skip if completely covered by exact matches
        region_set = set(range(sub_s, sub_e))
        if region_set.issubset(exact_covered):
            continue

        # Conservative alignment: ONLY 'equal' blocks are counted as matched words
        sm = difflib.SequenceMatcher(
            None,
            sub_tokens[sub_s:sub_e],
            src_tokens[src_s:src_e],
            autojunk=False,
        )
        equal_indices: set[int] = set()
        for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
            if tag == "equal":
                equal_indices.update(range(sub_s + i1, sub_s + i2))

        # Remove tokens already claimed by exact matches for this source
        new_equal = equal_indices - exact_covered
        if len(new_equal) < max(4, min_match_words // 2):
            continue
        if len(equal_indices) < max(4, min_match_words - 2):
            continue

        results.append(
            RawMatch(
                source_document_id=source_document_id,
                layer="NEAR_EXACT",
                sub_token_start=sub_s,
                sub_token_end=sub_e,
                src_token_start=src_s,
                src_token_end=src_e,
                matched_words=len(equal_indices),
                score=round(sm.ratio(), 4),
                counted_token_indices=equal_indices,
            )
        )

    # Deduplicate overlapping near-exact regions per source
    results.sort(key=lambda m: (-m.matched_words, m.sub_token_start))
    kept: list[RawMatch] = []
    occupied: set[int] = set()
    for m in results:
        span_set = set(range(m.sub_token_start, m.sub_token_end))
        if len(span_set & occupied) < len(span_set) * 0.5:
            kept.append(m)
            occupied.update(span_set)

    kept.sort(key=lambda m: m.sub_token_start)
    return kept
