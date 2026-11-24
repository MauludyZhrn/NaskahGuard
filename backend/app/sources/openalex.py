"""OpenAlex official API adapter with full-text awareness, locations inspection, and content API support."""

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

    @staticmethod
    def _reconstruct_abstract(inv_index: dict | None) -> str | None:
        if not inv_index or not isinstance(inv_index, dict):
            return None
        pos_map: dict[int, str] = {}
        for word, positions in inv_index.items():
            if not isinstance(positions, list):
                continue
            for p in positions:
                pos_map[int(p)] = word
        if not pos_map:
            return None
        return " ".join(pos_map[k] for k in sorted(pos_map.keys()))[:1200]

    def _parse_work(self, work: dict) -> SourceRecord:
        oa_loc = work.get("best_oa_location") or {}
        pdf_url = oa_loc.get("pdf_url")
        landing = oa_loc.get("landing_page_url") or (work.get("open_access") or {}).get("oa_url") or work.get("id")
        license_name = oa_loc.get("license")

        candidate_urls: list[str] = []
        if pdf_url:
            candidate_urls.append(pdf_url)
        for loc in work.get("locations") or []:
            if not isinstance(loc, dict):
                continue
            if loc.get("is_oa") and loc.get("pdf_url") and loc["pdf_url"] not in candidate_urls:
                candidate_urls.append(loc["pdf_url"])
                if not pdf_url:
                    pdf_url = loc["pdf_url"]
            if loc.get("is_oa") and loc.get("landing_page_url") and loc["landing_page_url"] not in candidate_urls:
                candidate_urls.append(loc["landing_page_url"])
            if not license_name and loc.get("license"):
                license_name = loc.get("license")
        if landing and landing not in candidate_urls and str(landing).startswith("http"):
            candidate_urls.append(landing)

        work_id = str(work.get("id", "")).split("/")[-1]
        has_content = work.get("has_fulltext") or False
        api_key = get_settings().OPENALEX_API_KEY.strip()
        if api_key and work_id and work.get("has_content", {}).get("grobid_xml"):
            candidate_urls.append(f"https://content.openalex.org/works/{work_id}.grobid-xml?api_key={api_key}")

        doi = work.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "", 1)

        authors = [
            a.get("author", {}).get("display_name")
            for a in work.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ]

        is_oa = bool((work.get("open_access") or {}).get("is_oa") or pdf_url or oa_loc.get("landing_page_url"))
        access_status = "FULL_TEXT_AVAILABLE" if (pdf_url or (is_oa and candidate_urls)) else "METADATA_ONLY"

        return SourceRecord(
            provider=self.name,
            external_id=work_id,
            title=work.get("display_name") or work.get("title") or "Tanpa Judul",
            authors=authors[:10],
            year=work.get("publication_year"),
            doi=doi,
            url=landing,
            canonical_url=landing,
            source_type="openalex_work",
            access_status=access_status,
            oa_pdf_url=pdf_url,
            candidate_urls=candidate_urls,
            license=license_name,
            abstract=self._reconstruct_abstract(work.get("abstract_inverted_index")),
            retrieved_at=datetime.now(timezone.utc),
            extra={"has_fulltext": bool(has_content), "is_oa": is_oa},
        )

    def search(self, query: str, *, prefer_fulltext: bool = True) -> list[SourceRecord]:
        settings = get_settings()
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        clean_q = query.strip().strip('"')
        try:
            params: dict[str, str | int] = {
                "search": clean_q,
                "per-page": 5,
                "mailto": settings.CONTACT_EMAIL,
            }
            if prefer_fulltext:
                params["filter"] = "is_oa:true"
            if settings.OPENALEX_API_KEY.strip():
                params["api_key"] = settings.OPENALEX_API_KEY.strip()

            resp = client.get(
                f"{self.BASE_URL}/works",
                params=params,
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            results = resp.json().get("results", [])

            # Fallback without is_oa filter if OA-filtered search returned 0 results
            if not results and prefer_fulltext:
                params.pop("filter", None)
                resp2 = client.get(
                    f"{self.BASE_URL}/works",
                    params=params,
                    headers={"User-Agent": self._user_agent()},
                )
                self.last_http_status = resp2.status_code
                resp2.raise_for_status()
                results = resp2.json().get("results", [])

            return [self._parse_work(w) for w in results]
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
            return FetchedContent(filename="openalex_source.pdf", raw_bytes=raw, file_type="pdf")
        finally:
            if should_close:
                client.close()

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        client, should_close = self._get_client()
        try:
            params = {"mailto": get_settings().CONTACT_EMAIL}
            resp = client.get(
                f"{self.BASE_URL}/works/{source_id}",
                params=params,
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            if resp.status_code >= 400:
                return None
            return self._parse_work(resp.json())
        except Exception as exc:
            self.last_error = str(exc)
            return None
        finally:
            if should_close:
                client.close()
