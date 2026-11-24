"""Layer 3: Lexical similarity via BM25 document selection and TF-IDF char_wb (3,5) cosine."""

from __future__ import annotations

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session

from app.engine.exact import RawMatch
from app.models import Segment

LEXICAL_THRESHOLD = 0.70
MIN_SENTENCE_WORDS = 6


def find_bm25_candidates(
    db: Session,
    sub_norm_tokens: list[str],
    allowed_doc_ids: set[str],
    *,
    exclude_doc_ids: set[str] | None = None,
    top_k: int = 5,
) -> list[str]:
    """Select top-k corpus documents via BM25 over body segment tokens."""
    pool_ids = allowed_doc_ids - (exclude_doc_ids or set())
    if not pool_ids or not sub_norm_tokens:
        return []

    rows = (
        db.query(Segment.document_id, Segment.normalized_text)
        .filter(Segment.document_id.in_(list(pool_ids)))
        .all()
    )
    doc_tokens: dict[str, list[str]] = {}
    for doc_id, norm_txt in rows:
        toks = norm_txt.split()
        if toks:
            doc_tokens.setdefault(doc_id, []).extend(toks)

    if not doc_tokens:
        return []

    ids = list(doc_tokens.keys())
    corpus = [doc_tokens[d] for d in ids]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(sub_norm_tokens[:500])
    ranked = sorted(
        ((ids[idx], float(sc)) for idx, sc in enumerate(scores) if sc > 0),
        key=lambda x: (-x[1], x[0]),
    )
    return [doc_id for doc_id, _ in ranked[:top_k]]


def find_lexical_matches(
    sub_segments: list[Segment],
    cand_segments: list[Segment],
    covered_tokens: set[int],
    *,
    threshold: float = LEXICAL_THRESHOLD,
    min_words: int = MIN_SENTENCE_WORDS,
) -> list[RawMatch]:
    """Compare uncovered submission sentences against candidate sentences using TF-IDF char_wb (3,5)."""
    eligible_sub = []
    for seg in sub_segments:
        t_len = seg.token_end - seg.token_start
        if t_len < min_words:
            continue
        seg_tok_set = set(range(seg.token_start, seg.token_end))
        if len(seg_tok_set & covered_tokens) / max(1, t_len) >= 0.50:
            continue
        if seg.normalized_text.strip():
            eligible_sub.append(seg)

    eligible_cand = [
        seg for seg in cand_segments
        if (seg.token_end - seg.token_start) >= min_words and seg.normalized_text.strip()
    ]

    if not eligible_sub or not eligible_cand:
        return []

    sub_texts = [s.normalized_text for s in eligible_sub]
    cand_texts = [c.normalized_text for c in eligible_cand]

    use_idf = (len(sub_texts) + len(cand_texts)) >= 6
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=False,
        use_idf=use_idf,
    )
    try:
        all_mat = vectorizer.fit_transform(sub_texts + cand_texts)
    except ValueError:
        return []

    n_sub = len(sub_texts)
    sub_mat = all_mat[:n_sub]
    cand_mat = all_mat[n_sub:]
    # Sparse cosine similarity (TF-IDF rows are already L2-normalized by sklearn)
    sim_matrix = (sub_mat @ cand_mat.T).toarray()

    matches: list[RawMatch] = []
    for i, sub_seg in enumerate(eligible_sub):
        best_j = -1
        best_score = threshold
        row = sim_matrix[i]
        for j, score in enumerate(row):
            if score >= best_score:
                best_score = float(score)
                best_j = j
        if best_j >= 0:
            c_seg = eligible_cand[best_j]
            # Avoid emitting identical sentence if already covered
            t_indices = set(range(sub_seg.token_start, sub_seg.token_end))
            matches.append(
                RawMatch(
                    source_document_id=c_seg.document_id,
                    layer="LEXICAL",
                    sub_token_start=sub_seg.token_start,
                    sub_token_end=sub_seg.token_end,
                    src_token_start=c_seg.token_start,
                    src_token_end=c_seg.token_end,
                    matched_words=sub_seg.token_end - sub_seg.token_start,
                    score=round(best_score, 4),
                    counted_token_indices=t_indices,
                )
            )
    return matches
