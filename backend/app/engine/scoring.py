"""Similarity Index calculation, coverage honesty, and operational categorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.attribution import SourceAttributionSummary, compute_exclusive_attribution
from app.engine.exact import RawMatch
from app.schemas import CheckSettingsSchema


@dataclass
class ScoringResult:
    metrics: dict[str, Any]
    coverage: dict[str, Any]
    source_summaries: list[SourceAttributionSummary]
    counted_match_flags: list[tuple[bool, str | None]]  # (counted, dominant_excluded_reason)


def classify_operational_level(
    similarity_index: float,
    threshold_low: float,
    threshold_high: float,
) -> dict[str, Any]:
    if similarity_index < threshold_low:
        level = "Rendah"
    elif similarity_index < threshold_high:
        level = "Sedang"
    else:
        level = "Tinggi"
    return {
        "level": level,
        "threshold_low": threshold_low,
        "threshold_high": threshold_high,
        "disclaimer": (
            "Kategori ini merupakan kategori operasional aplikasi yang dapat dikonfigurasi, "
            "bukan standar resmi institusi atau universitas, dan bukan keputusan otomatis pelanggaran plagiasi."
        ),
    }


def evaluate_coverage(
    *,
    full_text_sources_compared: int,
    metadata_only_sources: int,
    access_denied_sources: int,
    fetch_failed_sources: int,
    matched_eligible_words: int,
    external_enabled: bool,
) -> dict[str, Any]:
    if full_text_sources_compared < 10:
        level = "Sangat terbatas"
    elif full_text_sources_compared < 100:
        level = "Terbatas"
    elif full_text_sources_compared < 1000:
        level = "Sedang"
    else:
        level = "Luas"

    notes: list[str] = []
    if full_text_sources_compared == 0:
        notes.append(
            "Tidak ada dokumen sumber full-text dalam cakupan pemeriksaan. "
            "Hasil 0% tidak berarti dokumen bebas plagiasi."
        )
    elif matched_eligible_words == 0:
        notes.append(
            "Tidak ditemukan kecocokan dalam sumber yang diperiksa — ini tidak berarti dokumen bebas plagiasi."
        )
    if metadata_only_sources > 0:
        notes.append(
            f"{metadata_only_sources} sumber eksternal hanya menyediakan metadata/abstrak (METADATA_ONLY) "
            "dan tidak dihitung sebagai sumber full-text yang dibandingkan."
        )
    if not external_enabled:
        notes.append("Pemeriksaan hanya mencakup korpus lokal (pencarian sumber eksternal tidak diaktifkan).")

    return {
        "level": level,
        "full_text_sources_compared": full_text_sources_compared,
        "metadata_only_sources": metadata_only_sources,
        "access_denied_sources": access_denied_sources,
        "fetch_failed_sources": fetch_failed_sources,
        "external_sources_enabled": external_enabled,
        "notes": notes,
        "statement": (
            f"Cakupan pemeriksaan: {level} ({full_text_sources_compared} dokumen full-text dibandingkan"
            + (f", {metadata_only_sources} metadata-only" if metadata_only_sources else "")
            + ")."
        ),
    }


def compute_scores(
    *,
    all_matches: list[RawMatch],
    token_mask: list[str | None],
    settings: CheckSettingsSchema,
    threshold_low: float,
    threshold_high: float,
    full_text_sources_compared: int,
    metadata_only_sources: int = 0,
    access_denied_sources: int = 0,
    fetch_failed_sources: int = 0,
    semantic_status_msg: str = "",
) -> ScoringResult:
    total_words = len(token_mask)
    eligible_indices = {i for i, reason in enumerate(token_mask) if reason is None}
    eligible_words = len(eligible_indices)

    counted_layers = {"EXACT", "NEAR_EXACT"}
    if settings.include_lexical_in_index:
        counted_layers.add("LEXICAL")

    verified_matches = [m for m in all_matches if m.layer in counted_layers]
    lexical_matches = [m for m in all_matches if m.layer == "LEXICAL"]
    semantic_matches = [m for m in all_matches if m.layer == "SEMANTIC"]

    # Raw SI (no exclusion mask, all tokens of verified matches)
    raw_matched_tokens: set[int] = set()
    for m in verified_matches:
        raw_matched_tokens.update(m.counted_token_indices)
    raw_si = round((len(raw_matched_tokens) / total_words) * 100.0, 2) if total_words > 0 else 0.0

    # Determine per-match counted flag and exclusion reason
    match_flags: list[tuple[bool, str | None]] = []
    for m in all_matches:
        if m.layer == "SEMANTIC":
            match_flags.append((False, None))
            continue
        if m.layer == "LEXICAL" and not settings.include_lexical_in_index:
            match_flags.append((False, None))
            continue
        toks = m.counted_token_indices
        if not toks:
            match_flags.append((False, None))
            continue
        elig_toks = toks & eligible_indices
        if not elig_toks:
            # Find dominant exclusion reason
            reasons = [token_mask[t] for t in toks if t < len(token_mask) and token_mask[t] is not None]
            dom = max(set(reasons), key=reasons.count) if reasons else "EXCLUDED"
            match_flags.append((False, dom))
        else:
            match_flags.append((True, None))

    source_summaries, claimed_tokens, layer_counts = compute_exclusive_attribution(
        verified_matches, eligible_indices, token_mask
    )

    matched_eligible_words = len(claimed_tokens)
    unrounded_raw_si = (len(raw_matched_tokens) / total_words) * 100.0 if total_words > 0 else 0.0
    unrounded_adj_si = (matched_eligible_words / eligible_words) * 100.0 if eligible_words > 0 else 0.0
    unrounded_exact_pct = (layer_counts.get("EXACT", 0) / eligible_words) * 100.0 if eligible_words > 0 else 0.0
    unrounded_near_pct = (layer_counts.get("NEAR_EXACT", 0) / eligible_words) * 100.0 if eligible_words > 0 else 0.0

    adjusted_si = round(unrounded_adj_si, 2)
    exact_pct = round(unrounded_exact_pct, 2)
    near_exact_pct = round(unrounded_near_pct, 2)

    # Detect display rounding residue (e.g. 408/5973 -> 6.8307% = 6.83%, while 290/5973=4.86% + 118/5973=1.98% = 6.84%)
    rounded_layer_sum = round(exact_pct + near_exact_pct + (round((layer_counts.get("LEXICAL", 0) / eligible_words) * 100.0, 2) if (settings.include_lexical_in_index and eligible_words > 0) else 0.0), 2)
    rounding_gap = round(rounded_layer_sum - adjusted_si, 2)
    if abs(rounding_gap) > 0:
        rounding_note = (
            f"Nilai presisi sebelum pembulatan: Exact {unrounded_exact_pct:.4f}% ({layer_counts.get('EXACT', 0)} kata) "
            f"+ Near-Exact {unrounded_near_pct:.4f}% ({layer_counts.get('NEAR_EXACT', 0)} kata) "
            f"= {unrounded_adj_si:.4f}% ({matched_eligible_words}/{eligible_words} kata unik, tanpa double-counting). "
            f"Selisih {rounding_gap:+.2f}% antara jumlah angka terbulat ({rounded_layer_sum:.2f}%) dan Adjusted SI ({adjusted_si:.2f}%) "
            f"murni berasal dari pembulatan dua desimal masing-masing komponen."
        )
    else:
        rounding_note = (
            f"Nilai presisi sebelum pembulatan: {unrounded_adj_si:.4f}% ({matched_eligible_words}/{eligible_words} kata unik, "
            f"tanpa penghitungan ganda antar lapisan maupun sumber)."
        )

    # Lexical tokens outside claimed SI
    lexical_tokens: set[int] = set()
    for lm in lexical_matches:
        lexical_tokens.update(lm.counted_token_indices & eligible_indices)
    lexical_outside = lexical_tokens - set(claimed_tokens.keys())
    lexical_pct = round((len(lexical_outside) / eligible_words) * 100.0, 2) if eligible_words > 0 else 0.0
    if settings.include_lexical_in_index:
        lexical_pct = round((layer_counts.get("LEXICAL", 0) / eligible_words) * 100.0, 2) if eligible_words > 0 else 0.0

    semantic_token_set: set[int] = set()
    for sm in semantic_matches:
        semantic_token_set.update(range(sm.sub_token_start, sm.sub_token_end))

    excluded_words_count = total_words - eligible_words
    exclusion_breakdown: dict[str, int] = {}
    for r in token_mask:
        if r is not None:
            exclusion_breakdown[r] = exclusion_breakdown.get(r, 0) + 1

    op_category = classify_operational_level(adjusted_si, threshold_low, threshold_high)
    coverage = evaluate_coverage(
        full_text_sources_compared=full_text_sources_compared,
        metadata_only_sources=metadata_only_sources,
        access_denied_sources=access_denied_sources,
        fetch_failed_sources=fetch_failed_sources,
        matched_eligible_words=matched_eligible_words,
        external_enabled=settings.use_external_sources,
    )

    raw_diff = round(raw_si - adjusted_si, 2)
    if abs(raw_diff) < 0.01:
        diff_reason = (
            "Raw Similarity dan Adjusted Similarity bernilai sama karena tidak ada kata cocok "
            "yang berada di zona pengecualian atau tidak ada kata yang dikecualikan."
        )
    else:
        excl_parts = [f"{k}: {v} kata" for k, v in sorted(exclusion_breakdown.items())]
        excl_summary = ", ".join(excl_parts) if excl_parts else f"{excluded_words_count} kata dikecualikan"
        diff_reason = (
            f"Raw Similarity menghitung seluruh {len(raw_matched_tokens)} kata cocok dari {total_words} total kata "
            f"({raw_si:.2f}%), sedangkan Adjusted Similarity menghitung {matched_eligible_words} kata cocok unik "
            f"dari {eligible_words} kata eligible setelah mengeluarkan {excluded_words_count} kata ({excl_summary}) "
            f"sehingga menghasilkan {adjusted_si:.2f}% (selisih {raw_diff:+.2f} poin persentase)."
        )

    metrics = {
        "similarity_index": adjusted_si,
        "raw_similarity": raw_si,
        "adjusted_similarity": adjusted_si,
        "exact_match_pct": exact_pct,
        "near_exact_match_pct": near_exact_pct,
        "lexical_match_pct": lexical_pct,
        "exact_match_words": layer_counts.get("EXACT", 0),
        "near_exact_match_words": layer_counts.get("NEAR_EXACT", 0),
        "include_lexical_in_index": settings.include_lexical_in_index,
        "total_words": total_words,
        "eligible_words": eligible_words,
        "excluded_words": excluded_words_count,
        "exclusion_breakdown": exclusion_breakdown,
        "matched_words": matched_eligible_words,
        "raw_matched_words": len(raw_matched_tokens),
        "unmatched_eligible_words": max(0, eligible_words - matched_eligible_words),
        "sources_found": len(source_summaries),
        "lexical_candidates_count": len(lexical_matches),
        "semantic_candidates_count": len(semantic_matches),
        "semantic_candidate_words": len(semantic_token_set),
        "semantic_status": semantic_status_msg,
        "operational_category": op_category,
        "score_explanation": {
            "formula": "SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%",
            "adjusted_formula": f"{matched_eligible_words} / {eligible_words} × 100% = {adjusted_si:.2f}% (presisi: {unrounded_adj_si:.4f}%)",
            "raw_formula": f"{len(raw_matched_tokens)} / {total_words} × 100% = {raw_si:.2f}% (presisi: {unrounded_raw_si:.4f}%)",
            "raw_similarity": raw_si,
            "adjusted_similarity": adjusted_si,
            "unrounded_raw_similarity": round(unrounded_raw_si, 6),
            "unrounded_adjusted_similarity": round(unrounded_adj_si, 6),
            "unrounded_exact_pct": round(unrounded_exact_pct, 6),
            "unrounded_near_exact_pct": round(unrounded_near_pct, 6),
            "rounding_note": rounding_note,
            "total_words": total_words,
            "eligible_words": eligible_words,
            "unique_matched_words": matched_eligible_words,
            "matched_eligible_words": matched_eligible_words,
            "raw_matched_words": len(raw_matched_tokens),
            "exact_match_words": layer_counts.get("EXACT", 0),
            "exact_words": layer_counts.get("EXACT", 0),
            "exact_match_pct": exact_pct,
            "near_exact_match_words": layer_counts.get("NEAR_EXACT", 0),
            "near_exact_words": layer_counts.get("NEAR_EXACT", 0),
            "near_exact_match_pct": near_exact_pct,
            "lexical_words": layer_counts.get("LEXICAL", 0),
            "excluded_words": excluded_words_count,
            "exclusion_breakdown": exclusion_breakdown,
            "raw_vs_adjusted_difference": raw_diff,
            "raw_vs_adjusted_reason": diff_reason,
            "raw_vs_adjusted_diff_reason": diff_reason,
        },
    }

    return ScoringResult(
        metrics=metrics,
        coverage=coverage,
        source_summaries=source_summaries,
        counted_match_flags=match_flags,
    )
