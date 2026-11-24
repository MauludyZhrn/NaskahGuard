"""Source discovery registry & external ingestion coordinator."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.models import Document, ProviderQuery, Segment
from app.sources.arxiv import ArxivProvider
from app.sources.base import SourceRecord, extract_query_keywords
from app.sources.crossref import CrossrefProvider
from app.sources.openalex import OpenAlexProvider
from app.sources.pmc import PubMedCentralProvider


@dataclass
class DiscoverySummary:
    external_fulltext_doc_ids: set[str]
    metadata_only_records: list[SourceRecord]
    access_denied_count: int
    fetch_failed_count: int
    queries_executed: int


def get_provider_instances() -> dict[str, object]:
    return {
        "openalex": OpenAlexProvider(),
        "crossref": CrossrefProvider(),
        "arxiv": ArxivProvider(),
        "pmc": PubMedCentralProvider(),
    }


def discover_external_sources(
    db: Session,
    *,
    check_id: str,
    submission_doc: Document,
    submission_segments: list[Segment],
    provider_names: list[str],
) -> DiscoverySummary:
    """Query enabled external providers using only short title/keyword queries and index OA full-text."""
    providers = get_provider_instances()
    queries = extract_query_keywords(
        submission_doc.title,
        [s.original_text for s in submission_segments if s.zone == "BODY"],
    )
    settings = get_settings()

    fulltext_doc_ids: set[str] = set()
    metadata_only: list[SourceRecord] = []
    access_denied = 0
    fetch_failed = 0
    queries_executed = 0

    seen_external: set[tuple[str, str]] = set()
    for pname in provider_names:
        provider = providers.get(pname)
        if provider is None:
            continue
        for q_str in queries[:2]:
            started = datetime.now(timezone.utc)
            t0 = time.monotonic()
            records = provider.search(q_str)
            dur_ms = int((time.monotonic() - t0) * 1000)
            queries_executed += 1

            pq = ProviderQuery(
                check_id=check_id,
                provider=pname,
                query=q_str[:512],
                status="OK" if getattr(provider, "last_error", None) is None else "ERROR",
                result_count=len(records),
                http_status=getattr(provider, "last_http_status", None),
                error=getattr(provider, "last_error", None),
                started_at=started,
                duration_ms=dur_ms,
            )
            db.add(pq)
            db.flush()

            for rec in records[:3]:
                key = (rec.provider, rec.external_id)
                if key in seen_external:
                    continue
                seen_external.add(key)

                if rec.oa_pdf_url and rec.access_status == "FULL_TEXT_AVAILABLE":
                    fetched = provider.fetch_content(rec.oa_pdf_url)
                    if fetched is not None:
                        try:
                            validated = validate_local_bytes(
                                f"{rec.provider}_{rec.external_id}.pdf",
                                fetched.raw_bytes,
                                settings.max_upload_bytes,
                            )
                            ext_doc = ingest_validated_upload(
                                db,
                                validated,
                                role="EXTERNAL",
                                title=rec.title,
                                authors=rec.authors,
                                year=rec.year,
                                doi=rec.doi,
                                url=rec.url or rec.oa_pdf_url,
                                source_type=rec.source_type,
                                access_status="INDEXED_LOCALLY",
                                provider=rec.provider,
                                external_id=rec.external_id,
                            )
                            fulltext_doc_ids.add(ext_doc.id)
                            continue
                        except Exception:
                            fetch_failed += 1
                            continue
                    else:
                        err_label = getattr(provider, "last_error", "") or ""
                        if err_label == "ACCESS_DENIED":
                            access_denied += 1
                        else:
                            fetch_failed += 1
                        rec.access_status = err_label or "FETCH_FAILED"

                metadata_only.append(rec)

    db.commit()
    return DiscoverySummary(
        external_fulltext_doc_ids=fulltext_doc_ids,
        metadata_only_records=metadata_only,
        access_denied_count=access_denied,
        fetch_failed_count=fetch_failed,
        queries_executed=queries_executed,
    )
