"""Phase 7 tests: SSRF guard, Intelligent Query Generator, OpenAlex/Europe PMC/SearXNG, Crawler, Dedup, OAI-PMH."""

from __future__ import annotations

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.engine.pipeline import run_check_pipeline
from app.ingestion.html_extractor import extract_html_text_and_meta
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.ingestion.xml_extractor import extract_xml_text_and_meta
from app.main import create_app
from app.models import Check, CheckSource, Document, OAIRepository, Segment, SourceAcquisition
from app.schemas import CheckSettingsSchema
from app.sources.crawler import fetch_public_url
from app.sources.dedup import find_duplicate_source
from app.sources.europe_pmc import EuropePMCProvider
from app.sources.oai_pmh import OAIPMHClient, harvest_oai_repository
from app.sources.openalex import OpenAlexProvider
from app.sources.query_generator import generate_intelligent_queries
from app.sources.registry import discover_external_sources
from app.sources.ssrf import SSRFError, validate_public_url
from app.sources.web_search import OfficialWebSearchAPIProvider, SearXNGWebSearchProvider


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_ssrf_blocks_private_loopback_metadata_and_redirects():
    for bad in (
        "file:///etc/passwd",
        "http://localhost:8000/secret",
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "http://192.168.1.5/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://service.internal/api",
    ):
        with pytest.raises(SSRFError):
            validate_public_url(bad, resolve_dns=False)

    # Public URL passes syntax check
    assert validate_public_url("https://example.org/paper.pdf", resolve_dns=False) == "https://example.org/paper.pdf"

    # Redirect to 127.0.0.1 is blocked
    def redir_handler(req: httpx.Request) -> httpx.Response:
        if "robots.txt" in str(req.url):
            return httpx.Response(404)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1:8000/internal"})

    client = httpx.Client(transport=httpx.MockTransport(redir_handler))
    res = fetch_public_url("https://example.org/redir", client=client, resolve_dns=False)
    assert res.status == "ACCESS_RESTRICTED"
    assert "Redirect ditolak" in (res.error or "")


def test_intelligent_query_generator_excludes_bib_and_ranks_distinctive_phrases(isolated_env):
    db = get_session_factory()()
    try:
        txt = (
            "BAB I PENDAHULUAN\n\n"
            "Penelitian ini bertujuan untuk mengetahui pengaruh sistem informasi.\n\n"
            "Algoritma pencocokan sidik jari winnowing berbasis k-gram kata mampu menemukan kemiripan sintaksis "
            "pada skripsi mahasiswa secara deterministik dan transparan (DOI: 10.1145/872757.872770).\n\n"
            "BAB II METODE\n\n"
            "Metode penelitian ini menggunakan pendekatan seed-and-extend alignment untuk menyelaraskan rentang token.\n\n"
            "Daftar Pustaka\n\n"
            "Schleimer, S. (2003). Winnowing: Local Algorithms for Document Fingerprinting."
        )
        v = validate_local_bytes("tesis.txt", txt.encode("utf-8"), 5_000_000)
        doc = ingest_validated_upload(db, v, role="SUBMISSION", title="Deteksi Kemiripan Skripsi")
        segs = db.query(Segment).filter(Segment.document_id == doc.id).order_by(Segment.sentence_number).all()

        queries = generate_intelligent_queries(title=doc.title, segments=segs, max_queries=6)
        assert len(queries) >= 3
        q_texts = [q.query for q in queries]
        assert any("10.1145/872757.872770" in qt for qt in q_texts)
        assert not any("Schleimer" in qt for qt in q_texts)
    finally:
        db.close()


