"""PubMed Central (NCBI E-utilities) adapter (<= 3 req/sec without API key)."""

from __future__ import annotations

from datetime import datetime, timezone
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord


class PubMedCentralProvider(SourceProvider):
    name = "pmc"
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

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
            esearch = client.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params={"db": "pmc", "term": query, "retmax": 5, "retmode": "json"},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = esearch.status_code
            esearch.raise_for_status()
            id_list = esearch.json().get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []

            esum = client.get(
                f"{self.BASE_URL}/esummary.fcgi",
                params={"db": "pmc", "id": ",".join(id_list), "retmode": "json"},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = esum.status_code
            esum.raise_for_status()
            result_map = esum.json().get("result", {})
            records: list[SourceRecord] = []
            for pmcid in id_list:
                info = result_map.get(str(pmcid), {})
                if not isinstance(info, dict):
                    continue
                pubdate = info.get("pubdate", "")
                year = int(pubdate[:4]) if pubdate and pubdate[:4].isdigit() else None
                doi = None
                for aid in info.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value")
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=f"PMC{pmcid}" if not str(pmcid).startswith("PMC") else str(pmcid),
                        title=info.get("title") or f"PMC{pmcid}",
                        authors=[a.get("name") for a in info.get("authors", []) if a.get("name")][:10],
                        year=year,
                        doi=doi,
                        url=f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmcid}/",
                        source_type="pmc_article",
                        access_status="METADATA_ONLY",
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
        # PMC full-text OA archive requires bulk FTP/OA service XML retrieval; marked metadata-only here.
        return None

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        return None
