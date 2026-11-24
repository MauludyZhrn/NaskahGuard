"""Europe PMC official REST API adapter with open-access full-text XML retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord


class EuropePMCProvider(SourceProvider):
    name = "europe_pmc"
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def _user_agent(self) -> str:
        return f"NaskahGuard/0.1 (mailto:{get_settings().CONTACT_EMAIL})"

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=20.0), True

    def search(self, query: str) -> list[SourceRecord]:
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        clean_q = query.strip()
        try:
            resp = client.get(
                f"{self.BASE_URL}/search",
                params={
                    "query": clean_q,
                    "resultType": "core",
                    "pageSize": 5,
                    "format": "json",
                },
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            results = resp.json().get("resultList", {}).get("result", [])
            records: list[SourceRecord] = []
            for item in results:
                pmcid = item.get("pmcid")
                pmid = item.get("pmid")
                doi = item.get("doi")
                ext_id = pmcid or pmid or doi or item.get("id") or "epmc"
                title = (item.get("title") or ext_id).strip()
                pub_year = int(item["pubYear"]) if str(item.get("pubYear", "")).isdigit() else None

                authors: list[str] = []
                for a in item.get("authorList", {}).get("author", []):
                    nm = a.get("fullName") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
                    if nm:
                        authors.append(nm)
                if not authors and item.get("authorString"):
                    authors = [x.strip() for x in str(item["authorString"]).split(",") if x.strip()]

                is_oa = str(item.get("isOpenAccess", "N")).upper() == "Y"
                candidate_urls: list[str] = []
                pdf_url = None
                if pmcid and is_oa:
                    candidate_urls.append(f"{self.BASE_URL}/{pmcid}/fullTextXML")
                for ft in item.get("fullTextUrlList", {}).get("fullTextUrl", []):
                    u = ft.get("url")
                    if u and str(u).startswith("http") and u not in candidate_urls:
                        candidate_urls.append(u)
                        if ft.get("documentStyle") == "pdf" and not pdf_url:
                            pdf_url = u

                landing = (
                    f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
                    if pmcid
                    else (f"https://doi.org/{doi}" if doi else (candidate_urls[0] if candidate_urls else None))
                )
                access_status = "FULL_TEXT_AVAILABLE" if (pmcid and is_oa) or pdf_url else "METADATA_ONLY"

                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=str(ext_id),
                        title=title,
                        authors=authors[:10],
                        year=pub_year,
                        doi=doi,
                        pmid=str(pmid) if pmid else None,
                        url=landing,
                        canonical_url=landing,
                        source_type="europe_pmc_article",
                        access_status=access_status,
                        oa_pdf_url=pdf_url or (f"{self.BASE_URL}/{pmcid}/fullTextXML" if (pmcid and is_oa) else None),
                        candidate_urls=candidate_urls,
                        license=item.get("license"),
                        abstract=item.get("abstractText"),
                        retrieved_at=datetime.now(timezone.utc),
                        extra={"pmcid": pmcid, "pmid": pmid, "is_oa": is_oa},
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
        """Fetch full-text XML from Europe PMC for an open-access PMCID or XML URL."""
        xml_url = (
            source_id
            if source_id.startswith("http")
            else f"{self.BASE_URL}/{source_id}/fullTextXML"
        )
        client, should_close = self._get_client()
        try:
            resp = client.get(xml_url, headers={"User-Agent": self._user_agent()})
            self.last_http_status = resp.status_code
            if resp.status_code in {401, 403}:
                self.last_error = "ACCESS_DENIED"
                return None
            if resp.status_code >= 400 or not resp.content:
                self.last_error = f"FETCH_FAILED ({resp.status_code})"
                return None
            if resp.content.lstrip()[:5].startswith(b"%PDF-"):
                return FetchedContent(filename="epmc.pdf", raw_bytes=resp.content, file_type="pdf", content_type="application/pdf")
            if b"<article" in resp.content or b"<?xml" in resp.content:
                return FetchedContent(filename="epmc.xml", raw_bytes=resp.content, file_type="xml", content_type="application/xml")
            return None
        except Exception as exc:
            self.last_error = str(exc)
            return None
        finally:
            if should_close:
                client.close()

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        results = self.search(source_id)
        return results[0] if results else None
