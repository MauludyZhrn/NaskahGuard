"""DOAJ (Directory of Open Access Journals) public REST API source provider.

Uses the official keyless DOAJ Search API (https://doaj.org/api/search/articles/{query})
to discover peer-reviewed Open Access articles (including thousands of Indonesian OJS journals
indexed in DOAJ!). Strictly distinguishes full-text URLs from metadata/abstracts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord


class DOAJProvider(SourceProvider):
    name = "doaj"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client
        self.last_error: str | None = None
        self.last_http_status: int | None = None

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> list[SourceRecord]:
        self.last_error = None
        self.last_http_status = None
        cleaned = " ".join((query or "").replace('"', " ").split()).strip()
        if not cleaned:
            return []

        settings = get_settings()
        headers = {"User-Agent": f"NaskahGuard/0.1 (mailto:{settings.CONTACT_EMAIL})", "Accept": "application/json"}
        encoded_q = quote(cleaned[:180], safe="")
        url = f"https://doaj.org/api/search/articles/{encoded_q}"

        own = self._external_client is None
        http = self._external_client or httpx.Client(timeout=12.0)
        try:
            resp = http.get(url, params={"pageSize": max(1, min(limit, 10))}, headers=headers)
            self.last_http_status = resp.status_code
            if resp.status_code >= 400:
                self.last_error = f"HTTP {resp.status_code}"
                return []
            payload = resp.json()
        except Exception as exc:
            self.last_error = str(exc)
            return []
        finally:
            if own:
                http.close()

        results: list[SourceRecord] = []
        now = datetime.now(timezone.utc)
        for item in payload.get("results") or []:
            bib = item.get("bibjson") or {}
            title = (bib.get("title") or "").strip()
            if not title:
                continue

            ext_id = str(item.get("id") or title[:48])
            authors = [str(a.get("name")).strip() for a in (bib.get("author") or []) if a.get("name")]
            year_raw = bib.get("year")
            year = int(year_raw) if str(year_raw or "").isdigit() else None

            doi = None
            for ident in bib.get("identifier") or []:
                if str(ident.get("type") or "").lower() == "doi" and ident.get("id"):
                    doi = str(ident["id"]).strip()
                    break

            fulltext_urls: list[str] = []
            pdf_url: str | None = None
            landing_url: str | None = None
            for lnk in bib.get("link") or []:
                u = str(lnk.get("url") or "").strip()
                if not u.startswith(("http://", "https://")):
                    continue
                ltype = str(lnk.get("type") or "").lower()
                ctype = str(lnk.get("content_type") or "").lower()
                if landing_url is None:
                    landing_url = u
                if "pdf" in ctype or u.lower().endswith(".pdf"):
                    pdf_url = pdf_url or u
                    fulltext_urls.append(u)
                elif ltype == "fulltext":
                    fulltext_urls.append(u)

            lic_list = bib.get("license") or []
            lic_title = str(lic_list[0].get("type") or lic_list[0].get("title") or "").strip() if lic_list else None
            abstract = (bib.get("abstract") or "").strip() or None

            results.append(
                SourceRecord(
                    provider=self.name,
                    external_id=ext_id,
                    title=title,
                    authors=authors[:12],
                    year=year,
                    doi=doi,
                    url=landing_url or pdf_url,
                    source_type="doaj_open_access",
                    access_status="FULL_TEXT_AVAILABLE" if (pdf_url or fulltext_urls) else "METADATA_ONLY",
                    oa_pdf_url=pdf_url,
                    candidate_urls=fulltext_urls,
                    license=lic_title,
                    abstract=abstract,
                    retrieved_at=now,
                )
            )
        return results

    def get_metadata(self, external_id: str) -> SourceRecord | None:
        return None

    def fetch_content(self, url: str) -> FetchedContent | None:
        return None
