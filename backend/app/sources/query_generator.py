"""Intelligent Multi-Query Generator (Phase 9).

Features:
- Chapter-balanced round-robin query allocation (every substantive chapter gets coverage)
- Paragraph & sentence-level distinctive phrase extraction
- Corpus-local IDF keyword ranking + Indonesian academic stopword filtering
- English/Arabic technical terminology detection
- In-text DOI lookup (without leaking bibliography prose)
- Strict cross-chapter query deduplication & privacy preservation (only compact phrases/keywords sent)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from app.engine.exclusions import load_common_phrases
from app.models import Segment

PROFILE_LIMITS: dict[str, int] = {
    "QUICK": 8,
    "BALANCED": 24,
    "DEEP": 48,
}

_ID_STOPWORDS = {
    "yang", "dan", "pada", "dari", "untuk", "dengan", "dalam", "adalah", "oleh",
    "sebagai", "tidak", "akan", "atau", "juga", "dapat", "telah", "bahwa", "tersebut",
    "ini", "itu", "serta", "antara", "secara", "lebih", "karena", "sehingga", "namun",
    "berdasarkan", "penelitian", "hasil", "data", "metode", "analisis", "menggunakan",
    "dilakukan", "menunjukkan", "terhadap", "suatu", "setiap", "melalui", "menjadi",
    "hal", "bagian", "bab", "tabel", "gambar", "halaman", "tahun", "indonesia",
}

_EN_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "have",
    "has", "had", "been", "into", "over", "between", "through", "during", "using", "based",
    "study", "results", "method", "methods", "analysis", "paper", "section", "table", "figure",
}

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9\-]{3,}")


@dataclass(frozen=True)
class QueryCandidate:
    query: str
    kind: str
    chapter: str
    score: float
    language: str = "all"
    level: int = 3


def resolve_query_budget(profile: str, max_queries_override: int | None = None) -> int:
    default_limit = PROFILE_LIMITS.get((profile or "BALANCED").upper(), 24)
    if max_queries_override is not None and max_queries_override > 0:
        return min(max_queries_override, 48)
    return default_limit


def _compute_segment_idf(body_segs: list[Segment]) -> dict[str, float]:
    n_docs = max(1, len(body_segs))
    df: Counter[str] = Counter()
    for seg in body_segs:
        words = {w.lower() for w in _WORD_RE.findall(seg.original_text) if len(w) >= 4}
        for w in words:
            if w not in _ID_STOPWORDS and w not in _EN_STOPWORDS and not w.isdigit():
                df[w] += 1
    return {w: math.log((n_docs + 1.0) / (cnt + 0.5)) + 1.0 for w, cnt in df.items()}


def _is_foreign_or_technical_term(w: str) -> bool:
    low = w.lower()
    if low in _ID_STOPWORDS or low in _EN_STOPWORDS:
        return False
    # Technical suffixes / Latin-English-Arabic transliterated academic terms
    if any(low.endswith(suf) for suf in ("tion", "ment", "ness", "ity", "logy", "metry", "isasi", "ifikasi", "isme")):
        return True
    if "-" in low or any(sub in low for sub in ("kh", "sy", "dz", "th", "ph", "ch", "qu")):
        return True
    return len(low) >= 8


def generate_intelligent_queries(
    *,
    title: str | None,
    segments: list[Segment],
    max_queries: int = 24,
    profile: str = "BALANCED",
    search_language: str = "all",
    prioritized_chapters: set[str] | None = None,
) -> list[QueryCandidate]:
    """Generate chapter-distributed, deduplicated, privacy-safe search queries."""
    budget = resolve_query_budget(profile, max_queries)
    common_phrases = load_common_phrases()
    candidates: list[QueryCandidate] = []
    seen_q: set[str] = set()
    seen_shingles: set[str] = set()

    def _add(q: str, kind: str, chapter: str, score: float, level: int, lang: str = "all") -> None:
        cleaned = " ".join(q.split()).strip()
        key = cleaned.lower().strip('"')
        if not cleaned or len(key) < 8 or key in seen_q:
            return
        # Avoid near-duplicate queries across chapters using 4-word shingle signature
        words = [w for w in _WORD_RE.findall(key) if w not in _ID_STOPWORDS and w not in _EN_STOPWORDS]
        if len(words) >= 4:
            sig = " ".join(sorted(words[:5]))
            if sig in seen_shingles and kind != "doi_lookup":
                return
            seen_shingles.add(sig)
        if any(cp in key for cp in common_phrases if len(cp) >= 18):
            return
        seen_q.add(key)
        candidates.append(
            QueryCandidate(
                query=cleaned[:200],
                kind=kind,
                chapter=chapter,
                score=round(score, 3),
                language=lang,
                level=level,
            )
        )

    # Level 1: Explicit in-body DOIs (if any appear in body citations, up to 2)
    body_segs = [s for s in segments if s.zone == "BODY" and len(s.original_text.split()) >= 6]
    found_dois: list[str] = []
    for s in body_segs:
        for m in _DOI_RE.findall(s.original_text):
            d = m.rstrip(".,;)")
            if d not in found_dois:
                found_dois.append(d)
    for d in found_dois[:2]:
        _add(d, "doi_lookup", "Referensi DOI", 3.5, level=1, lang="all")

    # Level 2: Clean document title
    clean_title = (title or "").strip()
    if clean_title and not clean_title.lower().endswith((".pdf", ".docx", ".txt")):
        _add(clean_title, "title", "Judul", 3.2, level=2, lang=search_language)

    if not body_segs:
        return candidates[:budget]

    idf_map = _compute_segment_idf(body_segs)

    # Group body segments by substantive chapter/section label
    by_chapter: dict[str, list[Segment]] = {}
    for s in body_segs:
        ch = (s.section_label or "Bagian Utama").strip() or "Bagian Utama"
        by_chapter.setdefault(ch, []).append(s)

    chapter_buckets: dict[str, list[QueryCandidate]] = {ch: [] for ch in by_chapter}

    for ch, segs in by_chapter.items():
        prio_boost = 0.35 if (prioritized_chapters and ch in prioritized_chapters) else 0.0
        scored_segs: list[tuple[float, Segment, list[str]]] = []
        for s in segs:
            words = _WORD_RE.findall(s.original_text)
            if len(words) < 7:
                continue
            content_w = [w.lower() for w in words if w.lower() not in _ID_STOPWORDS and w.lower() not in _EN_STOPWORDS and len(w) >= 4]
            if len(content_w) < 4:
                continue
            avg_idf = sum(idf_map.get(w, 1.0) for w in content_w) / len(content_w)
            tech_bonus = 0.15 * sum(1 for w in content_w if _is_foreign_or_technical_term(w))
            seg_score = avg_idf + tech_bonus + prio_boost
            scored_segs.append((seg_score, s, words))

        scored_segs.sort(key=lambda x: x[0], reverse=True)

        local_before = len(candidates)
        for idx, (sc, seg, words) in enumerate(scored_segs[:8]):
            # 1. Exact distinctive 8-11 word phrase (quoted for precision)
            mid = max(0, min(len(words) - 9, len(words) // 4))
            phrase_words = words[mid : mid + 9]
            if len(phrase_words) >= 6:
                _add(f'"{" ".join(phrase_words)}"', "exact_phrase", ch, sc + 0.6, level=3, lang=search_language)

            # 2. Unquoted n-gram window (high recall on academic APIs)
            ngram_words = words[:10]
            if len(ngram_words) >= 6:
                _add(" ".join(ngram_words), "ngram_phrase", ch, sc + 0.35, level=3, lang=search_language)

            # 3. Top IDF distinctive keyword bundle
            ranked_kw = sorted(
                {w.lower() for w in words if w.lower() not in _ID_STOPWORDS and w.lower() not in _EN_STOPWORDS and len(w) >= 4},
                key=lambda w: idf_map.get(w, 1.0),
                reverse=True,
            )
            if len(ranked_kw) >= 4:
                _add(" ".join(ranked_kw[:6]), "distinctive_keywords", ch, sc + 0.2, level=4, lang=search_language)

            # 4. Technical / English / Arabic academic terminology query (for BALANCED / DEEP)
            tech_terms = [w for w in words if _is_foreign_or_technical_term(w)]
            if len(tech_terms) >= 3 and idx < 3:
                dedup_tech = list(dict.fromkeys(w.lower() for w in tech_terms))[:6]
                _add(" ".join(dedup_tech), "academic_terminology", ch, sc + 0.15, level=4, lang="en" if search_language == "all" else search_language)

            # 5. Paraphrase-resilient clause variation & language-aware query
            if len(ranked_kw) >= 5 and idx < 2:
                _add(" ".join(ranked_kw[1:6]), "similar_variation", ch, sc, level=5, lang=search_language)
                _add(" ".join(ranked_kw[:4] + [ch.lower()]), "language_aware", ch, sc - 0.05, level=5, lang=search_language)

        chapter_buckets[ch] = candidates[local_before:]

    # Assemble final list: keep Level 1-2 header queries first, then round-robin across substantive chapters!
    header_qs = [c for c in candidates if c.level <= 2]
    selected: list[QueryCandidate] = list(header_qs)
    selected_set = {c.query for c in selected}

    chapter_names = list(chapter_buckets.keys())
    round_idx = 0
    while len(selected) < budget and chapter_names:
        progressed = False
        for ch in chapter_names:
            bucket = chapter_buckets[ch]
            if round_idx < len(bucket):
                cand = bucket[round_idx]
                if cand.query not in selected_set:
                    selected.append(cand)
                    selected_set.add(cand.query)
                    progressed = True
                    if len(selected) >= budget:
                        break
        if not progressed:
            break
        round_idx += 1

    return selected[:budget]
