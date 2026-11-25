"""Phase 10.4 Mock & Integration Tests: Indonesian Academic Repository Expansion.

Strictly separated from live tests (uses httpx.MockTransport + isolated SQLite DB).
Verifies:
- Discovery catalog starts entries UNVERIFIED (never pre-claimed active), search, manual add, test & promote
- Advanced harvesting filters (collection, year_from/year_to, keyword, doc_type, max_downloads limit)
- OJS galley (/article/view/ID/GALLEY -> /article/download/ID/GALLEY) & landing PDF discovery
- Harvest run history (OAIHarvestRun) + retry failed + optional schedule config
- Full provenance persistence on Document & automatic local corpus comparison in plagiarism check
- Metadata-only records NEVER treated as full-text or matched
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_session_factory, init_db
from app.engine.pipeline import run_check_pipeline
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.main import create_app
from app.models import (
    Check,
    Document,
    OAIHarvestRecord,
    OAIHarvestRun,
    OAIRepository,
    RepositoryCatalogEntry,
)
from app.sources.oai_catalog import (
    add_catalog_entry,
    ensure_catalog_seeded,
    promote_catalog_entry_to_personal,
    test_catalog_entry as probe_catalog_entry,
)
from app.sources.oai_pmh import harvest_oai_repository


def _pdf_bytes(text: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 72, 520, 720), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def _dc_rec(
    oai_id: str,
    title: str,
    *,
    year: str = "2025",
    author: str = "Dr. Budi Santoso",
    doc_type: str = "Artikel Jurnal",
    subject: str = "Ilmu Komputer",
    doi: str | None = None,
    urls: list[str] | None = None,
    set_spec: str = "col_ti",
) -> str:
    ids = "".join(f"<dc:identifier>{u}</dc:identifier>" for u in (urls or []))
    if doi:
        ids += f"<dc:identifier>https://doi.org/{doi}</dc:identifier>"
    return f"""
    <record>
      <header>
        <identifier>{oai_id}</identifier>
        <datestamp>{year}-06-01</datestamp>
        <setSpec>{set_spec}</setSpec>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>{title}</dc:title>
          <dc:creator>{author}</dc:creator>
          <dc:date>{year}</dc:date>
          <dc:type>{doc_type}</dc:type>
          <dc:subject>{subject}</dc:subject>
          <dc:rights>CC-BY-SA-4.0</dc:rights>
          {ids}
        </oai_dc:dc>
      </metadata>
    </record>"""


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase10_4.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NG_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("NG_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("NG_API_TOKEN", "")
    monkeypatch.setenv("API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    engine = init_db(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def test_catalog_never_pre_verified_search_test_and_promote(isolated_db):
    seeded = ensure_catalog_seeded(isolated_db)
    assert seeded >= 8

    # Critical rule: NEVER mark catalog entries active before tested!
    entries = isolated_db.query(RepositoryCatalogEntry).all()
    assert all(e.oai_status == "UNVERIFIED" for e in entries)

    oai_url = "https://kampus-test.ac.id/server/oai/request"
    custom = add_catalog_entry(
        isolated_db,
        university="Universitas Contoh Nusantara",
        name="Repositori DSpace 7 Contoh",
        base_url=oai_url,
        platform="dspace7",
    )
    assert custom.oai_status == "UNVERIFIED"

    def handler(req: httpx.Request) -> httpx.Response:
        verb = parse_qs(urlparse(str(req.url)).query).get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(
                200,
                text=f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><Identify><repositoryName>Repositori Resmi Contoh</repositoryName><protocolVersion>2.0</protocolVersion></Identify></OAI-PMH>',
            )
        if verb == "ListMetadataFormats":
            return httpx.Response(
                200,
                text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListMetadataFormats><metadataFormat><metadataPrefix>oai_dc</metadataPrefix></metadataFormat><metadataFormat><metadataPrefix>dim</metadataPrefix></metadataFormat></ListMetadataFormats></OAI-PMH>',
            )
        if verb == "ListSets":
            return httpx.Response(
                200,
                text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListSets><set><setSpec>skripsi</setSpec><setName>Skripsi S1</setName></set></ListSets></OAI-PMH>',
            )
        if verb == "ListRecords":
            return httpx.Response(
                200,
                text=f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>{_dc_rec("oai:c:1", "Skripsi Uji Katalog", urls=["https://kampus-test.ac.id/bitstream/1.pdf"])}</ListRecords></OAI-PMH>',
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tested_entry, wizard = probe_catalog_entry(isolated_db, custom, client=client, resolve_dns=False)
    assert wizard["ok"] is True
    assert tested_entry.oai_status == "VERIFIED"
    assert tested_entry.collections_count == 1
    assert "dim" in tested_entry.supported_formats

    personal_repo, created_new = promote_catalog_entry_to_personal(isolated_db, tested_entry)
    assert created_new is True
    assert personal_repo.status == "VERIFIED"
    assert personal_repo.platform_detected == "dspace7"


def test_advanced_filters_max_downloads_ojs_galley_and_local_corpus_provenance(isolated_db):
    oai_url = "https://jurnal.kampus.ac.id/index.php/falak/oai"
    galley_view_1 = "https://jurnal.kampus.ac.id/index.php/falak/article/view/10/50"
    galley_dl_1 = "https://jurnal.kampus.ac.id/index.php/falak/article/download/10/50"
    galley_view_2 = "https://jurnal.kampus.ac.id/index.php/falak/article/view/11/51"
    galley_dl_2 = "https://jurnal.kampus.ac.id/index.php/falak/article/download/11/51"

    target_text = (
        "Metode hisab hakiki kontemporer dalam penentuan awal waktu salat Idain mempertimbangkan koreksi tinggi ufuk, "
        "refraksi atmosfer, serta kerendahan horizon geografis pengamat di wilayah khatulistiwa Indonesia secara matematis."
    )
    pdf1 = _pdf_bytes(target_text)
    pdf2 = _pdf_bytes("Artikel kedua tentang algoritma numerik kalender hijriah internasional dan interpolasi sudut jam matahari.")

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if u == galley_dl_1:
            return httpx.Response(200, content=pdf1, headers={"Content-Type": "application/pdf"})
        if u == galley_dl_2:
            return httpx.Response(200, content=pdf2, headers={"Content-Type": "application/pdf"})
        verb = parse_qs(urlparse(u).query).get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(
                200,
                text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><Identify><repositoryName>Jurnal Falak Nusantara (OJS)</repositoryName><protocolVersion>2.0</protocolVersion></Identify></OAI-PMH>',
            )
        if verb == "ListMetadataFormats":
            return httpx.Response(
                200,
                text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListMetadataFormats><metadataFormat><metadataPrefix>oai_dc</metadataPrefix></metadataFormat></ListMetadataFormats></OAI-PMH>',
            )
        if verb == "ListRecords":
            # 4 records:
            # r1: year 2018 -> excluded by year_from=2022
            # r2: year 2024, keyword wrong -> excluded by keyword="hisab"
            # r3: year 2024, keyword "hisab", artikel -> matched & PDF downloaded (hits max_downloads=1!)
            # r4: year 2025, keyword "hisab", artikel -> matched, metadata saved ONLY because max_downloads=1 reached!
            xml = (
                _dc_rec("oai:falak:1", "Kajian Hisab Klasik Lama", year="2018", urls=[galley_view_1])
                + _dc_rec("oai:falak:2", "Ekonomi Makro Nasional Modern", year="2024", subject="Ekonomi", urls=[galley_view_1])
                + _dc_rec("oai:falak:3", "Metode Hisab Hakiki Kontemporer Salat Idain", year="2024", doi="10.8888/falak.10", urls=[galley_view_1])
                + _dc_rec("oai:falak:4", "Hisab Kalender Hijriah Lanjutan", year="2025", doi="10.8888/falak.11", urls=[galley_view_2])
            )
            return httpx.Response(200, text=f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>{xml}</ListRecords></OAI-PMH>')
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Jurnal Falak Nusantara", base_url=oai_url, repo_type="ojs")
    isolated_db.add(repo)
    isolated_db.commit()

    summary = harvest_oai_repository(
        isolated_db,
        repo,
        max_records=10,
        max_downloads=1,
        download_pdfs=True,
        year_from=2022,
        year_to=2026,
        keyword_filter="hisab",
        doc_type_filter="artikel",
        client=client,
        resolve_dns=False,
    )
    assert summary["records_scanned"] == 4
    assert summary["records_matched_filter"] == 2
    assert summary["records_harvested"] == 2
    assert summary["fulltext_indexed"] == 1
    assert summary["metadata_only"] == 1  # r4 stopped by max_downloads=1 -> strictly metadata only!

    # Verify OAIHarvestRun history persisted
    runs = isolated_db.query(OAIHarvestRun).filter(OAIHarvestRun.repository_id == repo.id).all()
    assert len(runs) == 1
    assert runs[0].records_scanned == 4
    assert runs[0].fulltext_indexed == 1

    # Verify Provenance stored on indexed Document
    docs = isolated_db.query(Document).filter(Document.role == "CORPUS").all()
    assert len(docs) == 1
    d = docs[0]
    assert d.doi == "10.8888/falak.10"
    assert d.year == 2024
    assert d.license == "CC-BY-SA-4.0"
    assert d.retrieved_at is not None
    assert (d.extra or {}).get("university") == "Jurnal Falak Nusantara (OJS)"
    assert (d.extra or {}).get("repository_name") == "Jurnal Falak Nusantara"

    # Verify automatic availability in subsequent plagiarism check (AND r4 metadata-only never matches!)
    sub_text = (
        "Naskah Skripsi Uji Integrasi Korpus\n\n"
        + target_text
        + "\n\nKesimpulan mengenai metode hisab kalender hijriah lanjutan sebagai catatan penutup."
    )
    val = validate_local_bytes("uji_integrasi.txt", sub_text.encode("utf-8"), 25 * 1024 * 1024)
    sub_doc = ingest_validated_upload(isolated_db, val, role="SUBMISSION", title="Uji Integrasi")
    chk = Check(
        report_number="NG-OAI-104-01",
        document_id=sub_doc.id,
        status="QUEUED",
        mode="PLAGIARISM_ONLY",
        settings={
            "include_local_corpus": True,
            "use_external_sources": False,
            "exclude_bibliography": False,
            "min_match_words": 5,
        },
    )
    isolated_db.add(chk)
    isolated_db.commit()
    run_check_pipeline(isolated_db, chk.id)
    isolated_db.refresh(chk)
    assert chk.status == "COMPLETED"
    assert (chk.metrics or {}).get("similarity_index", 0) > 40.0
    assert (chk.metrics or {}).get("sources_found") == 1


def test_catalog_and_schedule_api_e2e(tmp_path, monkeypatch):
    db_path = tmp_path / "api_10_4.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NG_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("NG_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("NG_API_TOKEN", "")
    monkeypatch.setenv("API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as tc:
        # Catalog GET seeds entries cleanly with UNVERIFIED status
        cat_res = tc.get("/api/oai/catalog?q=IPB")
        assert cat_res.status_code == 200
        cat_items = cat_res.json()["items"]
        assert len(cat_items) == 1
        assert cat_items[0]["oai_status"] == "UNVERIFIED"
        cat_id = cat_items[0]["id"]

        # Promote to personal list
        add_res = tc.post(f"/api/oai/catalog/{cat_id}/add")
        assert add_res.status_code == 200
        assert add_res.json()["created"] is True
        repo_id = add_res.json()["repository"]["id"]

        # Schedule endpoint
        sched_res = tc.put(
            f"/api/oai/repositories/{repo_id}/schedule",
            json={"schedule_enabled": True, "schedule_interval_hours": 12},
        )
        assert sched_res.status_code == 200
        assert sched_res.json()["repository"]["schedule_enabled"] is True
        assert sched_res.json()["repository"]["schedule_interval_hours"] == 12

        # Harvest history (runs) & indexed-documents endpoints
        assert tc.get(f"/api/oai/repositories/{repo_id}/runs").status_code == 200
        assert tc.get(f"/api/oai/repositories/{repo_id}/indexed-documents").status_code == 200
