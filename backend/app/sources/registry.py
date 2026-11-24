"""Progressive Full-Text Acquisition Pipeline (Phase 9 Performance & Transparency Upgrade).

Key optimizations vs Phase 8 (~11m10s bottleneck resolved):
- Concurrent execution across independent external providers (`ThreadPoolExecutor`) with per-provider query budgets
  (e.g. capping arXiv's 3s rate-limited API to top-ranked queries so 24/48 queries never stall sequentially).
- Provider query TTL cache (`provider_query_cache`) to eliminate duplicate requests.
- Content SHA-256 cache (`content_hash_cache`) alongside DOI & canonical URL caches to prevent duplicate indexing.
- Connection reuse (`httpx.Client` pooling) inside worker pools.
- Transparent telemetry: `queries_generated`, `queries_executed`, `queries_skipped`, `stage_timings_ms`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.service import ingest_validated_upload, normalize_title_key
from app.ingestion.validators import validate_local_bytes
from app.models import Document, ProviderQuery, Segment, SourceAcquisition
from app.schemas import CheckSettingsSchema
from app.sources.arxiv import ArxivProvider
from app.sources.base import SourceRecord
from app.sources.cache import content_hash_cache, doi_resolution_cache, provider_query_cache, url_crawl_cache
from app.sources.crawler import CrawlResult, fetch_public_url
from app.sources.crossref import CrossrefProvider
from app.sources.dedup import find_duplicate_source
from app.sources.doaj import DOAJProvider
from app.sources.europe_pmc import EuropePMCProvider
from app.sources.openalex import OpenAlexProvider
from app.sources.pmc import PubMedCentralProvider
from app.sources.query_generator import QueryCandidate, generate_intelligent_queries
from app.sources.ranking import RankedCandidate, score_candidate_relevance
from app.sources.ssrf import canonicalize_url
from app.sources.web_search import OfficialWebSearchAPIProvider, SearXNGWebSearchProvider

# Provider-specific sensible per-check query caps so slow rate-limited providers never stall DEEP checks
_PROVIDER_MAX_QUERIES: dict[str, int] = {
    "arxiv": 6,        # arXiv mandates 3s delay per query -> max ~18s instead of 144s!
    "crossref": 12,    # metadata-only supplement
    "doaj": 12,
    "europe_pmc": 18,
    "pmc": 10,
    "openalex": 48,
    "searxng": 24,
    "web_api": 20,
}


@dataclass
class DiscoverySummary:
    external_fulltext_doc_ids: set[str]
    metadata_only_records: list[SourceRecord]
    access_denied_count: int
    fetch_failed_count: int
    queries_executed: int
    search_coverage: dict[str, Any] = field(default_factory=dict)
    stage_timings_ms: dict[str, int] = field(default_factory=dict)


def get_provider_instances() -> dict[str, object]:
    return {
        "openalex": OpenAlexProvider(),
        "europe_pmc": EuropePMCProvider(),
        "pmc": PubMedCentralProvider(),
        "arxiv": ArxivProvider(),
        "doaj": DOAJProvider(),
        "crossref": CrossrefProvider(),
        "searxng": SearXNGWebSearchProvider(),
        "web_api": OfficialWebSearchAPIProvider(),
    }


def _select_active_providers(cfg: CheckSettingsSchema) -> list[str]:
    selected: list[str] = []
    academic_set = {"openalex", "europe_pmc", "pmc", "arxiv", "doaj", "crossref"}
    web_set = {"searxng", "web_api"}
    for pname in cfg.external_providers:
        key = pname.lower()
        if key in academic_set and cfg.enable_academic_search:
            selected.append(key)
        elif key in web_set and cfg.enable_web_search:
            selected.append(key)
    if cfg.enable_web_search:
        for wp in ("searxng", "web_api"):
            if wp not in selected:
                selected.append(wp)
    return selected


def _run_provider_queries_worker(
    pname: str,
    provider: object,
    queries: list[QueryCandidate],
    use_cache: bool,
) -> tuple[str, list[tuple[QueryCandidate, list[SourceRecord], datetime, int, int | None, str | None]], int]:
    """Execute queries for a single provider (runs concurrently across distinct providers)."""
    cap = _PROVIDER_MAX_QUERIES.get(pname, 24)
    assigned = queries[:cap]
    skipped = max(0, len(queries) - len(assigned))
    logs: list[tuple[QueryCandidate, list[SourceRecord], datetime, int, int | None, str | None]] = []

    for qc in assigned:
        cache_key = f"{pname}:{qc.query.lower()}"
        if use_cache:
            cached_recs = provider_query_cache.get(cache_key)
            if cached_recs is not None:
                logs.append((qc, list(cached_recs), datetime.now(timezone.utc), 0, 200, None))
                continue

        started = datetime.now(timezone.utc)
        t0 = time.monotonic()
        records = provider.search(qc.query)  # type: ignore[attr-defined]
        dur_ms = int((time.monotonic() - t0) * 1000)
        err_msg = getattr(provider, "last_error", None)
        http_st = getattr(provider, "last_http_status", None)
        if use_cache and err_msg is None:
            provider_query_cache.set(cache_key, list(records))
        logs.append((qc, records, started, dur_ms, http_st, err_msg))
        # Early abort this provider if consecutive network unreachability occurs
        if err_msg and len(logs) >= 2 and all(item[5] is not None for item in logs[-2:]):
            skipped += max(0, len(assigned) - len(logs))
            break

    return pname, logs, skipped


def _fetch_candidate_worker(
    rec: SourceRecord,
    provider: object,
    urls_to_try: list[str],
    *,
    shared_http: httpx.Client | None,
    enable_browser_crawler: bool,
    max_download_bytes: int,
    resolve_dns: bool,
) -> tuple[bytes | None, str | None, bool, str | None, str | None, str, int]:
    """Bounded worker fetching a single candidate's full-text with TTL cache & connection reuse."""
    acq_t0 = time.monotonic()
    fetched_bytes: bytes | None = None
    fetched_type: str | None = None
    used_pw = False
    final_canon = canonicalize_url(rec.canonical_url or rec.url) if (rec.canonical_url or rec.url) else None
    acq_error: str | None = None
    acq_status = "CRAWL_FAILED"

    if rec.provider in {"europe_pmc", "pmc"} and rec.oa_pdf_url and "fullTextXML" in rec.oa_pdf_url:
        fc = provider.fetch_content(rec.oa_pdf_url)  # type: ignore[attr-defined]
        if fc is not None:
            fetched_bytes = fc.raw_bytes
            fetched_type = fc.file_type
            acq_status = "FULLTEXT_FETCHED"

    if fetched_bytes is None:
        ext_client = getattr(provider, "_external_client", None)
        use_client = ext_client or (None if enable_browser_crawler else shared_http)
        for target_url in urls_to_try[:2]:
            cache_key = canonicalize_url(target_url)
            cached = url_crawl_cache.get(cache_key) if ext_client is None else None
            if isinstance(cached, CrawlResult):
                crawl = cached
            else:
                crawl = fetch_public_url(
                    target_url,
                    client=use_client,
                    enable_browser_crawler=enable_browser_crawler,
                    max_bytes=max_download_bytes,
                    resolve_dns=resolve_dns,
                )
                if ext_client is None:
                    url_crawl_cache.set(cache_key, crawl)

            used_pw = used_pw or crawl.used_playwright
            if crawl.status == "FULLTEXT_FETCHED" and crawl.raw_bytes and crawl.file_type:
                fetched_bytes = crawl.raw_bytes
                fetched_type = crawl.file_type
                final_canon = crawl.canonical_url or final_canon
                acq_status = "FULLTEXT_FETCHED"
                if crawl.title and rec.title == "Tanpa Judul":
                    rec.title = crawl.title
                if crawl.doi and not rec.doi:
                    rec.doi = crawl.doi
                break
            acq_status = crawl.status
            acq_error = crawl.error

    acq_ms = int((time.monotonic() - acq_t0) * 1000)
    return fetched_bytes, fetched_type, used_pw, final_canon, acq_error, acq_status, acq_ms


