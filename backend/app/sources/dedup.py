"""Multi-signal source deduplication (DOI, canonical URL, normalized title, content hash, MinHash)."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.engine.minhash_lsh import build_minhash, minhash_from_bytes
from app.ingestion.service import normalize_title_key
from app.models import Document
from app.sources.ssrf import canonicalize_url

NEAR_DUP_JACCARD_THRESHOLD = 0.85


def _merge_alternate_url(doc: Document, new_url: str | None) -> None:
    if not new_url:
        return
    urls = list(doc.alternate_urls or [])
    if doc.url and doc.url not in urls:
        urls.append(doc.url)
    if new_url not in urls:
        urls.append(new_url)
        doc.alternate_urls = urls


def find_duplicate_source(
    db: Session,
    *,
    file_hash: str | None = None,
    doi: str | None = None,
    url: str | None = None,
    canonical_url: str | None = None,
    title: str | None = None,
    norm_tokens: list[str] | None = None,
) -> Document | None:
    """Detect whether an external/corpus source represents an already-indexed work."""
    corpus_roles = ["CORPUS", "EXTERNAL"]

    # 1. Exact content hash match
    if file_hash:
        hit = (
            db.query(Document)
            .filter(Document.role.in_(corpus_roles), Document.file_hash == file_hash)
            .first()
        )
        if hit is not None:
            _merge_alternate_url(hit, url or canonical_url)
            return hit

    # 2. DOI matching
    if doi:
        clean_doi = doi.strip().lower().replace("https://doi.org/", "")
        if clean_doi:
            hit = (
                db.query(Document)
                .filter(Document.role.in_(corpus_roles), func.lower(Document.doi) == clean_doi)
                .first()
            )
            if hit is not None:
                _merge_alternate_url(hit, url or canonical_url)
                return hit

    # 3. Canonical URL matching
    canon = canonicalize_url(canonical_url or url) if (canonical_url or url) else None
    if canon:
        hit = (
            db.query(Document)
            .filter(
                Document.role.in_(corpus_roles),
                (Document.canonical_url == canon) | (Document.url == canon),
            )
            .first()
        )
        if hit is not None:
            _merge_alternate_url(hit, url or canonical_url)
            return hit

    # 4. Normalized title matching (length >= 20 chars to avoid generic collisions)
    norm_title = normalize_title_key(title)
    if norm_title and len(norm_title) >= 20:
        hit = (
            db.query(Document)
            .filter(Document.role.in_(corpus_roles), Document.normalized_title == norm_title)
            .first()
        )
        if hit is not None:
            _merge_alternate_url(hit, url or canonical_url)
            return hit

    # 5. Near-duplicate fingerprint check via MinHash Jaccard
    if norm_tokens and len(norm_tokens) >= 40:
        cand_mh = build_minhash(norm_tokens)
        docs = (
            db.query(Document)
            .filter(Document.role.in_(corpus_roles), Document.minhash.isnot(None))
            .all()
        )
        for doc in docs:
            try:
                existing_mh = minhash_from_bytes(doc.minhash)  # type: ignore[arg-type]
                if cand_mh.jaccard(existing_mh) >= NEAR_DUP_JACCARD_THRESHOLD:
                    _merge_alternate_url(doc, url or canonical_url)
                    return doc
            except Exception:
                continue

    return None
