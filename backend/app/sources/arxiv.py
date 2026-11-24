"""arXiv Atom API adapter obeying >= 3s rate limit and open-access PDF retrieval."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from threading import Lock
import httpx

from app.config import get_settings
from app.sources.base import FetchedContent, SourceProvider, SourceRecord
from app.sources.robots import download_oa_pdf

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_rate_lock = Lock()
_last_request_ts = 0.0


class ArxivProvider(SourceProvider):
    name = "arxiv"
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, client: httpx.Client | None = None, min_interval_sec: float = 3.0) -> None:
        self._external_client = client
        self.min_interval_sec = min_interval_sec
        self.last_http_status: int | None = None
        self.last_error: str | None = None

    def _respect_rate_limit(self) -> None:
        global _last_request_ts
        if self._external_client is not None:
            return
        with _rate_lock:
            now = time.monotonic()
            wait = self.min_interval_sec - (now - _last_request_ts)
            if wait > 0:
                time.sleep(wait)
            _last_request_ts = time.monotonic()

    def _user_agent(self) -> str:
        return f"NaskahGuard/0.1 (mailto:{get_settings().CONTACT_EMAIL})"

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.Client(timeout=20.0), True

    def search(self, query: str) -> list[SourceRecord]:
        self._respect_rate_limit()
        client, should_close = self._get_client()
        self.last_http_status = None
        self.last_error = None
        try:
            resp = client.get(
                self.BASE_URL,
                params={"search_query": f"all:{query}", "start": 0, "max_results": 5},
                headers={"User-Agent": self._user_agent()},
            )
            self.last_http_status = resp.status_code
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            records: list[SourceRecord] = []
            for entry in root.findall("atom:entry", _ATOM_NS):
                entry_id = (entry.findtext("atom:id", default="", namespaces=_ATOM_NS) or "").strip()
                arxiv_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else entry_id.split("/")[-1]
                title = " ".join((entry.findtext("atom:title", default="", namespaces=_ATOM_NS) or "").split())
                published = entry.findtext("atom:published", default="", namespaces=_ATOM_NS)
                year = int(published[:4]) if published and published[:4].isdigit() else None
                authors = [
                    (a.findtext("atom:name", default="", namespaces=_ATOM_NS) or "").strip()
                    for a in entry.findall("atom:author", _ATOM_NS)
                ]
                pdf_url = None
                for link in entry.findall("atom:link", _ATOM_NS):
                    if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                        pdf_url = link.attrib.get("href")
                if not pdf_url and arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                records.append(
                    SourceRecord(
                        provider=self.name,
                        external_id=arxiv_id,
                        title=title or arxiv_id,
                        authors=[a for a in authors if a][:10],
                        year=year,
                        url=entry_id or f"https://arxiv.org/abs/{arxiv_id}",
                        source_type="arxiv_preprint",
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
        pdf_url = source_id if source_id.startswith("http") else f"https://arxiv.org/pdf/{source_id}.pdf"
        client, should_close = self._get_client()
        try:
            raw, status_label = download_oa_pdf(pdf_url, self._user_agent(), client)
            self.last_error = None if raw else status_label
            if raw is None:
                return None
            return FetchedContent(filename="arxiv_preprint.pdf", raw_bytes=raw)
        finally:
            if should_close:
                client.close()

    def get_metadata(self, source_id: str) -> SourceRecord | None:
        results = self.search(source_id)
        return results[0] if results else None
