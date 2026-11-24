"""General Web Search provider interface, SearXNG self-hosted adapter, and official search API adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord
from app.sources.ssrf import canonicalize_url


class GeneralWebSearchProvider(SourceProvider, ABC):
    name = "web_search"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if a search endpoint is configured."""

    @abstractmethod
    def status_message(self) -> str:
        """Human-readable status in Bahasa Indonesia."""


class SearXNGWebSearchProvider(GeneralWebSearchProvider):
    """Self-hosted SearXNG JSON search adapter (no API key required)."""

    name = "searxng"

    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        cfg = get_settings()
        self.base_url = (base_url if base_url is not None else cfg.SEARXNG_URL).strip().rstrip("/")
        self._external_client = client
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def status_message(self) -> str:
        if self.is_configured():
            return f"SearXNG aktif ({self.base_url})"
        return "SearXNG belum dikonfigurasi (atur NG_SEARXNG_URL untuk pencarian web umum)."

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=15.0), True

    def search(self, query: str) -> list[SourceRecord]:
        if not self.is_configured():
            self.last_error = "SearXNG belum dikonfigurasi."
            return []
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        try:
            resp = client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json", "language": "auto"},
                headers={"User-Agent": f"NaskahGuard/0.1 (mailto:{get_settings().CONTACT_EMAIL})"},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            items = resp.json().get("results", [])
            records: list[SourceRecord] = []
            for idx, item in enumerate(items[:8], start=1):
                raw_url = (item.get("url") or "").strip()
                if not raw_url.startswith(("http://", "https://")):
                    continue
                canon = canonicalize_url(raw_url)
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=canon[:250] or f"web-{idx}",
                        title=(item.get("title") or raw_url)[:500],
                        authors=[],
                        url=raw_url,
                        canonical_url=canon,
                        source_type="public_web_page",
                        access_status="URL_FOUND",
                        candidate_urls=[raw_url],
                        abstract=item.get("content"),
                        retrieved_at=datetime.now(timezone.utc),
                    )
                )
            return records
        except Exception as exc:
            self.last_error = str(exc)
            return []
        finally:
            if should_close:
                client.close()

    def fetch_content(self, source_id: str) -> FetchedContent | None:
        return None

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        return None


class OfficialWebSearchAPIProvider(GeneralWebSearchProvider):
    """Generic adapter for official JSON search APIs when endpoint & key credentials are configured."""

    name = "web_api"

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        cfg = get_settings()
        self.api_url = (api_url if api_url is not None else cfg.WEB_SEARCH_API_URL).strip()
        self.api_key = (api_key if api_key is not None else cfg.WEB_SEARCH_API_KEY).strip()
        self._external_client = client
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def status_message(self) -> str:
        if self.is_configured():
            return "API Pencarian Web Resmi terkonfigurasi."
        return "API Pencarian Web Resmi belum dikonfigurasi (opsional: NG_WEB_SEARCH_API_URL & NG_WEB_SEARCH_API_KEY)."

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=15.0), True

    def search(self, query: str) -> list[SourceRecord]:
        if not self.is_configured():
            self.last_error = "Kredensial API pencarian web belum dikonfigurasi."
            return []
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        try:
            resp = client.get(
                self.api_url,
                params={"q": query, "count": 5},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-API-Key": self.api_key,
                },
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            payload = resp.json()
            raw_items = payload.get("results") or payload.get("items") or payload.get("webPages", {}).get("value", [])
            records: list[SourceRecord] = []
            for idx, item in enumerate(raw_items[:8], start=1):
                raw_url = (item.get("url") or item.get("link") or "").strip()
                if not raw_url.startswith(("http://", "https://")):
                    continue
                canon = canonicalize_url(raw_url)
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=canon[:250] or f"webapi-{idx}",
                        title=(item.get("title") or item.get("name") or raw_url)[:500],
                        url=raw_url,
                        canonical_url=canon,
                        source_type="public_web_page",
                        access_status="URL_FOUND",
                        candidate_urls=[raw_url],
                        abstract=item.get("snippet") or item.get("description"),
                        retrieved_at=datetime.now(timezone.utc),
                    )
                )
            return records
        except Exception as exc:
            self.last_error = str(exc)
            return []
        finally:
            if should_close:
                client.close()

    def fetch_content(self, source_id: str) -> FetchedContent | None:
        return None

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        return None
