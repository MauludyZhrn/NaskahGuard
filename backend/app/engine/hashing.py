"""64-bit Blake2b n-gram hashing compatible with SQLite and PostgreSQL BIGINT."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence


def hash_ngram(tokens: Sequence[str]) -> int:
    """Compute a deterministic signed 64-bit integer hash for a sequence of normalized tokens."""
    payload = " ".join(tokens).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)
