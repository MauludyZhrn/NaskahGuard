"""Crossref official metadata API adapter (METADATA_ONLY)."""

from __future__ import annotations

from datetime import datetime, timezone
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord


class CrossrefProvider(SourceProvider):
    name = "crossref"
    BASE_URL = "https://api.crossref.org"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def _user_agent(self) -> str:
        return f"NaskahGuard/0.1 (mailto:{get_settings().CONTACT_EMAIL})"

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=15.0), True

    def search(self, query: str) -> list[SourceRecord]:
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        try:
            resp = client.get(
                f"{self.BASE_URL}/works",
                params={"query.bibliographic": query, "rows": 5},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            items = resp.json().get("message", {}).get("items", [])
            records: list[SourceRecord] = []
            for item in items:
                titles = item.get("title") or []
                title = titles[0] if titles else "Tanpa Judul"
                authors = [
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in item.get("author", [])
                    if a.get("family") or a.get("given")
                ]
                year = None
                issued = item.get("issued", {}).get("date-parts")
                if issued and issued[0] and issued[0][0] is not None:
                    year = int(issued[0][0])
                doi = item.get("DOI")
                landing = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
                licenses = item.get("license") or []
                lic_url = licenses[0].get("URL") if licenses and isinstance(licenses[0], dict) else None
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=doi or landing or title[:80],
                        title=title,
                        authors=authors[:10],
                        year=year,
                        doi=doi,
                        url=landing,
                        canonical_url=landing,
                        source_type="crossref_metadata",
                        access_status="METADATA_ONLY",
                        license=lic_url,
                        extra={"publisher": item.get("publisher")},
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
        # Crossref provides metadata only, never full-text PDFs directly
        return None

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        client, should_close = self._get_client()
        try:
            resp = client.get(
                f"{self.BASE_URL}/works/{source_id}",
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            if resp.status_code >= 400:
                return None
            item = resp.json().get("message", {})
            titles = item.get("title") or []
            doi = item.get("DOI")
            return SourceRecord(
                provider=self.name,
                external_id=doi or source_id,
                title=titles[0] if titles else "Tanpa Judul",
                authors=[
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in item.get("author", [])
                ][:10],
                doi=doi,
                url=item.get("URL"),
                source_type="crossref_metadata",
                access_status="METADATA_ONLY",
                retrieved_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            self.last_error = str(exc)
            return None
        finally:
            if should_close:
                client.close()
