"""Indonesian & Official Public OAI-PMH Repository Discovery Catalog.

CRITICAL RULE: Catalog entries NEVER claim to be active/verified prior to running an
explicit connectivity test (`UNVERIFIED` by default). Seed URLs strictly contain real
official academic endpoints referenced from verifiable public directories/documentation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import OAIHarvestLog, OAIRepository, RepositoryCatalogEntry
from app.sources.oai_pmh import (
    detect_platform_from_url,
    normalize_repo_type,
    platform_label,
    run_connection_wizard,
)
from app.sources.ssrf import validate_public_url

# Real official public endpoints verified in official .ac.id / open directories.
# All entries start as oai_status="UNVERIFIED" until explicitly tested by the user or probe!
INITIAL_CATALOG_SEEDS: list[dict[str, str]] = [
    {
        "university": "Universitas Negeri Yogyakarta (UNY)",
        "name": "Jurnal Pendidikan Vokasi Otomotif (OJS UNY)",
        "base_url": "https://journal.uny.ac.id/index.php/jpvo/oai",
        "platform": "ojs",
        "description": "Portal jurnal ilmiah Open Journal Systems (OJS) Universitas Negeri Yogyakarta.",
    },
    {
        "university": "IPB University (Institut Pertanian Bogor)",
        "name": "IPB Scientific Repository",
        "base_url": "https://repository.ipb.ac.id/oai/request",
        "platform": "dspace_legacy",
        "description": "Repositori karya ilmiah IPB University (skripsi, tesis, disertasi, laporan riset) berbasis DSpace.",
    },
    {
        "university": "UIN Sunan Kalijaga Yogyakarta",
        "name": "Institutional Repository UIN Sunan Kalijaga",
        "base_url": "http://digilib.uin-suka.ac.id/cgi/oai2",
        "platform": "eprints",
        "description": "Repositori digital skripsi, tesis, dan publikasi UIN Sunan Kalijaga berbasis EPrints.",
    },
    {
        "university": "Institut Teknologi Sepuluh Nopember (ITS)",
        "name": "ITS Repository",
        "base_url": "http://repository.its.ac.id/cgi/oai2",
        "platform": "eprints",
        "description": "Repositori institusional Institut Teknologi Sepuluh Nopember Surabaya berbasis EPrints.",
    },
    {
        "university": "Institut Seni Indonesia (ISI) Yogyakarta",
        "name": "Digilib ISI Yogyakarta",
        "base_url": "http://digilib.isi.ac.id/cgi/oai2",
        "platform": "eprints",
        "description": "Perpustakaan digital dan repositori akademik ISI Yogyakarta berbasis EPrints.",
    },
    {
        "university": "Universitas Sebelas Maret (UNS)",
        "name": "Journal of Informatics and Vocational Education (OJS UNS)",
        "base_url": "https://jurnal.uns.ac.id/index.php/joive/oai",
        "platform": "ojs",
        "description": "Portal jurnal OJS Universitas Sebelas Maret Surakarta.",
    },
    {
        "university": "Universitas Islam Indonesia (UII)",
        "name": "DSpace UII Repository",
        "base_url": "https://dspace.uii.ac.id/oai/request",
        "platform": "dspace_legacy",
        "description": "Repositori DSpace Universitas Islam Indonesia Yogyakarta.",
    },
    {
        "university": "Universitas Muhammadiyah Malang (UMM)",
        "name": "EPrints UMM Repository",
        "base_url": "https://eprints.umm.ac.id/cgi/oai2",
        "platform": "eprints",
        "description": "Repositori EPrints Universitas Muhammadiyah Malang.",
    },
    {
        "university": "STIKOM Yos Sudarso Purwokerto",
        "name": "SYS Digital Repository (DSpace 7)",
        "base_url": "https://digilib.stikomyos.ac.id/server/oai/request",
        "platform": "dspace7",
        "description": "Repositori institusi STIKOM Yos Sudarso dengan endpoint OAI-PMH DSpace 7.",
    },
    {
        "university": "arXiv (Cornell University Open Archive)",
        "name": "arXiv Public OAI-PMH",
        "base_url": "https://oaipmh.arxiv.org/oai",
        "platform": "arxiv",
        "description": "Arsip terbuka internasional untuk naskah sains, komputer, matematika, dan teknik.",
    },
]


def ensure_catalog_seeded(db: Session) -> int:
    """Idempotently seed official catalog entries with status UNVERIFIED (never pre-marked active)."""
    existing_urls = {
        row[0] for row in db.query(RepositoryCatalogEntry.base_url).all()
    }
    added = 0
    for item in INITIAL_CATALOG_SEEDS:
        if item["base_url"] in existing_urls:
            continue
        plat = normalize_repo_type(item["platform"])
        db.add(
            RepositoryCatalogEntry(
                university=item["university"],
                name=item["name"],
                base_url=item["base_url"],
                platform=plat,
                platform_label=platform_label(plat),
                description=item.get("description"),
                oai_status="UNVERIFIED",
                collections_count=0,
                supported_formats=[],
                available_sets=[],
                is_custom=False,
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def serialize_catalog_entry(entry: RepositoryCatalogEntry, *, personal_urls: set[str] | None = None) -> dict[str, Any]:
    return {
        "id": entry.id,
        "university": entry.university,
        "name": entry.name,
        "base_url": entry.base_url,
        "platform": entry.platform,
        "platform_label": entry.platform_label or platform_label(entry.platform),
        "description": entry.description,
        "oai_status": entry.oai_status,
        "identified_name": entry.identified_name,
        "collections_count": entry.collections_count,
        "supported_formats": entry.supported_formats or [],
        "available_sets": entry.available_sets or [],
        "last_error": entry.last_error,
        "last_tested_at": entry.last_tested_at.isoformat() if entry.last_tested_at else None,
        "is_custom": entry.is_custom,
        "already_in_personal": (entry.base_url in personal_urls) if personal_urls is not None else False,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def add_catalog_entry(
    db: Session,
    *,
    university: str,
    name: str,
    base_url: str,
    platform: str = "other",
    description: str | None = None,
) -> RepositoryCatalogEntry:
    clean_url = validate_public_url(base_url, resolve_dns=False)
    existing = db.query(RepositoryCatalogEntry).filter(RepositoryCatalogEntry.base_url == clean_url).first()
    if existing is not None:
        return existing
    norm_plat = normalize_repo_type(platform)
    if norm_plat == "other":
        norm_plat = detect_platform_from_url(clean_url)
    entry = RepositoryCatalogEntry(
        university=university.strip(),
        name=name.strip(),
        base_url=clean_url,
        platform=norm_plat,
        platform_label=platform_label(norm_plat),
        description=(description or "").strip() or None,
        oai_status="UNVERIFIED",
        collections_count=0,
        supported_formats=[],
        available_sets=[],
        is_custom=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def test_catalog_entry(
    db: Session,
    entry: RepositoryCatalogEntry,
    *,
    client: httpx.Client | None = None,
    resolve_dns: bool = True,
    timeout_sec: float = 20.0,
) -> tuple[RepositoryCatalogEntry, dict[str, Any]]:
    """Run live 8-stage OAI-PMH test on a catalog entry and persist real observed results."""
    report = run_connection_wizard(
        entry.base_url,
        probe_pdf=False,
        client=client,
        resolve_dns=resolve_dns,
        timeout_sec=timeout_sec,
    )
    entry.last_tested_at = datetime.now(timezone.utc)
    if report.get("platform_detected") and report["platform_detected"] != "other":
        entry.platform = report["platform_detected"]
        entry.platform_label = platform_label(entry.platform)
    if report.get("identified_name"):
        entry.identified_name = report["identified_name"][:500]
    if report.get("supported_formats"):
        entry.supported_formats = report["supported_formats"]
    if isinstance(report.get("available_sets"), list):
        entry.available_sets = report["available_sets"][:100]
        entry.collections_count = len(report["available_sets"])

    if report["overall_status"] == "READY":
        entry.oai_status = "VERIFIED"
        entry.last_error = None
    elif report["overall_status"] == "PARTIAL":
        entry.oai_status = "PARTIAL"
        warn_st = next((s for s in report["stages"] if s["status"] == "WARN"), None)
        entry.last_error = warn_st["message"] if warn_st else None
    else:
        entry.oai_status = "ERROR"
        fail_st = next((s for s in report["stages"] if s["status"] == "FAIL"), None)
        entry.last_error = (fail_st or {}).get("message") or "Koneksi gagal."

    db.commit()
    db.refresh(entry)
    return entry, report


def promote_catalog_entry_to_personal(
    db: Session,
    entry: RepositoryCatalogEntry,
    *,
    selected_set: str | None = None,
    metadata_prefix: str | None = None,
) -> tuple[OAIRepository, bool]:
    """Add a catalog entry into the user's personal `oai_repositories` list.

    Returns (repo, created_new).
    """
    existing = db.query(OAIRepository).filter(OAIRepository.base_url == entry.base_url).first()
    if existing is not None:
        return existing, False

    chosen_prefix = metadata_prefix or (
        "oai_dc"
        if not entry.supported_formats or "oai_dc" in entry.supported_formats
        else entry.supported_formats[0]
    )
    mapped_status = (
        "VERIFIED" if entry.oai_status in {"VERIFIED", "PARTIAL"} else ("ERROR" if entry.oai_status == "ERROR" else "UNVERIFIED")
    )
    repo = OAIRepository(
        name=entry.name,
        base_url=entry.base_url,
        repo_type=entry.platform or "other",
        platform_detected=entry.platform,
        identified_name=entry.identified_name or entry.university,
        metadata_prefix=chosen_prefix,
        selected_set=(selected_set or "").strip() or None,
        supported_formats=entry.supported_formats or [],
        available_sets=entry.available_sets or [],
        status=mapped_status,
        harvest_state="IDLE",
        last_error=entry.last_error if mapped_status == "ERROR" else None,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(repo)
    db.flush()
    db.add(
        OAIHarvestLog(
            repository_id=repo.id,
            level="INFO",
            stage="CATALOG_ADD",
            message=f"Ditambahkan dari Katalog Repositori ({entry.university}).",
        )
    )
    db.commit()
    db.refresh(repo)
    return repo, True
