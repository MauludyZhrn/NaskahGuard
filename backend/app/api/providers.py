"""Provider status and monitoring endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine.noplag_adapter import NoplagAdapter
from app.models import Document, ProviderQuery
from app.security import require_auth

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(require_auth)])


@router.get("")
def list_providers(db: Session = Depends(get_db)) -> dict:
    local_count = db.query(func.count(Document.id)).filter(Document.role == "CORPUS").scalar() or 0
    ext_count = db.query(func.count(Document.id)).filter(Document.role == "EXTERNAL").scalar() or 0
    recent_queries = db.query(ProviderQuery).order_by(ProviderQuery.started_at.desc()).limit(20).all()
    noplag = NoplagAdapter().health()

    providers = [
        {
            "id": "local_corpus",
            "name": "Korpus Lokal",
            "type": "local",
            "default_enabled": True,
            "full_text_capable": True,
            "indexed_documents": local_count,
            "rate_limit": "Tidak ada batas",
            "status": "Aktif",
        },
        {
            "id": "openalex",
            "name": "OpenAlex",
            "type": "external",
            "default_enabled": False,
            "full_text_capable": True,
            "indexed_documents": ext_count,
            "rate_limit": "~10 req/dtk, 100k/hari (polite pool mailto)",
            "status": "Siap (Nonaktif default — privasi dokumen)",
        },
        {
            "id": "crossref",
            "name": "Crossref",
            "type": "external",
            "default_enabled": False,
            "full_text_capable": False,
            "indexed_documents": 0,
            "rate_limit": "Polite pool User-Agent mailto",
            "status": "Siap (Metadata saja / METADATA_ONLY)",
        },
        {
            "id": "arxiv",
            "name": "arXiv",
            "type": "external",
            "default_enabled": False,
            "full_text_capable": True,
            "indexed_documents": 0,
            "rate_limit": "Minimal jeda 3 detik/permintaan",
            "status": "Siap (Pracetak OA PDF)",
        },
        {
            "id": "pmc",
            "name": "PubMed Central (PMC)",
            "type": "external",
            "default_enabled": False,
            "full_text_capable": False,
            "indexed_documents": 0,
            "rate_limit": "Maks. 3 req/dtk tanpa API key",
            "status": "Metadata E-utilities (Full-text OA FTP belum diimplementasikan)",
        },
        {
            "id": "noplag_engine",
            "name": "Noplag Engine (Internal Loopback Adapter)",
            "type": "internal_service",
            "default_enabled": False,
            "full_text_capable": True,
            "status": "Terhubung" if noplag.get("reachable") else "Tidak dikonfigurasi / tidak aktif",
            "details": noplag,
        },
    ]

    return {
        "providers": providers,
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
