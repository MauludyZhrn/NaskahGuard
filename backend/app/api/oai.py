"""User-managed OAI-PMH Academic Repository Registry, 8-Stage Wizard & Harvester API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.db import get_db
from app.models import (
    CheckSource,
    Document,
    OAIHarvestLog,
    OAIHarvestRecord,
    OAIHarvestRun,
    OAIRepository,
    RepositoryCatalogEntry,
)
from app.security import enforce_rate_limit, require_auth
from app.sources.oai_catalog import (
    add_catalog_entry,
    ensure_catalog_seeded,
    promote_catalog_entry_to_personal,
    serialize_catalog_entry,
    test_catalog_entry,
)
from app.sources.oai_pmh import (
    OFFICIAL_REFERENCE_ENDPOINTS,
    OAIPMHProtocolError,
    auto_detect_oai_endpoint,
    detect_platform_from_url,
    get_repository_funnel,
    harvest_oai_repository,
    normalize_repo_type,
    platform_label,
    preview_oai_records,
    retry_failed_oai_records,
    run_connection_wizard,
)
from app.sources.ssrf import SSRFError, validate_public_url

router = APIRouter(prefix="/oai", tags=["oai-pmh"], dependencies=[Depends(require_auth)])


class OAIRepoCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    base_url: str = Field(..., min_length=8, max_length=1024)
    repo_type: str = Field(default="other", max_length=32)
    metadata_prefix: str = Field(default="oai_dc", min_length=2, max_length=64)
    selected_set: str | None = Field(default=None, max_length=255)
    enabled: bool = True
    rate_limit_delay_sec: float = Field(default=0.8, ge=0.0, le=30.0)
    request_timeout_sec: int = Field(default=20, ge=5, le=120)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    keyword_filter: str | None = Field(default=None, max_length=255)
    doc_type_filter: str | None = Field(default=None, max_length=128)
    max_downloads: int = Field(default=10, ge=0, le=200)
    test_report: dict[str, Any] | None = None


class OAIRepoUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    base_url: str | None = Field(default=None, min_length=8, max_length=1024)
    repo_type: str | None = Field(default=None, max_length=32)
    metadata_prefix: str | None = Field(default=None, min_length=2, max_length=64)
    selected_set: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    rate_limit_delay_sec: float | None = Field(default=None, ge=0.0, le=30.0)
    request_timeout_sec: int | None = Field(default=None, ge=5, le=120)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    keyword_filter: str | None = Field(default=None, max_length=255)
    doc_type_filter: str | None = Field(default=None, max_length=128)
    max_downloads: int | None = Field(default=None, ge=0, le=200)


class OAIScheduleUpdate(BaseModel):
    schedule_enabled: bool = False
    schedule_interval_hours: int = Field(default=24, ge=1, le=720)


class OAICatalogCreateRequest(BaseModel):
    university: str = Field(..., min_length=2, max_length=255)
    name: str = Field(..., min_length=2, max_length=255)
    base_url: str = Field(..., min_length=8, max_length=1024)
    platform: str = Field(default="other", max_length=32)
    description: str | None = Field(default=None, max_length=500)


class OAICatalogAddPersonalRequest(BaseModel):
    selected_set: str | None = Field(default=None, max_length=255)
    metadata_prefix: str | None = Field(default=None, max_length=64)


class OAIAutoDetectRequest(BaseModel):
    base_url: str = Field(..., min_length=5, max_length=1024)


class OAITestConnectionRequest(BaseModel):
    base_url: str = Field(..., min_length=5, max_length=1024)
    metadata_prefix: str | None = Field(default="oai_dc", max_length=64)
    set_spec: str | None = Field(default=None, max_length=255)
    probe_pdf: bool = False
    auto_detect_fallback: bool = False


class OAIPreviewRequest(BaseModel):
    metadata_prefix: str | None = Field(default=None, max_length=64)
    set_spec: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=5, ge=1, le=20)


class OAIHarvestRequest(BaseModel):
    max_records: int = Field(default=15, ge=1, le=200)
    max_downloads: int | None = Field(default=None, ge=0, le=200)
    download_pdfs: bool = True
    resume: bool = False
    reset_cursor: bool = False
    incremental: bool = True
    set_spec: str | None = Field(default=None, max_length=255)
    metadata_prefix: str | None = Field(default=None, max_length=64)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    keyword_filter: str | None = Field(default=None, max_length=255)
    doc_type_filter: str | None = Field(default=None, max_length=128)


class OAIRetryRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


def _serialize_repo(r: OAIRepository, db: Session | None = None) -> dict[str, Any]:
    platform = r.platform_detected or normalize_repo_type(r.repo_type)
    funnel = get_repository_funnel(db, r) if db is not None else {
        "metadata_found": r.records_harvested,
        "metadata_saved": r.metadata_saved_count or r.records_harvested,
        "pdf_urls_found": r.pdf_urls_found_count,
        "pdf_accessible": r.pdf_accessible_count,
        "fulltext_extracted": r.fulltext_extracted_count,
        "document_indexed": r.fulltext_indexed,
        "document_compared": 0,
        "failed_records": r.failed_records_count,
    }
    return {
        "id": r.id,
        "name": r.name,
        "base_url": r.base_url,
        "repo_type": r.repo_type,
        "platform_detected": platform,
        "platform_label": platform_label(platform),
        "enabled": r.enabled,
        "identified_name": r.identified_name,
        "metadata_prefix": r.metadata_prefix,
        "selected_set": r.selected_set,
        "supported_formats": r.supported_formats or [],
        "available_sets": r.available_sets or [],
        "has_resumption_token": bool(r.resumption_token),
        "harvest_state": r.harvest_state or "IDLE",
        "last_test_report": r.last_test_report,
        "last_harvested_at": r.last_harvested_at.isoformat() if r.last_harvested_at else None,
        "last_datestamp": r.last_datestamp,
        "records_harvested": r.records_harvested,
        "metadata_saved_count": r.metadata_saved_count,
        "pdf_urls_found_count": r.pdf_urls_found_count,
        "pdf_accessible_count": r.pdf_accessible_count,
        "fulltext_extracted_count": r.fulltext_extracted_count,
        "fulltext_indexed": r.fulltext_indexed,
        "failed_records_count": r.failed_records_count,
        "rate_limit_delay_sec": r.rate_limit_delay_sec,
        "request_timeout_sec": r.request_timeout_sec,
        "year_from": r.year_from,
        "year_to": r.year_to,
        "keyword_filter": r.keyword_filter,
        "doc_type_filter": r.doc_type_filter,
        "max_downloads": r.max_downloads,
        "schedule_enabled": bool(r.schedule_enabled),
        "schedule_interval_hours": r.schedule_interval_hours or 24,
        "next_scheduled_at": r.next_scheduled_at.isoformat() if r.next_scheduled_at else None,
        "funnel": funnel,
        "status": r.status,
        "last_error": r.last_error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _serialize_run(run: OAIHarvestRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "repository_id": run.repository_id,
        "trigger_mode": run.trigger_mode,
        "status": run.status,
        "set_spec": run.set_spec,
        "metadata_prefix": run.metadata_prefix,
        "filters_snapshot": run.filters_snapshot or {},
        "records_scanned": run.records_scanned,
        "records_matched_filter": run.records_matched_filter,
        "records_harvested": run.records_harvested,
        "fulltext_indexed": run.fulltext_indexed,
        "metadata_only": run.metadata_only,
        "failed_records": run.failed_records,
        "duplicates_skipped": run.duplicates_skipped,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _serialize_record(rec: OAIHarvestRecord) -> dict[str, Any]:
    return {
        "id": rec.id,
        "repository_id": rec.repository_id,
        "oai_identifier": rec.oai_identifier,
        "datestamp": rec.datestamp,
        "set_spec": rec.set_spec,
        "metadata_prefix": rec.metadata_prefix,
        "deleted": rec.deleted,
        "title": rec.title,
        "authors": rec.authors or [],
        "year": rec.year,
        "doi": rec.doi,
        "doc_type": rec.doc_type,
        "subjects": rec.subjects or [],
        "rights": rec.rights,
        "landing_urls": rec.landing_urls or [],
        "pdf_urls": rec.pdf_urls or [],
        "status": rec.status,
        "document_id": rec.document_id,
        "error_code": rec.error_code,
        "error_message": rec.error_message,
        "attempts": rec.attempts,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


def _serialize_log(log: OAIHarvestLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "repository_id": log.repository_id,
        "level": log.level,
        "stage": log.stage,
        "http_status": log.http_status,
        "error_code": log.error_code,
        "message": log.message,
        "details": log.details or {},
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/reference-endpoints")
def get_reference_endpoints() -> list[dict[str, str]]:
    """Return official public OAI-PMH endpoints suitable for testing (never fabricated campus URLs)."""
    return OFFICIAL_REFERENCE_ENDPOINTS


@router.get("/catalog")
def list_repository_catalog(
    q: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List searchable Indonesian & public academic repository discovery catalog."""
    ensure_catalog_seeded(db)
    query = db.query(RepositoryCatalogEntry)
    if platform and platform != "ALL":
        query = query.filter(RepositoryCatalogEntry.platform == normalize_repo_type(platform))
    if status_filter and status_filter != "ALL":
        query = query.filter(RepositoryCatalogEntry.oai_status == status_filter)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (RepositoryCatalogEntry.university.ilike(like))
            | (RepositoryCatalogEntry.name.ilike(like))
            | (RepositoryCatalogEntry.base_url.ilike(like))
        )
    entries = query.order_by(RepositoryCatalogEntry.university.asc(), RepositoryCatalogEntry.name.asc()).all()
    personal_urls = {row[0] for row in db.query(OAIRepository.base_url).all()}
    return {
        "total": len(entries),
        "items": [serialize_catalog_entry(e, personal_urls=personal_urls) for e in entries],
    }


