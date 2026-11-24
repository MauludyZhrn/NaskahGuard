"""Thread-safe in-memory TTL caches for URL crawls, DOI resolutions, content hashes, and provider queries."""

from __future__ import annotations

from threading import Lock
import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(
        self,
        maxsize: int = 512,
        ttl_sec: float = 3600.0,
        *,
        max_entries: int | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        self.maxsize = max_entries if max_entries is not None else maxsize
        self.ttl_sec = ttl_seconds if ttl_seconds is not None else ttl_sec
        self._lock = Lock()
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, val = entry
            if now > expires_at:
                self._store.pop(key, None)
                return None
            return val

    def set(self, key: str, value: T) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._store) >= self.maxsize:
                expired = [k for k, (exp, _) in self._store.items() if now > exp]
                for k in expired:
                    self._store.pop(k, None)
                if len(self._store) >= self.maxsize:
                    oldest_key = next(iter(self._store))
                    self._store.pop(oldest_key, None)
            self._store[key] = (now + self.ttl_sec, value)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


url_crawl_cache: TTLCache[object] = TTLCache(maxsize=512, ttl_sec=3600.0)
doi_resolution_cache: TTLCache[str] = TTLCache(maxsize=1024, ttl_sec=7200.0)
content_hash_cache: TTLCache[str] = TTLCache(maxsize=1024, ttl_sec=7200.0)
provider_query_cache: TTLCache[list] = TTLCache(maxsize=512, ttl_sec=1800.0)
