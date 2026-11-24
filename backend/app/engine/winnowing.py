"""Winnowing fingerprinting (Schleimer et al., 2003) and candidate retrieval."""

from __future__ import annotations

from collections import defaultdict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.engine.hashing import hash_ngram
from app.models import Document, Fingerprint

DEFAULT_K = 5
DEFAULT_W = 4


def winnow_tokens(
    norm_tokens: list[str],
    k: int = DEFAULT_K,
    w: int = DEFAULT_W,
) -> list[tuple[int, int]]:
    """Return list of (fingerprint_hash, token_pos) using rightmost-minimum Winnowing."""
    n = len(norm_tokens)
    if n < k:
        return []

    kgram_hashes = [hash_ngram(norm_tokens[i : i + k]) for i in range(n - k + 1)]
    if len(kgram_hashes) < w:
        min_val = min(kgram_hashes)
        min_pos = len(kgram_hashes) - 1 - kgram_hashes[::-1].index(min_val)
        return [(min_val, min_pos)]

    fingerprints: list[tuple[int, int]] = []
    prev_min_pos = -1
    for i in range(len(kgram_hashes) - w + 1):
        window = kgram_hashes[i : i + w]
        min_val = min(window)
        # Rightmost minimum in window
        offset = len(window) - 1 - window[::-1].index(min_val)
        min_pos = i + offset
        if min_pos != prev_min_pos:
            fingerprints.append((min_val, min_pos))
            prev_min_pos = min_pos
    return fingerprints


def retrieve_winnowing_candidates(
    db: Session,
    query_fps: list[tuple[int, int]],
    *,
    allowed_doc_ids: set[str] | None = None,
    max_candidates: int = 50,
    chunk_size: int = 500,
) -> list[tuple[str, int]]:
    """Retrieve top candidate document IDs ranked by shared discriminative fingerprints."""
    if not query_fps:
        return []

    unique_hashes = list({h for h, _ in query_fps})
    min_shared = 1 if len(unique_hashes) < 3 else 2

    total_corpus_docs = (
        db.query(func.count(Document.id))
        .filter(Document.role.in_(["CORPUS", "EXTERNAL"]))
        .scalar()
        or 0
    )
    if allowed_doc_ids is not None:
        total_corpus_docs = max(total_corpus_docs, len(allowed_doc_ids))
    df_limit = max(3, int(0.30 * total_corpus_docs))

    # Count document frequency of each query hash in batches (respects SQLite param limits)
    hash_df: dict[int, int] = defaultdict(int)
    doc_shared_hashes: dict[str, set[int]] = defaultdict(set)

    for start in range(0, len(unique_hashes), chunk_size):
        batch = unique_hashes[start : start + chunk_size]
        q = db.query(Fingerprint.hash, Fingerprint.document_id).filter(Fingerprint.hash.in_(batch))
        if allowed_doc_ids is not None:
            if not allowed_doc_ids:
                return []
            q = q.filter(Fingerprint.document_id.in_(list(allowed_doc_ids)))
        rows = q.distinct().all()
        for h, doc_id in rows:
            hash_df[h] += 1
            doc_shared_hashes[doc_id].add(h)

    stop_hashes = {h for h, df in hash_df.items() if df > df_limit}
    scored: list[tuple[str, int]] = []
    for doc_id, shared in doc_shared_hashes.items():
        filtered = shared - stop_hashes
        # Fallback if all shared hashes were filtered on very small/repetitive texts
        effective = filtered if filtered else (shared if total_corpus_docs <= 3 else set())
        if len(effective) >= min_shared:
            scored.append((doc_id, len(effective)))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:max_candidates]
