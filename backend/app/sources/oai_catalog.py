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
INITIAL_CATALOG_SEEDS: list[dict[str, Any]] = [
    {
        "university": "Universitas Diponegoro (UNDIP)",
        "name": "UNDIP Institutional Repository",
        "base_url": "https://eprints2.undip.ac.id/cgi/oai2",
        "legacy_url": "http://eprints.undip.ac.id/cgi/oai2",
        "platform": "eprints",
        "policy_url": "https://eprints2.undip.ac.id/policies.html",
        "fulltext_policy": "METADATA_ONLY_DEFAULT",
        "harvesting_permission_status": "METADATA_ALLOWED_FULLTEXT_RESTRICTED",
        "default_download_pdfs": False,
        "requires_verification_before_save": True,
        "description": (
            "Repositori institusional resmi Universitas Diponegoro (EPrints2). "
            "Endpoint lama (http://eprints.undip.ac.id/cgi/oai2) mengarah 301 ke endpoint HTTPS baru ini. "
            "Sesuai policies.html UNDIP, metadata terbuka non-komersial dengan atribusi, sedangkan panen massal full-text oleh robot dibatasi."
        ),
    },
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


def fulltext_policy_label(policy: str | None) -> str:
    return {
        "METADATA_ONLY_DEFAULT": "Metadata Saja (Default Kebijakan)",
        "OPEN_PUBLIC_PDF": "Full-Text Publik Terbuka",
        "RESTRICTED": "Full-Text Terbatas",
    }.get(policy or "", "Full-Text Publik Terbuka")


def permission_status_label(perm: str | None) -> str:
    return {
        "METADATA_ALLOWED_FULLTEXT_RESTRICTED": "Metadata Diizinkan · Panen Robot PDF Dibatasi",
        "OPEN_UNRESTRICTED": "Terbuka untuk Metadata & Full-Text Publik",
        "MANUAL_PERMISSION_REQUIRED": "Memerlukan Izin Pengelola Repositori",
    }.get(perm or "", "Terbuka untuk Metadata & Full-Text Publik")


def ensure_catalog_seeded(db: Session) -> int:
    """Idempotently seed official catalog entries with status UNVERIFIED (never pre-marked active)."""
    existing_by_url = {
        row.base_url: row for row in db.query(RepositoryCatalogEntry).all()
    }
    changed = 0
    for item in INITIAL_CATALOG_SEEDS:
        plat = normalize_repo_type(item["platform"])
        existing = existing_by_url.get(item["base_url"])
        if existing is not None:
            # Backfill newly added policy fields for preset entries if upgraded from Phase 10.4
            updated_row = False
            if item.get("legacy_url") and not existing.legacy_url:
                existing.legacy_url = item["legacy_url"]
                updated_row = True
            if item.get("policy_url") and not existing.policy_url:
                existing.policy_url = item["policy_url"]
                updated_row = True
            if item.get("fulltext_policy") and existing.fulltext_policy != item["fulltext_policy"]:
                existing.fulltext_policy = item["fulltext_policy"]
                updated_row = True
            if item.get("harvesting_permission_status") and existing.harvesting_permission_status != item["harvesting_permission_status"]:
                existing.harvesting_permission_status = item["harvesting_permission_status"]
                updated_row = True
            if "default_download_pdfs" in item and existing.default_download_pdfs != bool(item["default_download_pdfs"]):
                existing.default_download_pdfs = bool(item["default_download_pdfs"])
                updated_row = True
            if "requires_verification_before_save" in item and existing.requires_verification_before_save != bool(item["requires_verification_before_save"]):
                existing.requires_verification_before_save = bool(item["requires_verification_before_save"])
                updated_row = True
            if updated_row:
                changed += 1
            continue

        db.add(
            RepositoryCatalogEntry(
                university=item["university"],
                name=item["name"],
                base_url=item["base_url"],
                legacy_url=item.get("legacy_url"),
                platform=plat,
                platform_label=platform_label(plat),
                description=item.get("description"),
                policy_url=item.get("policy_url"),
                fulltext_policy=item.get("fulltext_policy", "OPEN_PUBLIC_PDF"),
                harvesting_permission_status=item.get("harvesting_permission_status", "OPEN_UNRESTRICTED"),
                default_download_pdfs=bool(item.get("default_download_pdfs", True)),
                requires_verification_before_save=bool(item.get("requires_verification_before_save", False)),
                oai_status="UNVERIFIED",
                collections_count=0,
                supported_formats=[],
                available_sets=[],
                is_custom=False,
            )
        )
        changed += 1
    if changed:
        db.commit()
    return changed


def serialize_catalog_entry(entry: RepositoryCatalogEntry, *, personal_urls: set[str] | None = None) -> dict[str, Any]:
    return {
        "id": entry.id,
        "university": entry.university,
        "name": entry.name,
        "base_url": entry.base_url,
        "legacy_url": entry.legacy_url,
        "platform": entry.platform,
        "platform_label": entry.platform_label or platform_label(entry.platform),
        "description": entry.description,
        "policy_url": entry.policy_url,
        "fulltext_policy": entry.fulltext_policy or "OPEN_PUBLIC_PDF",
        "fulltext_policy_label": fulltext_policy_label(entry.fulltext_policy),
        "harvesting_permission_status": entry.harvesting_permission_status or "OPEN_UNRESTRICTED",
        "harvesting_permission_label": permission_status_label(entry.harvesting_permission_status),
        "default_download_pdfs": bool(entry.default_download_pdfs),
        "requires_verification_before_save": bool(entry.requires_verification_before_save),
        "record_count_estimate": entry.record_count_estimate,
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
    legacy_url: str | None = None,
    policy_url: str | None = None,
    fulltext_policy: str = "OPEN_PUBLIC_PDF",
    harvesting_permission_status: str = "OPEN_UNRESTRICTED",
    default_download_pdfs: bool = True,
    requires_verification_before_save: bool = False,
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
        legacy_url=legacy_url.strip() if legacy_url else None,
        platform=norm_plat,
        platform_label=platform_label(norm_plat),
        description=(description or "").strip() or None,
        policy_url=policy_url.strip() if policy_url else None,
        fulltext_policy=fulltext_policy,
        harvesting_permission_status=harvesting_permission_status,
        default_download_pdfs=default_download_pdfs,
        requires_verification_before_save=requires_verification_before_save,
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
    timeout_sec: float = 35.0,
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
    if report.get("record_count_estimate") is not None:
        entry.record_count_estimate = int(report["record_count_estimate"])

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
        cat_lbl = (fail_st or {}).get("error_category_label")
        msg = (fail_st or {}).get("message") or "Koneksi gagal."
        entry.last_error = f"[{cat_lbl}] {msg}" if cat_lbl else msg

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
    default_timeout = 45 if (entry.platform == "eprints" or "undip.ac.id" in entry.base_url) else 25
    repo = OAIRepository(
        name=entry.name,
        base_url=entry.base_url,
        legacy_url=entry.legacy_url,
        policy_url=entry.policy_url,
        fulltext_policy=entry.fulltext_policy or "OPEN_PUBLIC_PDF",
        harvesting_permission_status=entry.harvesting_permission_status or "OPEN_UNRESTRICTED",
        default_download_pdfs=bool(entry.default_download_pdfs),
        record_count_estimate=entry.record_count_estimate,
        repo_type=entry.platform or "other",
        platform_detected=entry.platform,
        identified_name=entry.identified_name or entry.university,
        metadata_prefix=chosen_prefix,
        selected_set=(selected_set or "").strip() or None,
        supported_formats=entry.supported_formats or [],
        available_sets=entry.available_sets or [],
        request_timeout_sec=default_timeout,
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
            message=(
                f"Ditambahkan dari Katalog Repositori ({entry.university}). "
                f"Kebijakan full-text: {fulltext_policy_label(repo.fulltext_policy)}."
            ),
        )
    )
    db.commit()
    db.refresh(repo)
    return repo, True