def test_html_and_xml_extractors_strip_boilerplate():
    html = """
    <html><head><title>Judul Artikel Web</title>
    <link rel="canonical" href="https://journal.example.org/article/1"/>
    <meta name="citation_author" content="Siti Rahma"/>
    <meta name="citation_doi" content="10.9999/web.1"/>
    </head><body>
      <nav>Menu Utama | Login | Daftar</nav>
      <aside class="sidebar">Iklan Banner Promo</aside>
      <article>
        <h1>Penerapan Winnowing pada Dokumen Ilmiah</h1>
        <p>Sistem temu kembali teks akademik memerlukan normalisasi Unicode yang tidak mengubah teks asli dokumen.</p>
      </article>
      <footer>Copyright 2026 All Rights Reserved</footer>
    </body></html>
    """
    ext_h = extract_html_text_and_meta(html)
    assert "Menu Utama" not in ext_h.text
    assert "Iklan Banner" not in ext_h.text
    assert "Copyright 2026" not in ext_h.text
    assert "normalisasi Unicode" in ext_h.text
    assert ext_h.extra["canonical_url"] == "https://journal.example.org/article/1"
    assert ext_h.extra["doi"] == "10.9999/web.1"

    jats = """<?xml version="1.0"?>
    <article><front><article-meta>
      <title-group><article-title>Open Access JATS Article</article-title></title-group>
      <contrib-group><contrib contrib-type="author"><name><surname>Putra</surname><given-names>Adi</given-names></name></contrib></contrib-group>
    </article-meta></front>
    <body><p>Full text extraction from Europe PMC XML enables verbatim passage alignment across open access journals.</p></body></article>
    """
    ext_x = extract_xml_text_and_meta(jats)
    assert ext_x.title == "Open Access JATS Article"
    assert "verbatim passage alignment" in ext_x.text


