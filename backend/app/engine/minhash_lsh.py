"""MinHash (128 permutations) + Locality Sensitive Hashing candidate retrieval."""

from __future__ import annotations

from threading import Lock
import numpy as np
from datasketch import MinHash, MinHashLSH
from sqlalchemy.orm import Session

from app.models import Document

NUM_PERM = 128
LSH_THRESHOLD = 0.2

_lsh_lock = Lock()
_lsh_cache: tuple[frozenset[str], MinHashLSH, dict[str, MinHash]] | None = None


def invalidate_lsh_cache() -> None:
    global _lsh_cache
    with _lsh_lock:
        _lsh_cache = None


def build_minhash(norm_tokens: list[str], ngram_size: int = 3) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    if not norm_tokens:
        return m
    if len(norm_tokens) < ngram_size:
        for tok in norm_tokens:
            m.update(tok.encode("utf-8"))
        return m
    for i in range(len(norm_tokens) - ngram_size + 1):
        shingle = " ".join(norm_tokens[i : i + ngram_size]).encode("utf-8")
        m.update(shingle)
    return m


def compute_minhash_bytes(norm_tokens: list[str]) -> bytes:
    m = build_minhash(norm_tokens)
    return m.hashvalues.astype(np.uint64).tobytes()


def minhash_from_bytes(raw: bytes) -> MinHash:
    arr = np.frombuffer(raw, dtype=np.uint64).copy()
    return MinHash(num_perm=len(arr), hashvalues=arr)


def query_minhash_candidates(
    db: Session,
    norm_tokens: list[str],
    *,
    allowed_doc_ids: set[str] | None = None,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    """Query LSH index over persisted corpus MinHash signatures."""
    global _lsh_cache
    if not norm_tokens:
        return []

    query_mh = build_minhash(norm_tokens)

    with _lsh_lock:
        if allowed_doc_ids is not None:
            docs = (
                db.query(Document.id, Document.minhash)
                .filter(Document.id.in_(list(allowed_doc_ids)), Document.minhash.isnot(None))
                .all()
            )
            doc_key = frozenset(d[0] for d in docs)
            if _lsh_cache is not None and _lsh_cache[0] == doc_key:
                _, lsh, mh_map = _lsh_cache
            else:
                lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
                mh_map = {}
                for doc_id, raw_bytes in docs:
                    mh = minhash_from_bytes(raw_bytes)
                    mh_map[doc_id] = mh
                    lsh.insert(doc_id, mh)
                _lsh_cache = (doc_key, lsh, mh_map)
        else:
            docs = (
                db.query(Document.id, Document.minhash)
                .filter(Document.role.in_(["CORPUS", "EXTERNAL"]), Document.minhash.isnot(None))
                .all()
            )
            doc_key = frozenset(d[0] for d in docs)
            if _lsh_cache is not None and _lsh_cache[0] == doc_key:
                _, lsh, mh_map = _lsh_cache
            else:
                lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
                mh_map = {}
                for doc_id, raw_bytes in docs:
                    mh = minhash_from_bytes(raw_bytes)
                    mh_map[doc_id] = mh
                    lsh.insert(doc_id, mh)
                _lsh_cache = (doc_key, lsh, mh_map)

    hits = lsh.query(query_mh)
    scored = [(doc_id, float(query_mh.jaccard(mh_map[doc_id]))) for doc_id in hits if doc_id in mh_map]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:top_k]
