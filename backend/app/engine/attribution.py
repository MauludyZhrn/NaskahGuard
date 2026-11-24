"""Exclusive source attribution so overlapping sources never double-count tokens."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.engine.exact import RawMatch

LAYER_PRIORITY = {
    "EXACT": 0,
    "NEAR_EXACT": 1,
    "LEXICAL": 2,
    "SEMANTIC": 3,
}


@dataclass
class SourceAttributionSummary:
    source_document_id: str
    rank: int
    matched_words_exclusive: int
    matched_words_total: int
    contribution_pct: float
    layers: dict[str, int]


def compute_exclusive_attribution(
    verified_matches: list[RawMatch],
    eligible_indices: set[int],
    token_mask: list[str | None],
) -> tuple[list[SourceAttributionSummary], dict[int, str], dict[str, int]]:
    """Assign each eligible matched token exclusively to the highest-priority source match.

    Returns:
      - ordered list of SourceAttributionSummary
      - mapping token_index -> owning layer ("EXACT" | "NEAR_EXACT" | "LEXICAL")
      - per-match metadata dict is mutated on RawMatch? No, caller inspects counted sets.
    """
    eligible_count = len(eligible_indices)
    if eligible_count == 0 or not verified_matches:
        return [], {}, {"EXACT": 0, "NEAR_EXACT": 0, "LEXICAL": 0}

    # Sort deterministically: EXACT first, then NEAR_EXACT, then LEXICAL, then length desc, then source ID
    ordered = sorted(
        verified_matches,
        key=lambda m: (
            LAYER_PRIORITY.get(m.layer, 99),
            -len(m.counted_token_indices & eligible_indices),
            m.source_document_id,
            m.sub_token_start,
        ),
    )

    claimed_tokens: dict[int, str] = {}
    exclusive_by_src: dict[str, set[int]] = defaultdict(set)
    total_by_src: dict[str, set[int]] = defaultdict(set)
    layers_by_src: dict[str, dict[str, int]] = defaultdict(lambda: {"EXACT": 0, "NEAR_EXACT": 0, "LEXICAL": 0})
    layer_token_counts = {"EXACT": 0, "NEAR_EXACT": 0, "LEXICAL": 0}

    for m in ordered:
        eligible_match_tokens = m.counted_token_indices & eligible_indices
        if not eligible_match_tokens:
            continue
        total_by_src[m.source_document_id].update(eligible_match_tokens)
        newly_claimed = {t for t in eligible_match_tokens if t not in claimed_tokens}
        if newly_claimed:
            for t in newly_claimed:
                claimed_tokens[t] = m.layer
            exclusive_by_src[m.source_document_id].update(newly_claimed)
            layers_by_src[m.source_document_id][m.layer] = (
                layers_by_src[m.source_document_id].get(m.layer, 0) + len(newly_claimed)
            )
            layer_token_counts[m.layer] = layer_token_counts.get(m.layer, 0) + len(newly_claimed)

    all_sources = set(total_by_src.keys())
    summaries: list[SourceAttributionSummary] = []
    for src_id in all_sources:
        excl_count = len(exclusive_by_src.get(src_id, set()))
        tot_count = len(total_by_src.get(src_id, set()))
        contrib = round((excl_count / eligible_count) * 100.0, 2)
        summaries.append(
            SourceAttributionSummary(
                source_document_id=src_id,
                rank=0,
                matched_words_exclusive=excl_count,
                matched_words_total=tot_count,
                contribution_pct=contrib,
                layers=dict(layers_by_src.get(src_id, {})),
            )
        )

    summaries.sort(key=lambda s: (-s.matched_words_exclusive, -s.matched_words_total, s.source_document_id))
    for idx, item in enumerate(summaries, start=1):
        item.rank = idx

    # Adjust rounding residue on the top contributor so sum(contribution_pct) == Adjusted SI exactly
    if summaries:
        exact_adjusted_si = round((len(claimed_tokens) / eligible_count) * 100.0, 2)
        current_sum = round(sum(s.contribution_pct for s in summaries), 2)
        diff = round(exact_adjusted_si - current_sum, 2)
        if abs(diff) > 0 and abs(diff) <= 0.2:
            summaries[0].contribution_pct = round(max(0.0, summaries[0].contribution_pct + diff), 2)

    return summaries, claimed_tokens, layer_token_counts