def test_openalex_europe_pmc_web_search_fulltext_acquisition_and_dedup(isolated_env):
    db = get_session_factory()()
    try:
        copied_sentence = (
            "Arsitektur penemuan sumber terbuka menggabungkan pencarian OpenAlex dan Europe PMC "
            "untuk mengambil berkas teks penuh yang sah secara hukum."
        )
        pdf_payload = _pdf_bytes(f"OpenAlex Full Paper\n\n{copied_sentence}\n\nAdditional discussion text.")
        epmc_xml = (
            '<?xml version="1.0"?><article><front><article-meta>'
            '<title-group><article-title>Europe PMC Full Study</article-title></title-group>'
            '</article-meta></front><body>'
            '<p>Biomedical open access retrieval provides structured JATS XML paragraphs for similarity verification.</p>'
            '</body></article>'
        ).encode("utf-8")

        def oa_handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "api.openalex.org/works" in u:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "https://openalex.org/W777",
                                "display_name": "Arsitektur Penemuan Sumber Terbuka",
                                "publication_year": 2025,
                                "doi": "https://doi.org/10.5555/oa.777",
                                "has_fulltext": True,
                                "open_access": {"is_oa": True, "oa_url": "https://oa.example.org/w777.pdf"},
                                "best_oa_location": {
                                    "is_oa": True,
                                    "pdf_url": "https://oa.example.org/w777.pdf",
                                    "landing_page_url": "https://oa.example.org/w777",
                                    "license": "cc-by",
                                },
                                "locations": [],
                                "authorships": [{"author": {"display_name": "Budi Hartono"}}],
                            }
                        ]
                    },
                )
            if "robots.txt" in u:
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            if "w777.pdf" in u:
                return httpx.Response(200, content=pdf_payload, headers={"Content-Type": "application/pdf"})
            return httpx.Response(404)

        def epmc_handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/search" in u:
                return httpx.Response(
                    200,
                    json={
                        "resultList": {
                            "result": [
                                {
                                    "pmcid": "PMC123456",
                                    "pmid": "987654",
                                    "doi": "10.5555/epmc.1",
                                    "title": "Europe PMC Full Study",
                                    "pubYear": "2024",
                                    "isOpenAccess": "Y",
                                    "license": "CC BY",
                                    "authorList": {"author": [{"fullName": "Dr. Maya Sari"}]},
                                    "fullTextUrlList": {"fullTextUrl": []},
                                }
                            ]
                        }
                    },
                )
            if "PMC123456/fullTextXML" in u:
                return httpx.Response(200, content=epmc_xml, headers={"Content-Type": "application/xml"})
            return httpx.Response(404)

        def searx_handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/search" in u:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "title": "Duplikat Karya OpenAlex via Web",
                                "url": "https://mirror.example.org/w777-copy",
                                "content": "Mirror copy",
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        sub_txt = (
            f"BAB I PENDAHULUAN\n\n{copied_sentence}\n\n"
            "Biomedical open access retrieval provides structured JATS XML paragraphs for similarity verification.\n\n"
            "Paragraf penutup ditulis asli oleh penulis sendiri."
        )
        v_sub = validate_local_bytes("naskah.txt", sub_txt.encode("utf-8"), 5_000_000)
        sub_doc = ingest_validated_upload(db, v_sub, role="SUBMISSION", title="Uji Sumber Web")
        sub_segs = db.query(Segment).filter(Segment.document_id == sub_doc.id).all()

        chk = Check(
            report_number="NG-P7-001",
            document_id=sub_doc.id,
            status="PROCESSING",
            stage="Penemuan Sumber",
            progress=20,
            settings={},
        )
        db.add(chk)
        db.commit()

        oa_prov = OpenAlexProvider(client=httpx.Client(transport=httpx.MockTransport(oa_handler)))
        epmc_prov = EuropePMCProvider(client=httpx.Client(transport=httpx.MockTransport(epmc_handler)))
        searx_prov = SearXNGWebSearchProvider(
            base_url="https://searx.example.org",
            client=httpx.Client(transport=httpx.MockTransport(searx_handler)),
        )
        assert searx_prov.is_configured() is True
        assert OfficialWebSearchAPIProvider().is_configured() is False

        cfg = CheckSettingsSchema(
            use_external_sources=True,
            enable_academic_search=True,
            enable_web_search=True,
            enable_fulltext_download=True,
            max_search_queries=2,
            external_providers=["openalex", "europe_pmc", "searxng"],
        )
        summary = discover_external_sources(
            db,
            check_id=chk.id,
            submission_doc=sub_doc,
            submission_segments=sub_segs,
            check_settings=cfg,
            providers_override={"openalex": oa_prov, "europe_pmc": epmc_prov, "searxng": searx_prov},
            resolve_dns=False,
        )
        assert len(summary.external_fulltext_doc_ids) == 2

        # Source deduplication test: same DOI from different repository URL does not duplicate Document
        dup = find_duplicate_source(
            db,
            doi="10.5555/oa.777",
            url="https://repo.kampus.ac.id/handle/12345",
            title="Arsitektur Penemuan Sumber Terbuka",
        )
        assert dup is not None
        assert "https://repo.kampus.ac.id/handle/12345" in (dup.alternate_urls or [])

        # Run full similarity pipeline against those newly indexed external sources (without re-running external discovery)
        chk.settings = CheckSettingsSchema(use_external_sources=False).model_dump()
        db.commit()
        run_check_pipeline(db, chk.id)
        db.refresh(chk)
        assert chk.status == "COMPLETED"
        assert chk.metrics["similarity_index"] > 50.0

        sources = db.query(CheckSource).filter(CheckSource.check_id == chk.id).all()
        assert len(sources) == 2
        acqs = db.query(SourceAcquisition).filter(SourceAcquisition.check_id == chk.id).all()
        assert any(a.status == "MATCH_VERIFIED" for a in acqs)
    finally:
        db.close()


