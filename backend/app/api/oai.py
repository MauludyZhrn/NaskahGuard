"""User-managed OAI-PMH Academic Repository Registry, 8-Stage Wizard & Harvester API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.db import get_db
from app.models import OAIHarvestLog, OAIHarvestRecord, OAIRepository
from app.security import enforce_rate_limit, require_auth
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
    download_pdfs: bool = True
    resume: bool = False
    reset_cursor: bool = False
    set_spec: str | None = Field(default=None, max_length=255)
    metadata_prefix: str | None = Field(default=None, max_length=64)


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
        "funnel": funnel,
        "status": r.status,
        "last_error": r.last_error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
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
            download_pdfs=req.download_pdfs,
            resume=req.resume,
            reset_cursor=req.reset_cursor,
            set_spec=req.set_spec,
            metadata_prefix=req.metadata_prefix,
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
            download_pdfs=req.download_pdfs,
            resume=True,
            reset_cursor=False,
            set_spec=req.set_spec,
            metadata_prefix=req.metadata_prefix,
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