def discover_external_sources(
    db: Session,
    *,
    check_id: str,
    submission_doc: Document,
    submission_segments: list[Segment],
    provider_names: list[str] | None = None,
    check_settings: CheckSettingsSchema | None = None,
    providers_override: dict[str, object] | None = None,
    resolve_dns: bool = True,
) -> DiscoverySummary:
    """Execute progressive multi-query search, candidate relevance ranking, bounded concurrent crawl, and indexing."""
    cfg = check_settings or CheckSettingsSchema(external_providers=provider_names or ["openalex", "europe_pmc", "arxiv", "crossref"])
    providers = providers_override if providers_override is not None else get_provider_instances()
    active_names = _select_active_providers(cfg) if check_settings is not None else (provider_names or [])
    settings = get_settings()

    t_q0 = time.perf_counter()
    queries = generate_intelligent_queries(
        title=submission_doc.title,
        segments=submission_segments,
        max_queries=cfg.max_search_queries,
        profile=cfg.search_intensity,
        search_language=cfg.search_language,
    )
    query_gen_ms = int((time.perf_counter() - t_q0) * 1000)

    doc_keywords: set[str] = set()
    for seg in submission_segments:
        if seg.zone == "BODY":
            for w in seg.normalized_text.split():
                if len(w) >= 5:
                    doc_keywords.add(w)

    fulltext_doc_ids: set[str] = set()
    metadata_only: list[SourceRecord] = []
    access_denied = 0
    fetch_failed = 0
    queries_executed = 0
    queries_skipped = 0
    provider_responses = 0
    providers_failed: list[str] = []
    unique_urls: set[str] = set()
    pages_crawled = 0
    fulltext_fetched = 0
    fulltext_indexed = 0

    seen_candidates: set[str] = set()
    ranked_pool: list[tuple[RankedCandidate, object]] = []
    max_download_bytes = min(settings.max_upload_bytes, cfg.max_download_mb * 1024 * 1024)

    # Stage A: Concurrent Per-Provider Search
    t_search0 = time.perf_counter()
    runnable_providers: list[tuple[str, object]] = []
    for pname in active_names:
        provider = providers.get(pname)
        if provider is None:
            continue
        if hasattr(provider, "is_configured") and not provider.is_configured():
            queries_skipped += len(queries)
            continue
        runnable_providers.append((pname, provider))

    provider_batches: list[tuple[str, object, list, int]] = []
    use_query_cache = providers_override is None
    if runnable_providers and queries:
        if providers_override is None and len(runnable_providers) > 1:
            with ThreadPoolExecutor(max_workers=min(5, len(runnable_providers))) as qpool:
                futs = {
                    qpool.submit(_run_provider_queries_worker, pname, prov, queries, use_query_cache): (pname, prov)
                    for pname, prov in runnable_providers
                }
                for fut in as_completed(futs):
                    pname, prov = futs[fut]
                    _, logs, sk = fut.result()
                    provider_batches.append((pname, prov, logs, sk))
        else:
            for pname, prov in runnable_providers:
                _, logs, sk = _run_provider_queries_worker(pname, prov, queries, use_query_cache)
                provider_batches.append((pname, prov, logs, sk))

    #Deterministic ordering by active_names
    order_idx = {name: i for i, name in enumerate(active_names)}
    provider_batches.sort(key=lambda b: order_idx.get(b[0], 99))

    for pname, provider, logs, sk in provider_batches:
        queries_skipped += sk
        for qc, records, started, dur_ms, http_st, err_msg in logs:
            queries_executed += 1
            if err_msg and pname not in providers_failed:
                providers_failed.append(pname)
            if records:
                provider_responses += len(records)

            db.add(
                ProviderQuery(
                    check_id=check_id,
                    provider=pname,
                    query=qc.query[:512],
                    status="OK" if err_msg is None else "ERROR",
                    result_count=len(records),
                    http_status=http_st,
                    error=err_msg,
                    started_at=started,
                    duration_ms=dur_ms,
                )
            )

            for rec in records[:6]:
                cand_canon = canonicalize_url(rec.canonical_url or rec.url) if (rec.canonical_url or rec.url) else None
                dedup_keys = [
                    f"id:{rec.provider}:{rec.external_id}",
                    f"doi:{rec.doi.lower()}" if rec.doi else "",
                    f"url:{cand_canon}" if cand_canon else "",
                    f"title:{normalize_title_key(rec.title)}" if normalize_title_key(rec.title) else "",
                ]
                if any(k and k in seen_candidates for k in dedup_keys):
                    continue
                for k in dedup_keys:
                    if k:
                        seen_candidates.add(k)

                for u in ([rec.url, rec.oa_pdf_url] + list(rec.candidate_urls or [])):
                    if u and str(u).startswith("http"):
                        unique_urls.add(canonicalize_url(u))

                ranked = score_candidate_relevance(
                    rec,
                    doc_title=submission_doc.title,
                    doc_keywords=doc_keywords,
                    matched_query=qc.query,
                )
                ranked_pool.append((ranked, provider))

    db.flush()
    provider_search_ms = int((time.perf_counter() - t_search0) * 1000)

    ranked_pool.sort(key=lambda item: (-item[0].relevance_score, item[0].record.provider))

    # Stage B: Dedup check against DB + Bounded Concurrent Full-Text Acquisition
    t_crawl0 = time.perf_counter()
    to_fetch: list[tuple[RankedCandidate, object, list[str], str | None]] = []

    for ranked, provider in ranked_pool:
        rec = ranked.record
        cand_canon = canonicalize_url(rec.canonical_url or rec.url) if (rec.canonical_url or rec.url) else None

        if rec.doi:
            cached_doc_id = doi_resolution_cache.get(rec.doi.strip().lower())
            if cached_doc_id:
                existing_cached = db.query(Document).filter(Document.id == cached_doc_id).first()
                if existing_cached is not None:
                    fulltext_doc_ids.add(existing_cached.id)
                    db.add(
                        SourceAcquisition(
                            check_id=check_id,
                            provider=rec.provider,
                            query=ranked.matched_query[:512],
                            title=rec.title[:512],
                            authors=rec.authors,
                            year=rec.year,
                            doi=rec.doi,
                            source_url=rec.url,
                            canonical_url=existing_cached.canonical_url or cand_canon,
                            source_type=rec.source_type,
                            file_type=existing_cached.file_type,
                            license=rec.license,
                            status="FULLTEXT_INDEXED",
                            document_id=existing_cached.id,
                            duration_ms=0,
                        )
                    )
                    continue

        existing_doc = find_duplicate_source(
            db,
            doi=rec.doi,
            url=rec.url,
            canonical_url=cand_canon,
            title=rec.title,
        )
        if existing_doc is not None:
            fulltext_doc_ids.add(existing_doc.id)
            if rec.doi:
                doi_resolution_cache.set(rec.doi.strip().lower(), existing_doc.id)
            db.add(
                SourceAcquisition(
                    check_id=check_id,
                    provider=rec.provider,
                    query=ranked.matched_query[:512],
                    title=rec.title[:512],
                    authors=rec.authors,
                    year=rec.year,
                    doi=rec.doi,
                    source_url=rec.url,
                    canonical_url=existing_doc.canonical_url or cand_canon,
                    source_type=rec.source_type,
                    file_type=existing_doc.file_type,
                    license=rec.license,
                    status="FULLTEXT_INDEXED",
                    document_id=existing_doc.id,
                    duration_ms=0,
                )
            )
            continue

        urls_to_try: list[str] = []
        for u in [rec.oa_pdf_url] + list(rec.candidate_urls or []) + [rec.url]:
            if u and str(u).startswith("http") and u not in urls_to_try:
                urls_to_try.append(u)

        if ranked.relevance_label == "UNRELATED":
            metadata_only.append(rec)
            db.add(
                SourceAcquisition(
                    check_id=check_id,
                    provider=rec.provider,
                    query=ranked.matched_query[:512],
                    title=rec.title[:512],
                    authors=rec.authors,
                    year=rec.year,
                    doi=rec.doi,
                    source_url=rec.url,
                    canonical_url=cand_canon,
                    source_type=rec.source_type,
                    license=rec.license,
                    status="SEARCH_RESULT_ONLY",
                    error=f"Relevansi tidak memadai ({ranked.relevance_label}, skor={ranked.relevance_score})",
                )
            )
            continue

        if not cfg.enable_fulltext_download or not urls_to_try or rec.provider == "crossref":
            status_label = "METADATA_ONLY" if rec.provider == "crossref" or not urls_to_try else "URL_FOUND"
            metadata_only.append(rec)
            db.add(
                SourceAcquisition(
                    check_id=check_id,
                    provider=rec.provider,
                    query=ranked.matched_query[:512],
                    title=rec.title[:512],
                    authors=rec.authors,
                    year=rec.year,
                    doi=rec.doi,
                    source_url=rec.url,
                    canonical_url=cand_canon,
                    source_type=rec.source_type,
                    license=rec.license,
                    status=status_label,
                )
            )
            continue

        if len(to_fetch) >= cfg.max_crawled_urls:
            metadata_only.append(rec)
            db.add(
                SourceAcquisition(
                    check_id=check_id,
                    provider=rec.provider,
                    query=ranked.matched_query[:512],
                    title=rec.title[:512],
                    authors=rec.authors,
                    year=rec.year,
                    doi=rec.doi,
                    source_url=rec.url,
                    canonical_url=cand_canon,
                    source_type=rec.source_type,
                    license=rec.license,
                    status="URL_FOUND",
                    error="Batas maksimum URL crawl tercapai.",
                )
            )
            continue

        to_fetch.append((ranked, provider, urls_to_try, cand_canon))

    fetch_results: list[tuple[RankedCandidate, list[str], str | None, tuple]] = []
    if to_fetch:
        pages_crawled = len(to_fetch)
        use_threads = providers_override is None and len(to_fetch) > 1
        limits = httpx.Limits(max_keepalive_connections=8, max_connections=12)
        with httpx.Client(timeout=float(settings.CRAWL_TIMEOUT_SEC), limits=limits) as shared_http:
            if use_threads:
                with ThreadPoolExecutor(max_workers=min(4, len(to_fetch))) as pool:
                    fut_map = {
                        pool.submit(
                            _fetch_candidate_worker,
                            ranked.record,
                            provider,
                            urls_to_try,
                            shared_http=shared_http if providers_override is None else None,
                            enable_browser_crawler=cfg.enable_browser_crawler,
                            max_download_bytes=max_download_bytes,
                            resolve_dns=resolve_dns,
                        ): (ranked, urls_to_try, cand_canon)
                        for ranked, provider, urls_to_try, cand_canon in to_fetch
                    }
                    for fut in as_completed(fut_map):
                        ranked, urls_to_try, cand_canon = fut_map[fut]
                        fetch_results.append((ranked, urls_to_try, cand_canon, fut.result()))
            else:
                for ranked, provider, urls_to_try, cand_canon in to_fetch:
                    res = _fetch_candidate_worker(
                        ranked.record,
                        provider,
                        urls_to_try,
                        shared_http=shared_http if providers_override is None else None,
                        enable_browser_crawler=cfg.enable_browser_crawler,
                        max_download_bytes=max_download_bytes,
                        resolve_dns=resolve_dns,
                    )
                    fetch_results.append((ranked, urls_to_try, cand_canon, res))

    crawl_download_ms = int((time.perf_counter() - t_crawl0) * 1000)

    # Stage C: Text Extraction, Content-Hash Cache & Local Corpus Indexing
    t_idx0 = time.perf_counter()
    for ranked, urls_to_try, _cand_canon, res in fetch_results:
        rec = ranked.record
        fetched_bytes, fetched_type, used_pw, final_canon, acq_error, acq_status, acq_ms = res
        if fetched_bytes is not None and fetched_type is not None:
            fulltext_fetched += 1
            raw_sha = hashlib.sha256(fetched_bytes).hexdigest()
            cached_hash_doc_id = content_hash_cache.get(raw_sha)
            if cached_hash_doc_id:
                existing_h = db.query(Document).filter(Document.id == cached_hash_doc_id).first()
                if existing_h is not None:
                    fulltext_doc_ids.add(existing_h.id)
                    fulltext_indexed += 1
                    db.add(
                        SourceAcquisition(
                            check_id=check_id,
                            provider=rec.provider,
                            query=ranked.matched_query[:512],
                            title=(existing_h.title or rec.title)[:512],
                            authors=rec.authors,
                            year=rec.year,
                            doi=existing_h.doi or rec.doi,
                            source_url=rec.url or urls_to_try[0],
                            canonical_url=existing_h.canonical_url or final_canon,
                            source_type=rec.source_type,
                            file_type=fetched_type,
                            license=rec.license,
                            status="FULLTEXT_INDEXED",
                            used_playwright=used_pw,
                            document_id=existing_h.id,
                            duration_ms=acq_ms,
                        )
                    )
                    continue

            try:
                validated = validate_local_bytes(
                    f"{rec.provider}_{rec.external_id}.{fetched_type}",
                    fetched_bytes,
                    max_download_bytes,
                    allow_web_formats=True,
                )
                ext_doc = ingest_validated_upload(
                    db,
                    validated,
                    role="EXTERNAL",
                    title=rec.title,
                    authors=rec.authors,
                    year=rec.year,
                    doi=rec.doi,
                    url=rec.url or urls_to_try[0],
                    canonical_url=final_canon,
                    license_name=rec.license,
                    indexing_status="FULLTEXT_INDEXED",
                    source_type=rec.source_type,
                    access_status="INDEXED_LOCALLY",
                    provider=rec.provider,
                    external_id=rec.external_id,
                )
                fulltext_doc_ids.add(ext_doc.id)
                fulltext_indexed += 1
                content_hash_cache.set(raw_sha, ext_doc.id)
                if ext_doc.doi:
                    doi_resolution_cache.set(ext_doc.doi.strip().lower(), ext_doc.id)
                db.add(
                    SourceAcquisition(
                        check_id=check_id,
                        provider=rec.provider,
                        query=ranked.matched_query[:512],
                        title=(ext_doc.title or rec.title)[:512],
                        authors=rec.authors,
                        year=rec.year,
                        doi=ext_doc.doi or rec.doi,
                        source_url=rec.url or urls_to_try[0],
                        canonical_url=ext_doc.canonical_url or final_canon,
                        source_type=rec.source_type,
                        file_type=fetched_type,
                        license=rec.license,
                        status="FULLTEXT_INDEXED",
                        used_playwright=used_pw,
                        document_id=ext_doc.id,
                        duration_ms=acq_ms,
                    )
                )
                continue
            except Exception as exc:
                fetch_failed += 1
                acq_status = "CRAWL_FAILED"
                acq_error = f"Gagal ekstraksi/indeksasi: {exc}"
        else:
            if acq_status == "ACCESS_RESTRICTED":
                access_denied += 1
                rec.access_status = "ACCESS_DENIED"
            else:
                fetch_failed += 1
                rec.access_status = "FETCH_FAILED"

        metadata_only.append(rec)
        db.add(
            SourceAcquisition(
                check_id=check_id,
                provider=rec.provider,
                query=ranked.matched_query[:512],
                title=rec.title[:512],
                authors=rec.authors,
                year=rec.year,
                doi=rec.doi,
                source_url=rec.url,
                canonical_url=final_canon,
                source_type=rec.source_type,
                license=rec.license,
                status=acq_status,
                used_playwright=used_pw,
                error=acq_error,
                duration_ms=acq_ms,
            )
        )

    indexing_ms = int((time.perf_counter() - t_idx0) * 1000)
    db.commit()

    relevance_counts: dict[str, int] = {}
    for rc, _ in ranked_pool:
        relevance_counts[rc.relevance_label] = relevance_counts.get(rc.relevance_label, 0) + 1

    search_coverage = {
        "queries_generated": len(queries),
        "total_search_queries": queries_executed,
        "queries_skipped": queries_skipped,
        "total_provider_responses": provider_responses,
        "total_unique_urls_found": len(unique_urls),
        "total_pages_crawled": pages_crawled,
        "total_fulltext_fetched": fulltext_fetched,
        "total_fulltext_indexed": fulltext_indexed,
        "total_metadata_only": len(metadata_only),
        "total_inaccessible_sources": access_denied,
        "total_failed_crawling": fetch_failed,
        "providers_failed": providers_failed,
        "relevance_breakdown": relevance_counts,
        "generated_queries": [
            {"query": q.query, "kind": q.kind, "chapter": q.chapter, "score": q.score, "level": q.level}
            for q in queries
        ],
    }

    return DiscoverySummary(
        external_fulltext_doc_ids=fulltext_doc_ids,
        metadata_only_records=metadata_only,
        access_denied_count=access_denied,
        fetch_failed_count=fetch_failed,
        queries_executed=queries_executed,
        search_coverage=search_coverage,
        stage_timings_ms={
            "query_generation_ms": query_gen_ms,
            "provider_search_ms": provider_search_ms,
            "crawling_and_download_ms": crawl_download_ms,
            "extraction_and_indexing_ms": indexing_ms,
        },
    )
