"""OpenAlex official API adapter (/works?search= with polite pool mailto)."""

from __future__ import annotations

from datetime import datetime, timezone
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord
from app.sources.robots import download_oa_pdf


class OpenAlexProvider(SourceProvider):
    name = "openalex"
    BASE_URL = "https://api.openalex.org"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def _user_agent(self) -> str:
        email = get_settings().CONTACT_EMAIL
        return f"NaskahGuard/0.1 (mailto:{email})"

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=15.0), True

    def search(self, query: str) -> list[SourceRecord]:
        email = get_settings().CONTACT_EMAIL
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        try:
            resp = client.get(
                f"{self.BASE_URL}/works",
                params={"search": query, "per-page": 5, "mailto": email},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            data = resp.json()
            records: list[SourceRecord] = []
            for work in data.get("results", []):
                oa_loc = work.get("best_oa_location") or {}
                pdf_url = oa_loc.get("pdf_url")
                landing = oa_loc.get("landing_page_url") or work.get("id")
                doi = work.get("doi")
                if doi and doi.startswith("https://doi.org/"):
                    doi = doi.replace("https://doi.org/", "", 1)
                authors = [
                    a.get("author", {}).get("display_name")
                    for a in work.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ]
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=str(work.get("id", "")).split("/")[-1],
                        title=work.get("display_name") or work.get("title") or "Tanpa Judul",
                        authors=authors[:10],
                        year=work.get("publication_year"),
                        doi=doi,
                        url=landing,
                        source_type="openalex_work",
                        access_status="FULL_TEXT_AVAILABLE" if pdf_url else "METADATA_ONLY",
                        oa_pdf_url=pdf_url,
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
        pdf_url = source_id if source_id.startswith("http") else None
        if not pdf_url:
            meta = self.get_metadata(source_id)
            pdf_url = meta.oa_pdf_url if meta else None
        if not pdf_url:
            return None
        client, should_close = self._get_client()
        try:
            raw, status_label = download_oa_pdf(pdf_url, self._user_agent(), client)
            self.last_error = None if raw else status_label
            if raw is None:
                return None
            return FetchedContent(filename="openalex_source.pdf", raw_bytes=raw)
        finally:
            if should_close:
                client.close()

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        client, should_close = self._get_client()
        try:
            resp = client.get(
                f"{self.BASE_URL}/works/{source_id}",
                params={"mailto": get_settings().CONTACT_EMAIL},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            if resp.status_code >= 400:
                return None
            w = resp.json()
            oa_loc = w.get("best_oa_location") or {}
            pdf_url = oa_loc.get("pdf_url")
            return SourceRecord(
                provider=self.name,
                external_id=source_id,
                title=w.get("display_name") or "Tanpa Judul",
                authors=[
                    a.get("author", {}).get("display_name")
                    for a in w.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ][:10],
                year=w.get("publication_year"),
                doi=w.get("doi"),
                url=oa_loc.get("landing_page_url") or w.get("id"),
                source_type="openalex_work",
                access_status="FULL_TEXT_AVAILABLE" if pdf_url else "METADATA_ONLY",
                oa_pdf_url=pdf_url,
                retrieved_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            self.last_error = str(exc)
            return None
        finally:
            if should_close:
                client.close()
