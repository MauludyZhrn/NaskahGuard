"""Provider status, user-runnable live diagnostics, and Source Discovery Monitor endpoints (Phase 9)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.engine.noplag_adapter import NoplagAdapter
from app.models import Check, Document, OAIRepository, ProviderQuery, SourceAcquisition
from app.security import require_auth
from app.sources.arxiv import ArxivProvider
from app.sources.browser_extractor import IsolatedPlaywrightExtractor
from app.sources.crossref import CrossrefProvider
from app.sources.doaj import DOAJProvider
from app.sources.europe_pmc import EuropePMCProvider
from app.sources.oai_pmh import OAIPMHClient
from app.sources.openalex import OpenAlexProvider
from app.sources.web_search import OfficialWebSearchAPIProvider, SearXNGWebSearchProvider

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(require_auth)])

# In-memory diagnostic snapshot populated ONLY when a real health check or live query runs
_DIAGNOSTIC_STATE: dict[str, dict[str, Any]] = {}


def _build_provider_list(db: Session) -> list[dict[str, Any]]:
    settings = get_settings()
    local_count = db.query(func.count(Document.id)).filter(Document.role == "CORPUS").scalar() or 0
    ext_count = db.query(func.count(Document.id)).filter(Document.role == "EXTERNAL").scalar() or 0
    oai_count = db.query(func.count(OAIRepository.id)).scalar() or 0
    noplag = NoplagAdapter().health()

    searx = SearXNGWebSearchProvider()
    web_api = OfficialWebSearchAPIProvider()
    pw_installed = importlib.util.find_spec("playwright") is not None

    all_pq = db.query(ProviderQuery).order_by(ProviderQuery.started_at.desc()).limit(500).all()
    telemetry: dict[str, dict[str, Any]] = {}
    for pq in all_pq:
        st = telemetry.setdefault(
            pq.provider,
            {
                "request_count": 0,
                "result_count": 0,
                "timeout_count": 0,
                "error_count": 0,
                "last_checked": None,
                "last_successful_request": None,
                "last_error": None,
            },
        )
        st["request_count"] += 1
        st["result_count"] += int(pq.result_count or 0)
        if st["last_checked"] is None and pq.started_at:
            st["last_checked"] = pq.started_at.isoformat()
        if pq.status == "OK":
            if st["last_successful_request"] is None and pq.started_at:
                st["last_successful_request"] = pq.started_at.isoformat()
        else:
            st["error_count"] += 1
            if st["last_error"] is None and pq.error:
                st["last_error"] = pq.error
            if pq.error and "timeout" in pq.error.lower():
                st["timeout_count"] += 1

    def _enrich(item: dict[str, Any], configured: bool, *, always_local: bool = False) -> dict[str, Any]:
        pid = item["id"]
        t = telemetry.get(pid, {})
        diag = _DIAGNOSTIC_STATE.get(pid, {})
        req_cnt = t.get("request_count", 0)
        err_cnt = t.get("error_count", 0)

        # Never claim reachable=True unless verified by local DB or an explicit check/query!
        if always_local:
            reachable: bool | None = True
            health = "healthy"
        elif not configured:
            reachable = False
            health = "unconfigured"
        elif "reachable" in diag:
            reachable = bool(diag["reachable"])
            health = "healthy" if reachable else "degraded"
        elif req_cnt > 0:
            reachable = err_cnt < req_cnt
            health = "healthy" if reachable else "degraded"
        else:
            reachable = None
            health = "ready"

        item["configured"] = configured
        item["enabled"] = bool(item.get("default_enabled"))
        item["reachable"] = reachable
        item["last_checked"] = diag.get("last_checked") or t.get("last_checked")
        item["health"] = health
        item["request_count"] = req_cnt
        item["result_count"] = t.get("result_count", 0)
        item["timeout_count"] = t.get("timeout_count", 0)
        item["last_successful_request"] = diag.get("last_successful_request") or t.get("last_successful_request")
        item["last_error"] = diag.get("last_error") if "last_error" in diag else t.get("last_error")
        if diag.get("status_override"):
            item["status"] = diag["status_override"]
        return item

    return [
        _enrich({
            "id": "local_corpus",
            "name": "Korpus Lokal (SQLite)",
            "type": "local",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": local_count,
            "rate_limit": "Tidak ada batas",
            "status": f"Aktif ({local_count} dokumen lokal)",
        }, True, always_local=True),
        _enrich({
            "id": "openalex",
            "name": "OpenAlex (Full-Text & OA)",
            "type": "academic",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": ext_count,
            "rate_limit": "~10 req/dtk, 100k/hari (polite pool mailto)",
            "status": "Terkonfigurasi (Belum diuji konektivitas live)",
        }, True),
        _enrich({
            "id": "europe_pmc",
            "name": "Europe PMC (REST + Full-Text XML)",
            "type": "academic",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": 0,
            "rate_limit": "API REST resmi EMBL-EBI",
            "status": "Terkonfigurasi (Belum diuji konektivitas live)",
        }, True),
        _enrich({
            "id": "arxiv",
            "name": "arXiv",
            "type": "academic",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": 0,
            "rate_limit": "Minimal jeda 3 detik/permintaan (maks 6 kueri/cek)",
            "status": "Terkonfigurasi (Belum diuji konektivitas live)",
        }, True),
        _enrich({
            "id": "doaj",
            "name": "DOAJ (Directory of Open Access Journals)",
            "type": "academic",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": 0,
            "rate_limit": "API publik tanpa kunci (Open Access)",
            "status": "Terkonfigurasi (Belum diuji konektivitas live)",
        }, True),
        _enrich({
            "id": "crossref",
            "name": "Crossref",
            "type": "academic",
            "default_enabled": True,
            "full_text_capable": False,
            "indexed_documents": 0,
            "rate_limit": "Polite pool User-Agent mailto",
            "status": "Terkonfigurasi (Metadata & DOI — METADATA_ONLY)",
        }, True),
        _enrich({
            "id": "searxng",
            "name": "General Web Search (SearXNG Self-Hosted)",
            "type": "web",
            "default_enabled": searx.is_configured(),
            "full_text_capable": True,
            "rate_limit": "Mengikuti instance SearXNG lokal/pribadi",
            "status": searx.status_message() if searx.is_configured() else "NOT_CONFIGURED (Atur NG_SEARXNG_URL / docker-compose.searxng.yml)",
        }, searx.is_configured()),
        _enrich({
            "id": "web_api",
            "name": "General Web Search (Official JSON API)",
            "type": "web",
            "default_enabled": web_api.is_configured(),
            "full_text_capable": True,
            "rate_limit": "Mengikuti kredensial API resmi",
            "status": web_api.status_message() if web_api.is_configured() else "NOT_CONFIGURED (Kredensial API belum diatur)",
        }, web_api.is_configured()),
        _enrich({
            "id": "playwright_crawler",
            "name": "Playwright Chromium Public-Web Crawler",
            "type": "crawler",
            "default_enabled": settings.PLAYWRIGHT_ENABLED and pw_installed,
            "full_text_capable": True,
            "rate_limit": f"Jeda {settings.CRAWL_DOMAIN_DELAY_SEC}s/domain · Konteks Terisolasi + SSRF Guard",
            "status": "Terkonfigurasi (Klik Uji Konektivitas untuk memverifikasi browser)" if pw_installed else "NOT_CONFIGURED (Playwright belum terpasang)",
        }, pw_installed and settings.PLAYWRIGHT_ENABLED),
        _enrich({
            "id": "oai_pmh",
            "name": "OAI-PMH Harvester (Repositori Akademik)",
            "type": "repository",
            "default_enabled": oai_count > 0,
            "full_text_capable": True,
            "indexed_documents": oai_count,
            "rate_limit": "Panen bertahap via resumptionToken & datestamp",
            "status": f"{oai_count} repositori terdaftar" if oai_count > 0 else "NOT_CONFIGURED (0 repositori OAI-PMH terdaftar)",
        }, oai_count > 0),
        _enrich({
            "id": "noplag_engine",
            "name": "Noplag Engine (Internal Loopback Adapter)",
            "type": "internal_service",
            "default_enabled": False,
            "full_text_capable": True,
            "status": "Terhubung" if noplag.get("reachable") else "NOT_CONFIGURED (Opsional loopback service)",
            "details": noplag,
        }, bool(noplag.get("configured"))),
    ]


@router.get("")
def list_providers(db: Session = Depends(get_db)) -> dict[str, Any]:
    recent_queries = db.query(ProviderQuery).order_by(ProviderQuery.started_at.desc()).limit(25).all()
    return {
        "providers": _build_provider_list(db),
        "recent_queries": [
            {
                "id": pq.id,
                "check_id": pq.check_id,
                "provider": pq.provider,
                "query": pq.query,
                "status": pq.status,
                "result_count": pq.result_count,
                "http_status": pq.http_status,
                "error": pq.error,
                "duration_ms": pq.duration_ms,
                "started_at": pq.started_at.isoformat() if pq.started_at else None,
            }
            for pq in recent_queries
        ],
    }


@router.post("/diagnostics")
def run_provider_diagnostics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run real non-private connectivity & browser health diagnostics across configured providers."""
    checked_at = datetime.now(timezone.utc).isoformat()
    public_probe_query = "winnowing document fingerprinting"

    search_targets: list[tuple[str, Any]] = [
        ("openalex", OpenAlexProvider()),
        ("europe_pmc", EuropePMCProvider()),
        ("arxiv", ArxivProvider()),
        ("doaj", DOAJProvider()),
        ("crossref", CrossrefProvider()),
    ]
    searx = SearXNGWebSearchProvider()
    if searx.is_configured():
        search_targets.append(("searxng", searx))
    web_api = OfficialWebSearchAPIProvider()
    if web_api.is_configured():
        search_targets.append(("web_api", web_api))

    def _probe_search(pid: str, inst: Any) -> tuple[str, dict[str, Any]]:
        res = inst.search(public_probe_query)
        err = getattr(inst, "last_error", None)
        ok = err is None
        return pid, {
            "reachable": ok,
            "last_checked": checked_at,
            "last_successful_request": checked_at if ok else _DIAGNOSTIC_STATE.get(pid, {}).get("last_successful_request"),
            "last_error": err,
            "status_override": f"Terverifikasi aktif ({len(res)} hasil uji publik)" if ok else f"Tidak terjangkau ({err})",
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_probe_search, pid, inst) for pid, inst in search_targets]
        pw_fut = pool.submit(IsolatedPlaywrightExtractor().health_check_sync)
        for f in as_completed(futs):
            pid, snap = f.result()
            _DIAGNOSTIC_STATE[pid] = snap

        pw_res = pw_fut.result()
        _DIAGNOSTIC_STATE["playwright_crawler"] = {
            "reachable": bool(pw_res.get("reachable")),
            "last_checked": checked_at,
            "last_successful_request": checked_at if pw_res.get("reachable") else None,
            "last_error": None if pw_res.get("reachable") else pw_res.get("message"),
            "status_override": pw_res.get("message"),
        }

    # Probe first registered OAI-PMH repo if any
    first_oai = db.query(OAIRepository).first()
    if first_oai is not None:
        try:
            ident = OAIPMHClient().identify(first_oai.base_url)
            _DIAGNOSTIC_STATE["oai_pmh"] = {
                "reachable": True,
                "last_checked": checked_at,
                "last_successful_request": checked_at,
                "last_error": None,
                "status_override": f"Terverifikasi ({ident.get('repositoryName') or first_oai.name})",
            }
        except Exception as exc:
            _DIAGNOSTIC_STATE["oai_pmh"] = {
                "reachable": False,
                "last_checked": checked_at,
                "last_error": str(exc),
                "status_override": f"Gagal Identify OAI-PMH: {exc}",
            }

    return {
        "checked_at": checked_at,
        "providers": _build_provider_list(db),
    }


