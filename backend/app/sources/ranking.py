"""Search Quality Ranking: classifies candidate relevance before spending crawl/download budget.

IMPORTANT: Relevance score is strictly for candidate prioritization and is NEVER used as a plagiarism score.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.sources.base import SourceRecord

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class RankedCandidate:
    record: SourceRecord
    relevance_score: float
    relevance_label: str  # HIGHLY_RELEVANT | RELEVANT | WEAK_CANDIDATE | UNRELATED
    matched_query: str


def _word_set(text: str | None) -> set[str]:
    if not text:
        return set()
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) >= 4}


def score_candidate_relevance(
    record: SourceRecord,
    *,
    doc_title: str | None,
    doc_keywords: set[str],
    matched_query: str,
) -> RankedCandidate:
    """Rank search candidate relevance using title, abstract, keyword overlap, DOI, and OA availability."""
    cand_title_words = _word_set(record.title)
    cand_abs_words = _word_set(record.abstract)
    cand_all = cand_title_words | cand_abs_words
    query_words = _word_set(matched_query)
    doc_title_words = _word_set(doc_title)

    # 1. Query keyword overlap
    q_overlap = len(query_words & cand_all) / max(1, len(query_words)) if query_words else 0.0
    # 2. Document keyword overlap
    d_overlap = len(doc_keywords & cand_all) / max(1, min(len(doc_keywords), 15)) if doc_keywords else 0.0
    # 3. Title overlap
    t_overlap = len(doc_title_words & cand_title_words) / max(1, len(doc_title_words)) if doc_title_words else 0.0
    # 4. Exact phrase substring bonus
    clean_q = matched_query.strip().strip('"').lower()
    haystack = f"{record.title or ''} {record.abstract or ''}".lower()
    exact_bonus = 0.25 if (len(clean_q) >= 12 and clean_q in haystack) else 0.0
    # 5. Academic identity & OA availability bonus
    meta_bonus = 0.0
    if record.doi:
        meta_bonus += 0.08
    if record.oa_pdf_url or record.access_status == "FULL_TEXT_AVAILABLE":
        meta_bonus += 0.10
    if record.canonical_url:
        meta_bonus += 0.04

    score = min(1.0, round(0.38 * q_overlap + 0.27 * d_overlap + 0.20 * t_overlap + exact_bonus + meta_bonus, 4))

    if score >= 0.55:
        label = "HIGHLY_RELEVANT"
    elif score >= 0.30:
        label = "RELEVANT"
    elif score >= 0.14:
        label = "WEAK_CANDIDATE"
    else:
        label = "UNRELATED"

    return RankedCandidate(
        record=record,
        relevance_score=score,
        relevance_label=label,
        matched_query=matched_query,
    )