@router.post("/catalog", status_code=status.HTTP_201_CREATED)
def add_repository_to_catalog(
    body: OAICatalogCreateRequest,
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_catalog_seeded(db)
    try:
        entry = add_catalog_entry(
            db,
            university=body.university,
            name=body.name,
            base_url=body.base_url,
            platform=body.platform,
            description=body.description,
        )
    except SSRFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    personal_urls = {row[0] for row in db.query(OAIRepository.base_url).all()}
    log_audit(db, actor=actor, action="ADD_OAI_CATALOG", target_type="oai_catalog", target_id=entry.id)
    return serialize_catalog_entry(entry, personal_urls=personal_urls)


@router.post("/catalog/{catalog_id}/test")
def test_catalog_repository(
    catalog_id: str,
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    entry = db.query(RepositoryCatalogEntry).filter(RepositoryCatalogEntry.id == catalog_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entri katalog repositori tidak ditemukan.")
    entry, wizard = test_catalog_entry(db, entry)
    personal_urls = {row[0] for row in db.query(OAIRepository.base_url).all()}
    return {
        "entry": serialize_catalog_entry(entry, personal_urls=personal_urls),
        "wizard": wizard,
    }


@router.post("/catalog/{catalog_id}/add")
def add_catalog_entry_to_personal(
    catalog_id: str,
    body: OAICatalogAddPersonalRequest | None = Body(default=None),
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    entry = db.query(RepositoryCatalogEntry).filter(RepositoryCatalogEntry.id == catalog_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entri katalog repositori tidak ditemukan.")
    req = body or OAICatalogAddPersonalRequest()
    repo, created_new = promote_catalog_entry_to_personal(
        db,
        entry,
        selected_set=req.selected_set,
        metadata_prefix=req.metadata_prefix,
    )
    if created_new:
        log_audit(db, actor=actor, action="ADD_OAI_REPO_FROM_CATALOG", target_type="oai_repository", target_id=repo.id)
    return {"created": created_new, "repository": _serialize_repo(repo, db)}


@router.post("/auto-detect")
def auto_detect_repository_endpoint(
    body: OAIAutoDetectRequest,
    _rl: None = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    return auto_detect_oai_endpoint(body.base_url.strip())


@router.post("/test-connection")
def test_oai_connection_wizard(
    body: OAITestConnectionRequest,
    _rl: None = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Run the 8-stage OAI-PMH connection wizard BEFORE saving a repository."""
    report = run_connection_wizard(
        body.base_url.strip(),
        metadata_prefix=body.metadata_prefix,
        set_spec=body.set_spec or None,
        probe_pdf=body.probe_pdf,
    )
    if not report["ok"] and body.auto_detect_fallback:
        suggestion = auto_detect_oai_endpoint(body.base_url.strip())
        report["auto_detect_suggestion"] = suggestion if suggestion.get("found") else None
    return report


@router.get("/repositories")
def list_oai_repositories(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.query(OAIRepository).order_by(OAIRepository.created_at.desc()).all()
    return [_serialize_repo(r, db) for r in rows]


@router.get("/repositories/{repo_id}")
def get_oai_repository(repo_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    return _serialize_repo(repo, db)


@router.post("/repositories", status_code=status.HTTP_201_CREATED)
def add_oai_repository(
    body: OAIRepoCreate,
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        clean_url = validate_public_url(body.base_url, resolve_dns=False)
    except SSRFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.query(OAIRepository).filter(OAIRepository.base_url == clean_url).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Base URL repositori OAI-PMH sudah terdaftar.")

    norm_type = normalize_repo_type(body.repo_type)
    inferred_platform = detect_platform_from_url(clean_url)
    if norm_type == "other" and inferred_platform != "other":
        norm_type = inferred_platform

    repo = OAIRepository(
        name=body.name.strip(),
        base_url=clean_url,
        repo_type=norm_type,
        platform_detected=inferred_platform if inferred_platform != "other" else norm_type,
        metadata_prefix=body.metadata_prefix.strip() or "oai_dc",
        selected_set=(body.selected_set or "").strip() or None,
        enabled=body.enabled,
        rate_limit_delay_sec=body.rate_limit_delay_sec,
        request_timeout_sec=body.request_timeout_sec,
        status="UNVERIFIED",
        harvest_state="IDLE",
        updated_at=datetime.now(timezone.utc),
    )

    if isinstance(body.test_report, dict):
        repo.last_test_report = body.test_report
        if body.test_report.get("identified_name"):
            repo.identified_name = str(body.test_report["identified_name"])[:500]
        if body.test_report.get("platform_detected"):
            repo.platform_detected = str(body.test_report["platform_detected"])[:32]
        if isinstance(body.test_report.get("supported_formats"), list):
            repo.supported_formats = body.test_report["supported_formats"]
        if isinstance(body.test_report.get("available_sets"), list):
            repo.available_sets = body.test_report["available_sets"]
        if body.test_report.get("ok"):
            repo.status = "VERIFIED"

    db.add(repo)
    db.flush()
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="INFO",
            stage="CREATE",
            message=f"Repositori '{repo.name}' ditambahkan ({clean_url}).",
        )
    )
    db.commit()
    db.refresh(repo)
    log_audit(
        db,
        actor=actor,
        action="ADD_OAI_REPO",
        target_type="oai_repository",
        target_id=repo.id,
        details={"base_url": clean_url, "repo_type": repo.repo_type},
    )
    return _serialize_repo(repo, db)


@router.put("/repositories/{repo_id}")
def update_oai_repository(
    repo_id: str,
    body: OAIRepoUpdate,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")

    if body.base_url is not None:
        try:
            clean_url = validate_public_url(body.base_url, resolve_dns=False)
        except SSRFError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if clean_url != repo.base_url:
            dup = (
                db.query(OAIRepository)
                .filter(OAIRepository.base_url == clean_url, OAIRepository.id != repo.id)
                .first()
            )
            if dup is not None:
                raise HTTPException(status_code=409, detail="Base URL repositori OAI-PMH sudah digunakan repositori lain.")
            repo.base_url = clean_url
            repo.status = "UNVERIFIED"
            repo.resumption_token = None

    if body.name is not None:
        repo.name = body.name.strip()
    if body.repo_type is not None:
        repo.repo_type = normalize_repo_type(body.repo_type)
    if body.metadata_prefix is not None:
        new_prefix = body.metadata_prefix.strip()
        if new_prefix != repo.metadata_prefix:
            repo.metadata_prefix = new_prefix
            repo.resumption_token = None
    if body.selected_set is not None:
        new_set = body.selected_set.strip() or None
        if new_set != repo.selected_set:
            repo.selected_set = new_set
            repo.resumption_token = None
    if body.enabled is not None:
        repo.enabled = body.enabled
    if body.rate_limit_delay_sec is not None:
        repo.rate_limit_delay_sec = body.rate_limit_delay_sec
    if body.request_timeout_sec is not None:
        repo.request_timeout_sec = body.request_timeout_sec
    if body.year_from is not None:
        repo.year_from = body.year_from
    if body.year_to is not None:
        repo.year_to = body.year_to
    if body.keyword_filter is not None:
        repo.keyword_filter = body.keyword_filter.strip() or None
    if body.doc_type_filter is not None:
        repo.doc_type_filter = body.doc_type_filter.strip() or None
    if body.max_downloads is not None:
        repo.max_downloads = body.max_downloads

    repo.updated_at = datetime.now(timezone.utc)
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="INFO",
            stage="UPDATE",
            message=f"Pengaturan repositori diperbarui (format: {repo.metadata_prefix}, koleksi: {repo.selected_set or 'Semua'}).",
        )
    )
    db.commit()
    db.refresh(repo)
    log_audit(db, actor=actor, action="UPDATE_OAI_REPO", target_type="oai_repository", target_id=repo.id)
    return _serialize_repo(repo, db)


@router.post("/repositories/{repo_id}/verify")
def verify_oai_repository(repo_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")

    report = run_connection_wizard(
        repo.base_url,
        metadata_prefix=repo.metadata_prefix,
        set_spec=repo.selected_set,
        probe_pdf=False,
        timeout_sec=float(repo.request_timeout_sec or 20),
    )

    repo.last_test_report = report
    repo.platform_detected = report.get("platform_detected") or repo.platform_detected
    if report.get("identified_name"):
        repo.identified_name = report["identified_name"][:500]
    if report.get("supported_formats"):
        repo.supported_formats = report["supported_formats"]
    if report.get("available_sets") is not None:
        repo.available_sets = report["available_sets"]

    if report["ok"]:
        repo.status = "VERIFIED"
        repo.last_error = None
        if report.get("recommended_prefix"):
            repo.metadata_prefix = report["recommended_prefix"]
        db.add(
            OAIHarvestLog(
                repository_id=repo.id,
                level="INFO",
                stage="VERIFY",
                message=f"Uji koneksi 8 tahap selesai ({report['overall_status']}): {repo.identified_name or repo.name}.",
                details=report.get("summary_counts"),
            )
        )
        repo.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(repo)
        return {
            "repository": _serialize_repo(repo, db),
            "wizard": report,
            "identify": report.get("identify") or {},
            "formats": report.get("supported_formats") or [],
        }

    failed_stage = next((s for s in report["stages"] if s["status"] == "FAIL"), None)
    err_msg = (failed_stage or {}).get("message") or "Verifikasi OAI-PMH gagal."
    err_code = (failed_stage or {}).get("error_code") or "VERIFY_FAILED"
    http_st = (failed_stage or {}).get("http_status")
    repo.status = "ERROR"
    repo.last_error = f"[{err_code}] {err_msg}"
    repo.updated_at = datetime.now(timezone.utc)
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="ERROR",
            stage="VERIFY",
            http_status=http_st,
            error_code=err_code,
            message=err_msg,
            details={"suggestion": (failed_stage or {}).get("suggestion")},
        )
    )
    db.commit()
    raise HTTPException(
        status_code=502,
        detail=f"Gagal memverifikasi OAI-PMH ({err_code}): {err_msg}",
    )


@router.post("/repositories/{repo_id}/preview")
def preview_oai_repository_metadata(
    repo_id: str,
    body: OAIPreviewRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    req = body or OAIPreviewRequest()
    try:
        return preview_oai_records(
            repo.base_url,
            metadata_prefix=req.metadata_prefix or repo.metadata_prefix or "oai_dc",
            set_spec=req.set_spec if req.set_spec is not None else repo.selected_set,
            limit=req.limit,
            timeout_sec=float(repo.request_timeout_sec or 20),
        )
    except OAIPMHProtocolError as exc:
        raise HTTPException(status_code=502, detail=f"[{exc.error_code}] {exc.message}") from exc


@router.post("/repositories/{repo_id}/harvest")
def trigger_oai_harvest(
    repo_id: str,
    body: OAIHarvestRequest | None = Body(default=None),
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    req = body or OAIHarvestRequest()
    try:
        summary = harvest_oai_repository(
            db,
            repo,
            max_records=req.max_records,
            max_downloads=req.max_downloads,
            download_pdfs=req.download_pdfs,
            resume=req.resume,
            reset_cursor=req.reset_cursor,
            incremental=req.incremental,
            set_spec=req.set_spec,
            metadata_prefix=req.metadata_prefix,
            year_from=req.year_from,
            year_to=req.year_to,
            keyword_filter=req.keyword_filter,
            doc_type_filter=req.doc_type_filter,
            trigger_mode="MANUAL",
        )
        log_audit(
            db,
            actor=actor,
            action="HARVEST_OAI_REPO",
            target_type="oai_repository",
            target_id=repo.id,
            details=summary,
        )
        return {"repository": _serialize_repo(repo, db), "summary": summary}
    except OAIPMHProtocolError as exc:
        raise HTTPException(status_code=502, detail=f"Gagal panen OAI-PMH ({exc.error_code}): {exc.message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal panen OAI-PMH: {exc}") from exc


@router.post("/repositories/{repo_id}/pause")
def pause_oai_harvest(
    repo_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    repo.harvest_state = "PAUSED"
    repo.status = "PAUSED"
    repo.updated_at = datetime.now(timezone.utc)
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="INFO",
            stage="PAUSE",
            message="Pengguna menjeda panen repositori. Progres dan token tersimpan.",
        )
    )
    db.commit()
    db.refresh(repo)
    log_audit(db, actor=actor, action="PAUSE_OAI_REPO", target_type="oai_repository", target_id=repo.id)
    return {"repository": _serialize_repo(repo, db)}


@router.post("/repositories/{repo_id}/resume")
def resume_oai_harvest(
    repo_id: str,
    body: OAIHarvestRequest | None = Body(default=None),
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    req = body or OAIHarvestRequest(resume=True)
    try:
        summary = harvest_oai_repository(
            db,
            repo,
            max_records=req.max_records,
            max_downloads=req.max_downloads,
            download_pdfs=req.download_pdfs,
            resume=True,
            reset_cursor=False,
            incremental=req.incremental,
            set_spec=req.set_spec,
            metadata_prefix=req.metadata_prefix,
            year_from=req.year_from,
            year_to=req.year_to,
            keyword_filter=req.keyword_filter,
            doc_type_filter=req.doc_type_filter,
            trigger_mode="RESUME",
        )
        log_audit(
            db,
            actor=actor,
            action="RESUME_OAI_REPO",
            target_type="oai_repository",
            target_id=repo.id,
            details=summary,
        )
        return {"repository": _serialize_repo(repo, db), "summary": summary}
    except OAIPMHProtocolError as exc:
        raise HTTPException(status_code=502, detail=f"Gagal melanjutkan panen ({exc.error_code}): {exc.message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal melanjutkan panen: {exc}") from exc


@router.post("/repositories/{repo_id}/retry-failed")
def retry_failed_repository_records(
    repo_id: str,
    body: OAIRetryRequest | None = Body(default=None),
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    req = body or OAIRetryRequest()
    summary = retry_failed_oai_records(db, repo, limit=req.limit)
    log_audit(
        db,
        actor=actor,
        action="RETRY_FAILED_OAI_REPO",
        target_type="oai_repository",
        target_id=repo.id,
        details=summary,
    )
    return {"repository": _serialize_repo(repo, db), "summary": summary}


@router.get("/repositories/{repo_id}/records")
def list_oai_repository_records(
    repo_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")

    query = db.query(OAIHarvestRecord).filter(OAIHarvestRecord.repository_id == repo_id)
    if status_filter and status_filter != "ALL":
        query = query.filter(OAIHarvestRecord.status == status_filter)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (OAIHarvestRecord.title.ilike(like))
            | (OAIHarvestRecord.oai_identifier.ilike(like))
            | (OAIHarvestRecord.doi.ilike(like))
        )

    total = query.count()
    items = (
        query.order_by(OAIHarvestRecord.updated_at.desc(), OAIHarvestRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_record(item) for item in items],
    }


@router.put("/repositories/{repo_id}/schedule")
def update_oai_schedule(
    repo_id: str,
    body: OAIScheduleUpdate,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    repo.schedule_enabled = body.schedule_enabled
    repo.schedule_interval_hours = body.schedule_interval_hours
    repo.next_scheduled_at = (
        datetime.now(timezone.utc) + timedelta(hours=body.schedule_interval_hours)
        if body.schedule_enabled
        else None
    )
    repo.updated_at = datetime.now(timezone.utc)
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="INFO",
            stage="SCHEDULE_UPDATE",
            message=(
                f"Jadwal panen otomatis diaktifkan (setiap {body.schedule_interval_hours} jam)."
                if body.schedule_enabled
                else "Jadwal panen otomatis dinonaktifkan."
            ),
        )
    )
    db.commit()
    db.refresh(repo)
    log_audit(db, actor=actor, action="SCHEDULE_OAI_REPO", target_type="oai_repository", target_id=repo.id)
    return {"repository": _serialize_repo(repo, db)}


@router.get("/repositories/{repo_id}/runs")
def list_oai_harvest_runs(
    repo_id: str,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    runs = (
        db.query(OAIHarvestRun)
        .filter(OAIHarvestRun.repository_id == repo_id)
        .order_by(OAIHarvestRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_run(r) for r in runs]


@router.get("/repositories/{repo_id}/indexed-documents")
def list_oai_indexed_documents(
    repo_id: str,
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return all locally indexed full-text documents from this repository with full provenance."""
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")

    rec_rows = (
        db.query(OAIHarvestRecord)
        .filter(
            OAIHarvestRecord.repository_id == repo_id,
            OAIHarvestRecord.status == "INDEXED",
            OAIHarvestRecord.document_id.isnot(None),
        )
        .order_by(OAIHarvestRecord.updated_at.desc())
        .limit(limit)
        .all()
    )
    doc_ids = [r.document_id for r in rec_rows if r.document_id]
    docs_by_id: dict[str, Document] = {}
    usage_counts: dict[str, int] = {}
    if doc_ids:
        for d in db.query(Document).filter(Document.id.in_(doc_ids)).all():
            docs_by_id[d.id] = d
        for sid, cnt in (
            db.query(CheckSource.source_document_id, func.count(func.distinct(CheckSource.check_id)))
            .filter(CheckSource.source_document_id.in_(doc_ids))
            .group_by(CheckSource.source_document_id)
            .all()
        ):
            usage_counts[sid] = int(cnt)

    items: list[dict[str, Any]] = []
    for r in rec_rows:
        d = docs_by_id.get(r.document_id or "")
        if d is None:
            continue
        extra = dict(d.extra or {})
        items.append(
            {
                "document_id": d.id,
                "oai_identifier": r.oai_identifier,
                "university": extra.get("university") or repo.identified_name or repo.name,
                "repository_name": extra.get("repository_name") or repo.name,
                "title": d.title or r.title,
                "authors": d.authors or r.authors or [],
                "year": d.year or r.year,
                "doi": d.doi or r.doi,
                "doc_type": r.doc_type or extra.get("doc_type"),
                "url": d.url or d.canonical_url,
                "license": d.license or r.rights,
                "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None,
                "word_count": d.word_count,
                "page_count": d.page_count,
                "indexing_status": d.indexing_status,
                "compared_checks_count": usage_counts.get(d.id, 0),
            }
        )
    return {"total": len(items), "items": items}


@router.get("/repositories/{repo_id}/logs")
def list_oai_repository_logs(
    repo_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    rows = (
        db.query(OAIHarvestLog)
        .filter(OAIHarvestLog.repository_id == repo_id)
        .order_by(OAIHarvestLog.created_at.desc(), OAIHarvestLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_log(r) for r in rows]


@router.delete("/repositories/{repo_id}")
def delete_oai_repository(
    repo_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    db.delete(repo)
    db.commit()
    log_audit(db, actor=actor, action="DELETE_OAI_REPO", target_type="oai_repository", target_id=repo_id)
    return {"deleted": True}