@router.get("/monitor")
def discovery_monitor(check_id: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Live Source Discovery Monitor endpoint returning actual query, URL, download, and indexing telemetry."""
    q_acq = db.query(SourceAcquisition)
    q_pq = db.query(ProviderQuery)
    if check_id:
        q_acq = q_acq.filter(SourceAcquisition.check_id == check_id)
        q_pq = q_pq.filter(ProviderQuery.check_id == check_id)

    acquisitions = q_acq.order_by(SourceAcquisition.id.desc()).limit(100).all()
    queries = q_pq.order_by(ProviderQuery.id.desc()).limit(60).all()
    recent_checks = db.query(Check).order_by(Check.created_at.desc()).limit(10).all()

    status_counts: dict[str, int] = {}
    for a in acquisitions:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1

    return {
        "summary": {
            "total_queries": len(queries),
            "failed_queries": sum(1 for q in queries if q.status != "OK"),
            "total_acquisitions": len(acquisitions),
            "status_counts": status_counts,
        },
        "recent_checks": [
            {
                "id": c.id,
                "report_number": c.report_number,
                "status": c.status,
                "stage": c.stage,
                "progress": c.progress,
            }
            for c in recent_checks
        ],
        "queries": [
            {
                "id": q.id,
                "check_id": q.check_id,
                "provider": q.provider,
                "query": q.query,
                "status": q.status,
                "result_count": q.result_count,
                "http_status": q.http_status,
                "error": q.error,
                "duration_ms": q.duration_ms,
                "started_at": q.started_at.isoformat() if q.started_at else None,
            }
            for q in queries
        ],
        "acquisitions": [
            {
                "id": a.id,
                "check_id": a.check_id,
                "provider": a.provider,
                "query": a.query,
                "title": a.title,
                "source_url": a.source_url,
                "canonical_url": a.canonical_url,
                "doi": a.doi,
                "file_type": a.file_type,
                "status": a.status,
                "used_playwright": a.used_playwright,
                "document_id": a.document_id,
                "error": a.error,
                "duration_ms": a.duration_ms,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in acquisitions
        ],
    }
