"""User-managed OAI-PMH Indonesian Academic Repository Registry & Harvester endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.db import get_db
from app.models import OAIRepository
from app.security import enforce_rate_limit, require_auth
from app.sources.oai_pmh import OAIPMHClient, harvest_oai_repository
from app.sources.ssrf import SSRFError, validate_public_url

router = APIRouter(prefix="/oai", tags=["oai-pmh"], dependencies=[Depends(require_auth)])


class OAIRepoCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    base_url: str = Field(..., min_length=10, max_length=1024)
    repo_type: str = Field(default="ojs", pattern="^(ojs|dspace|eprints|other)$")
    metadata_prefix: str = Field(default="oai_dc", min_length=2, max_length=64)


class OAIHarvestRequest(BaseModel):
    max_records: int = Field(default=15, ge=1, le=100)
    download_pdfs: bool = True


def _serialize_repo(r: OAIRepository) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "base_url": r.base_url,
        "repo_type": r.repo_type,
        "enabled": r.enabled,
        "identified_name": r.identified_name,
        "metadata_prefix": r.metadata_prefix,
        "last_harvested_at": r.last_harvested_at.isoformat() if r.last_harvested_at else None,
        "last_datestamp": r.last_datestamp,
        "records_harvested": r.records_harvested,
        "fulltext_indexed": r.fulltext_indexed,
        "status": r.status,
        "last_error": r.last_error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/repositories")
def list_oai_repositories(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(OAIRepository).order_by(OAIRepository.created_at.desc()).all()
    return [_serialize_repo(r) for r in rows]


@router.post("/repositories", status_code=status.HTTP_201_CREATED)
def add_oai_repository(
    body: OAIRepoCreate,
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    try:
        clean_url = validate_public_url(body.base_url, resolve_dns=False)
    except SSRFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.query(OAIRepository).filter(OAIRepository.base_url == clean_url).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Base URL repositori OAI-PMH sudah terdaftar.")

    repo = OAIRepository(
        name=body.name.strip(),
        base_url=clean_url,
        repo_type=body.repo_type,
        metadata_prefix=body.metadata_prefix.strip(),
        status="UNVERIFIED",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    log_audit(db, actor=actor, action="ADD_OAI_REPO", target_type="oai_repository", target_id=repo.id, details={"base_url": clean_url})
    return _serialize_repo(repo)


@router.post("/repositories/{repo_id}/verify")
def verify_oai_repository(repo_id: str, db: Session = Depends(get_db)) -> dict:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    oai = OAIPMHClient()
    try:
        ident = oai.identify(repo.base_url)
        formats = oai.list_metadata_formats(repo.base_url)
        repo.identified_name = ident.get("repositoryName") or repo.name
        repo.status = "VERIFIED"
        repo.last_error = None
        db.commit()
        return {"repository": _serialize_repo(repo), "identify": ident, "formats": formats}
    except Exception as exc:
        repo.status = "ERROR"
        repo.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Gagal memverifikasi OAI-PMH: {exc}") from exc


@router.post("/repositories/{repo_id}/harvest")
def trigger_oai_harvest(
    repo_id: str,
    body: OAIHarvestRequest,
    actor: str = Depends(require_auth),
    _rl: None = Depends(enforce_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    try:
        summary = harvest_oai_repository(
            db,
            repo,
            max_records=body.max_records,
            download_pdfs=body.download_pdfs,
        )
        log_audit(db, actor=actor, action="HARVEST_OAI_REPO", target_type="oai_repository", target_id=repo.id, details=summary)
        return {"repository": _serialize_repo(repo), "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal panen OAI-PMH: {exc}") from exc


@router.delete("/repositories/{repo_id}")
def delete_oai_repository(
    repo_id: str,
    actor: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    repo = db.query(OAIRepository).filter(OAIRepository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repositori OAI-PMH tidak ditemukan.")
    db.delete(repo)
    db.commit()
    log_audit(db, actor=actor, action="DELETE_OAI_REPO", target_type="oai_repository", target_id=repo_id)
    return {"deleted": True}
