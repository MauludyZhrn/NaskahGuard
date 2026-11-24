"""OAI-PMH 2.0 Harvester for Indonesian Academic Repositories (OJS, DSpace, EPrints)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
import defusedxml.ElementTree as ET
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.models import OAIRepository
from app.sources.crawler import fetch_public_url
from app.sources.dedup import find_duplicate_source
from app.sources.ssrf import validate_public_url

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


@dataclass
class OAIRecord:
    identifier: str
    datestamp: str | None
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    urls: list[str] = field(default_factory=list)
    pdf_urls: list[str] = field(default_factory=list)
    rights: str | None = None
    description: str | None = None


class OAIPMHClient:
    """Standards-compliant OAI-PMH 2.0 client using defusedxml and SSRF checks."""

    def __init__(self, client: httpx.Client | None = None, *, resolve_dns: bool = True) -> None:
        self._external_client = client
        self.resolve_dns = resolve_dns

    def _get(self, base_url: str, params: dict[str, str]) -> ET.Element:
        safe_url = validate_public_url(base_url, resolve_dns=self.resolve_dns)
        ua = f"NaskahGuard-OAI/0.1 (mailto:{get_settings().CONTACT_EMAIL})"
        client = self._external_client or httpx.Client(timeout=20.0)
        try:
            resp = client.get(safe_url, params=params, headers={"User-Agent": ua}, follow_redirects=False)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            for child in root:
                if _local(child.tag) == "error":
                    code = child.attrib.get("code", "unknown")
                    raise ValueError(f"OAI-PMH error ({code}): {child.text or ''}")
            return root
        finally:
            if self._external_client is None:
                client.close()

    def identify(self, base_url: str) -> dict[str, str]:
        root = self._get(base_url, {"verb": "Identify"})
        info: dict[str, str] = {}
        for el in root.iter():
            ln = _local(el.tag)
            if ln in {"repositoryName", "baseURL", "protocolVersion", "earliestDatestamp", "granularity"} and el.text:
                info[ln] = el.text.strip()
        return info

    def list_metadata_formats(self, base_url: str) -> list[str]:
        root = self._get(base_url, {"verb": "ListMetadataFormats"})
        formats: list[str] = []
        for el in root.iter():
            if _local(el.tag) == "metadataPrefix" and el.text:
                formats.append(el.text.strip())
        return formats

    def list_sets(self, base_url: str) -> list[dict[str, str]]:
        root = self._get(base_url, {"verb": "ListSets"})
        sets: list[dict[str, str]] = []
        for s_el in root.iter():
            if _local(s_el.tag) == "set":
                spec = ""
                name = ""
                for c in s_el:
                    if _local(c.tag) == "setSpec" and c.text:
                        spec = c.text.strip()
                    elif _local(c.tag) == "setName" and c.text:
                        name = c.text.strip()
                if spec:
                    sets.append({"setSpec": spec, "setName": name or spec})
        return sets

    @staticmethod
    def _parse_record(rec_el: ET.Element) -> OAIRecord | None:
        identifier = ""
        datestamp = None
        deleted = False
        titles: list[str] = []
        authors: list[str] = []
        dates: list[str] = []
        identifiers: list[str] = []
        relations: list[str] = []
        rights: list[str] = []
        descriptions: list[str] = []

        for el in rec_el.iter():
            ln = _local(el.tag)
            if ln == "header" and el.attrib.get("status") == "deleted":
                deleted = True
            elif ln == "identifier" and el.text and not identifier:
                identifier = el.text.strip()
            elif ln == "datestamp" and el.text and datestamp is None:
                datestamp = el.text.strip()
            elif ln == "title" and el.text:
                titles.append(" ".join(el.text.split()))
            elif ln == "creator" and el.text:
                authors.append(" ".join(el.text.split()))
            elif ln == "date" and el.text:
                dates.append(el.text.strip())
            elif ln == "relation" and el.text:
                relations.append(el.text.strip())
            elif ln == "rights" and el.text:
                rights.append(el.text.strip())
            elif ln == "description" and el.text:
                descriptions.append(" ".join(el.text.split()))
            elif ln == "identifier" and el.text and el.text.strip() != identifier:
                identifiers.append(el.text.strip())

        if deleted or not identifier:
            return None

        year = None
        for d in dates:
            m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", d)
            if m_yr:
                year = int(m_yr.group(1))
                break

        doi = None
        urls: list[str] = []
        pdf_urls: list[str] = []
        for val in identifiers + relations:
            m_doi = _DOI_RE.search(val)
            if m_doi and not doi:
                doi = m_doi.group(1).rstrip(".,;)")
            if val.startswith(("http://", "https://")):
                if val not in urls:
                    urls.append(val)
                low = val.lower()
                if low.endswith(".pdf") or "/article/download/" in low or "/bitstream/" in low:
                    if val not in pdf_urls:
                        pdf_urls.append(val)

        return OAIRecord(
            identifier=identifier,
            datestamp=datestamp,
            title=(titles[0] if titles else identifier)[:500],
            authors=authors[:10],
            year=year,
            doi=doi,
            urls=urls,
            pdf_urls=pdf_urls,
            rights=rights[0][:250] if rights else None,
            description=descriptions[0][:1000] if descriptions else None,
        )

    def list_records(
        self,
        base_url: str,
        *,
        metadata_prefix: str = "oai_dc",
        from_datestamp: str | None = None,
        until_datestamp: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
    ) -> tuple[list[OAIRecord], str | None]:
        params: dict[str, str] = {"verb": "ListRecords"}
        if resumption_token:
            params["resumptionToken"] = resumption_token
        else:
            params["metadataPrefix"] = metadata_prefix
            if from_datestamp:
                params["from"] = from_datestamp
            if until_datestamp:
                params["until"] = until_datestamp
            if set_spec:
                params["set"] = set_spec

        root = self._get(base_url, params)
        records: list[OAIRecord] = []
        next_token: str | None = None
        for el in root.iter():
            ln = _local(el.tag)
            if ln == "record":
                parsed = self._parse_record(el)
                if parsed is not None:
                    records.append(parsed)
            elif ln == "resumptionToken" and el.text and el.text.strip():
                next_token = el.text.strip()
        return records, next_token

    def get_record(self, base_url: str, identifier: str, metadata_prefix: str = "oai_dc") -> OAIRecord | None:
        root = self._get(base_url, {"verb": "GetRecord", "identifier": identifier, "metadataPrefix": metadata_prefix})
        for el in root.iter():
            if _local(el.tag) == "record":
                return self._parse_record(el)
        return None


def harvest_oai_repository(
    db: Session,
    repo: OAIRepository,
    *,
    max_records: int = 20,
    download_pdfs: bool = True,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
) -> dict[str, int | str]:
    """Incrementally harvest OAI-PMH records and index public full-text PDFs into local corpus."""
    oai = OAIPMHClient(client=client, resolve_dns=resolve_dns)
    settings = get_settings()
    repo.status = "HARVESTING"
    repo.last_error = None
    db.commit()

    harvested = 0
    indexed_ft = 0
    metadata_only = 0
    latest_ds = repo.last_datestamp

    try:
        ident = oai.identify(repo.base_url)
        if ident.get("repositoryName"):
            repo.identified_name = ident["repositoryName"][:500]

        token: str | None = None
        first_page = True
        while harvested < max_records:
            recs, token = oai.list_records(
                repo.base_url,
                metadata_prefix=repo.metadata_prefix,
                from_datestamp=repo.last_datestamp if first_page else None,
                resumption_token=token if not first_page else None,
            )
            first_page = False
            if not recs:
                break

            for rec in recs:
                if harvested >= max_records:
                    break
                harvested += 1
                if rec.datestamp and (latest_ds is None or rec.datestamp > latest_ds):
                    latest_ds = rec.datestamp

                primary_url = rec.pdf_urls[0] if rec.pdf_urls else (rec.urls[0] if rec.urls else None)
                dup = find_duplicate_source(
                    db,
                    doi=rec.doi,
                    url=primary_url,
                    title=rec.title,
                )
                if dup is not None:
                    db.commit()
                    continue

                if download_pdfs and rec.pdf_urls:
                    fetched_ok = False
                    for pdf_url in rec.pdf_urls[:2]:
                        crawl = fetch_public_url(
                            pdf_url,
                            client=client,
                            enable_browser_crawler=False,
                            max_bytes=settings.MAX_EXTERNAL_DOWNLOAD_MB * 1024 * 1024,
                            resolve_dns=resolve_dns,
                        )
                        if crawl.status == "FULLTEXT_FETCHED" and crawl.raw_bytes and crawl.file_type:
                            try:
                                val = validate_local_bytes(
                                    f"oai_{repo.repo_type}.{crawl.file_type}",
                                    crawl.raw_bytes,
                                    settings.max_upload_bytes,
                                    allow_web_formats=True,
                                )
                                ingest_validated_upload(
                                    db,
                                    val,
                                    role="CORPUS",
                                    title=rec.title,
                                    authors=rec.authors,
                                    year=rec.year,
                                    doi=rec.doi,
                                    url=primary_url,
                                    canonical_url=crawl.canonical_url or primary_url,
                                    license_name=rec.rights,
                                    indexing_status="FULLTEXT_INDEXED",
                                    source_type=f"oai_{repo.repo_type}",
                                    access_status="INDEXED_LOCALLY",
                                    provider=f"oai:{repo.name}",
                                    external_id=rec.identifier,
                                )
                                indexed_ft += 1
                                fetched_ok = True
                                break
                            except Exception:
                                continue
                    if fetched_ok:
                        continue

                # Metadata-only: never treat as full-text!
                metadata_only += 1

            if not token:
                break

        repo.last_harvested_at = datetime.now(timezone.utc)
        repo.last_datestamp = latest_ds
        repo.records_harvested += harvested
        repo.fulltext_indexed += indexed_ft
        repo.status = "VERIFIED"
        db.commit()
    except Exception as exc:
        repo.status = "ERROR"
        repo.last_error = str(exc)
        db.commit()
        raise

    return {
        "repository": repo.name,
        "records_harvested": harvested,
        "fulltext_indexed": indexed_ft,
        "metadata_only": metadata_only,
        "status": repo.status,
    }