def test_oai_pmh_harvester_and_registry_api(isolated_env):
    identify_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <Identify>
        <repositoryName>Jurnal Informatika Nusantara (OJS)</repositoryName>
        <protocolVersion>2.0</protocolVersion>
      </Identify>
    </OAI-PMH>"""

    formats_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <ListMetadataFormats>
        <metadataFormat><metadataPrefix>oai_dc</metadataPrefix></metadataFormat>
      </ListMetadataFormats>
    </OAI-PMH>"""

    page1_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <ListRecords>
        <record>
          <header><identifier>oai:ojs.kampus.ac.id:article/10</identifier><datestamp>2026-10-01</datestamp></header>
          <metadata><oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:title>Deteksi Kemiripan Skripsi Menggunakan Winnowing</dc:title>
            <dc:creator>Andi Wijaya</dc:creator>
            <dc:date>2026</dc:date>
            <dc:identifier>10.1234/jik.2026.10</dc:identifier>
            <dc:identifier>https://jurnal.kampus.ac.id/index.php/jik/article/download/10/pdf</dc:identifier>
          </oai_dc:dc></metadata>
        </record>
        <resumptionToken>tok2</resumptionToken>
      </ListRecords>
    </OAI-PMH>"""

    page2_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <ListRecords>
        <record>
          <header><identifier>oai:ojs.kampus.ac.id:article/11</identifier><datestamp>2026-10-05</datestamp></header>
          <metadata><oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:title>Artikel Metadata Saja Tanpa PDF</dc:title>
            <dc:creator>Dewi Lestari</dc:creator>
            <dc:date>2026</dc:date>
          </oai_dc:dc></metadata>
        </record>
      </ListRecords>
    </OAI-PMH>"""

    pdf_raw = _pdf_bytes("Deteksi Kemiripan Skripsi Menggunakan Winnowing berhasil diindeks dari OJS Indonesia.")

    def oai_handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if "robots.txt" in u:
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if "verb=Identify" in u:
            return httpx.Response(200, text=identify_xml)
        if "verb=ListMetadataFormats" in u:
            return httpx.Response(200, text=formats_xml)
        if "resumptionToken=tok2" in u:
            return httpx.Response(200, text=page2_xml)
        if "verb=ListRecords" in u:
            return httpx.Response(200, text=page1_xml)
        if "article/download/10/pdf" in u:
            return httpx.Response(200, content=pdf_raw, headers={"Content-Type": "application/pdf"})
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(oai_handler))
    db = get_session_factory()()
    try:
        repo = OAIRepository(
            name="Jurnal Kampus",
            base_url="https://jurnal.kampus.ac.id/index.php/jik/oai",
            repo_type="ojs",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

        res = harvest_oai_repository(db, repo, max_records=10, download_pdfs=True, client=mock_client, resolve_dns=False)
        assert res["records_harvested"] == 2
        assert res["fulltext_indexed"] == 1
        assert res["metadata_only"] == 1  # Metadata-only record MUST NOT be indexed as full-text!
        assert repo.last_datestamp == "2026-10-05"
        assert repo.identified_name == "Jurnal Informatika Nusantara (OJS)"

        corpus_docs = db.query(Document).filter(Document.role == "CORPUS").all()
        assert len(corpus_docs) == 1
        assert corpus_docs[0].doi == "10.1234/jik.2026.10"
    finally:
        db.close()

    # Verify OAI-PMH Registry API rejects SSRF localhost URL & supports CRUD
    app = create_app()
    with TestClient(app) as client:
        bad = client.post("/api/oai/repositories", json={"name": "Local", "base_url": "http://127.0.0.1:9000/oai"})
        assert bad.status_code == 400
        good = client.post("/api/oai/repositories", json={"name": "OJS UI", "base_url": "https://jurnal.ui.ac.id/oai", "repo_type": "ojs"})
        assert good.status_code == 201
        assert len(client.get("/api/oai/repositories").json()) >= 1
        assert client.get("/api/providers/monitor").status_code == 200


def test_playwright_isolated_browser_context_available():
    """Verify Playwright Chromium launches cleanly in an isolated ephemeral context (no personal profile/cookies)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_content("<html><body><main id='app'></main><script>document.getElementById('app').textContent='Konten JS Terender Secara Aman';</script></body></html>")
        txt = page.locator("#app").inner_text()
        assert txt == "Konten JS Terender Secara Aman"
        assert len(ctx.cookies()) == 0
        ctx.close()
        browser.close()
