"""Comprehensive Phase 10.3 tests for Academic Repository Reliability & OAI-PMH Harvesting.

Covers all 18+ required scenarios:
- DSpace 7, Legacy DSpace, OJS, EPrints endpoints & platform detection
- Valid & invalid endpoints, SSRF blocking, HTML-instead-of-XML
- Unsupported metadataPrefix negotiation (cannotDisseminateFormat)
- Empty repository (noRecordsMatch), noSetHierarchy
- Multi-page pagination with opaque resumptionToken
- Expired resumptionToken (badResumptionToken) automatic recovery
- Deleted records (<header status="deleted">)
- Safe HTTP redirects & SSRF-blocked redirects
- Timeout preserving partial page progress
- Accessible PDF full-text indexing vs inaccessible PDF (403) + retry-failed
- Duplicate DOI deduplication
- Pause / Resume cursor preservation
- API E2E regressions (Bug #1 repo_type="OAI-PMH", Bug #2 empty harvest POST body, PUT edit, logs, records)
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_session_factory, init_db
from app.main import create_app
from app.models import Document, OAIHarvestLog, OAIHarvestRecord, OAIRepository
from app.sources.oai_pmh import (
    OAIPMHProtocolError,
    auto_detect_oai_endpoint,
    clean_oai_base_url,
    detect_platform_from_url,
    get_repository_funnel,
    harvest_oai_repository,
    preview_oai_records,
    retry_failed_oai_records,
    run_connection_wizard,
)


def _sample_pdf_bytes(text: str) -> bytes:
    """Build a valid multi-sentence PDF using PyMuPDF so full-text extraction succeeds cleanly."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _xml_identify(name: str, base_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <responseDate>2026-11-25T10:00:00Z</responseDate>
  <request verb="Identify">{base_url}</request>
  <Identify>
    <repositoryName>{name}</repositoryName>
    <baseURL>{base_url}</baseURL>
    <protocolVersion>2.0</protocolVersion>
    <earliestDatestamp>2018-01-01</earliestDatestamp>
    <deletedRecord>persistent</deletedRecord>
    <granularity>YYYY-MM-DD</granularity>
  </Identify>
</OAI-PMH>"""


def _xml_formats(prefixes: list[str]) -> str:
    items = "\n".join(
        f"<metadataFormat><metadataPrefix>{p}</metadataPrefix><schema>http://example.org/{p}.xsd</schema></metadataFormat>"
        for p in prefixes
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListMetadataFormats>{items}</ListMetadataFormats>
</OAI-PMH>"""


def _xml_sets(sets: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f"<set><setSpec>{sp}</setSpec><setName>{nm}</setName></set>" for sp, nm in sets
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListSets>{items}</ListSets>
</OAI-PMH>"""


def _xml_error(code: str, msg: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <error code="{code}">{msg}</error>
</OAI-PMH>"""


def _xml_records(records_xml: str, token: str | None = None) -> str:
    tok_xml = f"<resumptionToken>{token}</resumptionToken>" if token else "<resumptionToken/>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    {records_xml}
    {tok_xml}
  </ListRecords>
</OAI-PMH>"""


def _dc_record(
    oai_id: str,
    title: str,
    *,
    datestamp: str = "2026-06-01",
    author: str = "Ahmad Fauzi",
    year: str = "2025",
    doi: str | None = None,
    urls: list[str] | None = None,
    set_spec: str = "col_1",
) -> str:
    id_tags = ""
    if doi:
        id_tags += f"<dc:identifier>https://doi.org/{doi}</dc:identifier>"
    for u in urls or []:
        id_tags += f"<dc:identifier>{u}</dc:identifier>"
    return f"""
    <record>
      <header>
        <identifier>{oai_id}</identifier>
        <datestamp>{datestamp}</datestamp>
        <setSpec>{set_spec}</setSpec>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>{title}</dc:title>
          <dc:creator>{author}</dc:creator>
          <dc:date>{year}-05-10</dc:date>
          <dc:rights>CC-BY-4.0</dc:rights>
          {id_tags}
        </oai_dc:dc>
      </metadata>
    </record>"""


def _deleted_record(oai_id: str, datestamp: str = "2026-06-02") -> str:
    return f"""
    <record>
      <header status="deleted">
        <identifier>{oai_id}</identifier>
        <datestamp>{datestamp}</datestamp>
      </header>
    </record>"""


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase10_3_oai.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    engine = init_db(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Platform detection & URL normalization (DSpace 7, Legacy DSpace, OJS, EPrints)
# ---------------------------------------------------------------------------
def test_endpoint_patterns_and_non_destructive_cleaning():
    assert detect_platform_from_url("https://repo.kampus.example/server/oai/request") == "dspace7"
    assert detect_platform_from_url("https://repo.kampus.example/oai/request") == "dspace_legacy"
    assert detect_platform_from_url("https://repo.kampus.example/dspace-oai/request") == "dspace_legacy"
    assert detect_platform_from_url("https://jurnal.kampus.example/index.php/alafaq/oai") == "ojs"
    assert detect_platform_from_url("https://jurnal.kampus.example/alafaq/oai") == "ojs"
    assert detect_platform_from_url("https://eprints.kampus.example/cgi/oai2") == "eprints"

    cleaned, changed = clean_oai_base_url("https://repo.kampus.example/server/oai/request?verb=Identify")
    assert changed is True
    assert cleaned == "https://repo.kampus.example/server/oai/request"


# ---------------------------------------------------------------------------
# 2. DSpace 7 auto-detection & bitstream PDF harvesting
# ---------------------------------------------------------------------------
def test_dspace7_auto_detect_and_bitstream_harvest(isolated_db):
    pdf_bytes = _sample_pdf_bytes(
        "Penelitian ini menganalisis tata kelola sistem repositori akademik DSpace 7 di perguruan tinggi Indonesia secara komprehensif dan terukur."
    )
    dspace_oai = "https://dspace7.kampus.example/server/oai/request"
    bitstream_url = "https://dspace7.kampus.example/server/api/core/bitstreams/1111-2222-3333/content"

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str.startswith("https://dspace7.kampus.example/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if url_str == bitstream_url:
            return httpx.Response(200, content=pdf_bytes, headers={"Content-Type": "application/pdf"})
        if urlparse(url_str).path == "/server/oai/request":
            verb = q.get("verb", [""])[0]
            if verb == "Identify":
                return httpx.Response(200, text=_xml_identify("Repositori DSpace 7 Kampus", dspace_oai))
            if verb == "ListMetadataFormats":
                return httpx.Response(200, text=_xml_formats(["oai_dc", "dim", "xoai"]))
            if verb == "ListSets":
                return httpx.Response(200, text=_xml_sets([("col_12345_1", "Skripsi & Tesis")]))
            if verb == "ListRecords":
                rec = _dc_record(
                    "oai:dspace7.kampus.example:12345/101",
                    "Implementasi Arsitektur DSpace 7 untuk Repositori Skripsi",
                    doi="10.1234/dspace7.101",
                    urls=[bitstream_url],
                )
                return httpx.Response(200, text=_xml_records(rec))
        return httpx.Response(200, text="<html><body>Portal DSpace 7</body></html>", headers={"Content-Type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    det = auto_detect_oai_endpoint("https://dspace7.kampus.example", client=client, resolve_dns=False)
    assert det["found"] is True
    assert det["detected_url"] == dspace_oai
    assert det["platform_detected"] == "dspace7"

    repo = OAIRepository(name="DSpace 7 Test", base_url=dspace_oai, repo_type="dspace7")
    isolated_db.add(repo)
    isolated_db.commit()

    summary = harvest_oai_repository(isolated_db, repo, max_records=5, download_pdfs=True, client=client, resolve_dns=False)
    assert summary["records_harvested"] == 1
    assert summary["fulltext_indexed"] == 1
    funnel = get_repository_funnel(isolated_db, repo)
    assert funnel["metadata_saved"] == 1
    assert funnel["pdf_urls_found"] == 1
    assert funnel["pdf_accessible"] == 1
    assert funnel["document_indexed"] == 1


# ---------------------------------------------------------------------------
# 3. Legacy DSpace (/oai/request & /dspace-oai/request) + DIM format + /bitstream/
# ---------------------------------------------------------------------------
def test_legacy_dspace_dim_and_bitstream_harvest(isolated_db):
    oai_url = "https://legacy.kampus.example/dspace-oai/request"
    pdf_url = "https://legacy.kampus.example/bitstream/handle/12345/9/tesis.pdf"
    pdf_bytes = _sample_pdf_bytes(
        "Kajian hukum ekonomi syariah pada lembaga keuangan mikro berbasis masyarakat di Jawa Timur menggunakan metode kualitatif deskriptif."
    )

    dim_records = f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:legacy.kampus.example:12345/9</identifier>
        <datestamp>2025-11-01</datestamp>
      </header>
      <metadata>
        <dim:dim xmlns:dim="http://www.dspace.org/xmlns/dspace/dim">
          <dim:field mdschema="dc" element="title">Kajian Hukum Ekonomi Syariah pada Lembaga Keuangan Mikro</dim:field>
          <dim:field mdschema="dc" element="contributor" qualifier="author">Siti Rahmawati</dim:field>
          <dim:field mdschema="dc" element="date" qualifier="issued">2025</dim:field>
          <dim:field mdschema="dc" element="identifier" qualifier="uri">{pdf_url}</dim:field>
        </dim:dim>
      </metadata>
    </record>
  </ListRecords>
</OAI-PMH>"""

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str.endswith("/robots.txt"):
            return httpx.Response(404)
        if url_str == pdf_url:
            return httpx.Response(200, content=pdf_bytes, headers={"Content-Type": "application/pdf"})
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("DSpace Lama Kampus", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["dim"]))
        if verb == "ListSets":
            return httpx.Response(200, text=_xml_error("noSetHierarchy", "No sets configured"))
        if verb == "ListRecords":
            if q.get("metadataPrefix", [""])[0] != "dim":
                return httpx.Response(200, text=_xml_error("cannotDisseminateFormat", "oai_dc unsupported"))
            return httpx.Response(200, text=dim_records)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    wizard = run_connection_wizard(oai_url, metadata_prefix="oai_dc", client=client, resolve_dns=False)
    assert wizard["ok"] is True
    assert wizard["recommended_prefix"] == "dim"
    # Stage 4 should WARN cannotDisseminateFormat and recommend dim; Stage 5 should WARN noSetHierarchy
    st4 = next(s for s in wizard["stages"] if s["step"] == 4)
    st5 = next(s for s in wizard["stages"] if s["step"] == 5)
    assert st4["status"] == "WARN" and st4["error_code"] == "cannotDisseminateFormat"
    assert st5["status"] == "WARN" and st5["error_code"] == "noSetHierarchy"

    repo = OAIRepository(name="Legacy DSpace", base_url=oai_url, repo_type="dspace_legacy", metadata_prefix="oai_dc")
    isolated_db.add(repo)
    isolated_db.commit()
    summary = harvest_oai_repository(isolated_db, repo, max_records=5, download_pdfs=True, client=client, resolve_dns=False)
    assert summary["fulltext_indexed"] == 1
    assert repo.metadata_prefix == "dim"


# ---------------------------------------------------------------------------
# 4. OJS (/index.php/{journal}/oai) + citation_pdf_url discovery on landing page
# ---------------------------------------------------------------------------
def test_ojs_landing_citation_pdf_discovery(isolated_db):
    oai_url = "https://jurnal.kampus.example/index.php/alafaq/oai"
    landing_url = "https://jurnal.kampus.example/index.php/alafaq/article/view/42"
    pdf_url = "https://jurnal.kampus.example/index.php/alafaq/article/download/42/99"
    pdf_bytes = _sample_pdf_bytes(
        "Analisis metode hisab awal bulan kamariah dalam perspektif ilmu falak kontemporer di Indonesia dengan perbandingan algoritma astronomi modern."
    )

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if url_str == landing_url:
            html = f'<html><head><meta name="citation_pdf_url" content="{pdf_url}"></head><body>Artikel OJS</body></html>'
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        if url_str == pdf_url:
            return httpx.Response(200, content=pdf_bytes, headers={"Content-Type": "application/pdf"})
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Jurnal Al-Afaq (Open Journal Systems)", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            rec = _dc_record(
                "oai:ojs.kampus.example:article/42",
                "Analisis Metode Hisab Awal Bulan Kamariah dalam Perspektif Ilmu Falak",
                urls=[landing_url],
            )
            return httpx.Response(200, text=_xml_records(rec))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Jurnal Al-Afaq", base_url=oai_url, repo_type="ojs")
    isolated_db.add(repo)
    isolated_db.commit()

    summary = harvest_oai_repository(isolated_db, repo, max_records=5, download_pdfs=True, client=client, resolve_dns=False)
    assert summary["records_harvested"] == 1
    assert summary["fulltext_indexed"] == 1
    assert repo.platform_detected == "ojs"


# ---------------------------------------------------------------------------
# 5. EPrints (/cgi/oai2) + Full 8-Stage Wizard PASS + Preview
# ---------------------------------------------------------------------------
def test_eprints_8_stage_wizard_and_preview():
    oai_url = "https://eprints.kampus.example/cgi/oai2"
    pdf_url = "https://eprints.kampus.example/1234/1/skripsi_lengkap.pdf"

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str == pdf_url:
            return httpx.Response(200, content=b"%PDF-1.4\n...", headers={"Content-Type": "application/pdf"})
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("EPrints Kampus Merdeka", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc", "didl"]))
        if verb == "ListSets":
            return httpx.Response(200, text=_xml_sets([("7374617475733D707562", "Published")]))
        if verb == "ListRecords":
            rec = _dc_record(
                "oai:eprints.kampus.example:1234",
                "Model Evaluasi Kualitas Pembelajaran Daring di Perguruan Tinggi",
                doi="10.9999/eprints.1234",
                urls=[pdf_url],
            )
            return httpx.Response(200, text=_xml_records(rec))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = run_connection_wizard(oai_url, probe_pdf=True, client=client, resolve_dns=False)
    assert report["ok"] is True
    assert report["overall_status"] == "READY"
    assert report["platform_detected"] == "eprints"
    assert len(report["stages"]) == 8
    assert all(s["status"] == "PASS" for s in report["stages"])
    assert len(report["sample_records"]) == 1
    assert report["sample_records"][0]["pdf_urls"] == [pdf_url]

    prev = preview_oai_records(oai_url, client=client, resolve_dns=False)
    assert prev["count"] == 1
    assert prev["records"][0]["doi"] == "10.9999/eprints.1234"


# ---------------------------------------------------------------------------
# 6. Invalid Endpoint (404 / SSRF / Malformed) & HTML-Instead-of-XML
# ---------------------------------------------------------------------------
def test_invalid_endpoint_ssrf_and_html_instead_of_xml():
    # SSRF loopback blocked cleanly at stage 1
    ssrf_rep = run_connection_wizard("http://127.0.0.1:8000/oai", resolve_dns=False)
    assert ssrf_rep["ok"] is False
    assert ssrf_rep["stages"][0]["status"] == "FAIL"
    assert ssrf_rep["stages"][0]["error_code"] == "SSRF_BLOCKED"

    # Malformed URL blocked at stage 1
    bad_url = run_connection_wizard("ftp://kampus.example/oai", resolve_dns=False)
    assert bad_url["ok"] is False
    assert bad_url["stages"][0]["error_code"] == "INVALID_URL"

    # HTTP 404 failed cleanly at stage 2
    client_404 = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(404, text="Not found")))
    rep_404 = run_connection_wizard("https://kampus.example/wrong/oai", client=client_404, resolve_dns=False)
    assert rep_404["ok"] is False
    st2 = next(s for s in rep_404["stages"] if s["step"] == 2)
    assert st2["status"] == "FAIL" and st2["error_code"] == "HTTP_404" and st2["http_status"] == 404

    # HTML instead of XML -> Stage 2 PASS (HTTP 200), Stage 3 FAIL with HTML_RESPONSE + Indonesian suggestion
    client_html = httpx.Client(
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(
                200,
                text="<!DOCTYPE html><html><head><title>Portal</title></head><body>Halo</body></html>",
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        )
    )
    rep_html = run_connection_wizard("https://kampus.example/", client=client_html, resolve_dns=False)
    assert rep_html["ok"] is False
    st2_h = next(s for s in rep_html["stages"] if s["step"] == 2)
    st3_h = next(s for s in rep_html["stages"] if s["step"] == 3)
    assert st2_h["status"] == "PASS"
    assert st3_h["status"] == "FAIL"
    assert st3_h["error_code"] == "HTML_RESPONSE"
    assert "HTML" in st3_h["message"]
    assert st3_h["suggestion"]


# ---------------------------------------------------------------------------
# 7. Empty Repository (noRecordsMatch) handled gracefully
# ---------------------------------------------------------------------------
def test_empty_repository_no_records_match(isolated_db):
    oai_url = "https://empty.kampus.example/oai/request"

    def handler(req: httpx.Request) -> httpx.Response:
        verb = parse_qs(urlparse(str(req.url)).query).get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Repositori Kosong", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListSets":
            return httpx.Response(200, text=_xml_sets([]))
        if verb == "ListRecords":
            return httpx.Response(200, text=_xml_error("noRecordsMatch", "No records found"))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    wizard = run_connection_wizard(oai_url, client=client, resolve_dns=False)
    assert wizard["ok"] is True
    assert wizard["overall_status"] == "PARTIAL"
    st6 = next(s for s in wizard["stages"] if s["step"] == 6)
    assert st6["status"] == "WARN" and st6["error_code"] == "noRecordsMatch"

    repo = OAIRepository(name="Empty Repo", base_url=oai_url, repo_type="dspace_legacy")
    isolated_db.add(repo)
    isolated_db.commit()
    summary = harvest_oai_repository(isolated_db, repo, max_records=10, download_pdfs=False, client=client, resolve_dns=False)
    assert summary["records_harvested"] == 0
    assert summary["status"] == "VERIFIED"
    assert repo.harvest_state == "COMPLETED"


# ---------------------------------------------------------------------------
# 8. Pagination, Expired resumptionToken Recovery, & Deleted Records
# ---------------------------------------------------------------------------
def test_pagination_expired_token_recovery_and_deleted_records(isolated_db):
    oai_url = "https://paged.kampus.example/cgi/oai2"
    expired_triggered = {"count": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        q = parse_qs(urlparse(str(req.url)).query)
        verb = q.get("verb", [""])[0]
        tok = q.get("resumptionToken", [None])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Paged EPrints", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            if tok == "expired-tok-000":
                expired_triggered["count"] += 1
                return httpx.Response(200, text=_xml_error("badResumptionToken", "Token expired"))
            if tok == "page-2-token":
                xml = _dc_record("oai:paged:2", "Artikel Halaman Kedua Penelitian Sosial", datestamp="2026-06-05") + _deleted_record("oai:paged:del1")
                return httpx.Response(200, text=_xml_records(xml, token=None))
            # Page 1
            xml = _dc_record("oai:paged:1", "Artikel Halaman Pertama Analisis Data", datestamp="2026-06-01")
            return httpx.Response(200, text=_xml_records(xml, token="page-2-token"))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(
        name="Paged Repo",
        base_url=oai_url,
        repo_type="eprints",
        resumption_token="expired-tok-000",
    )
    isolated_db.add(repo)
    isolated_db.commit()

    # Resume with expired token -> recovers cleanly, harvests page 1 + page 2 + records deleted item
    summary = harvest_oai_repository(
        isolated_db,
        repo,
        max_records=10,
        download_pdfs=False,
        resume=True,
        client=client,
        resolve_dns=False,
    )
    assert expired_triggered["count"] == 1
    assert summary["pages_fetched"] == 2
    assert summary["records_harvested"] == 2
    assert summary["deleted_skipped"] == 1
    assert repo.resumption_token is None

    del_row = (
        isolated_db.query(OAIHarvestRecord)
        .filter(OAIHarvestRecord.repository_id == repo.id, OAIHarvestRecord.oai_identifier == "oai:paged:del1")
        .first()
    )
    assert del_row is not None
    assert del_row.deleted is True
    assert del_row.status == "DELETED"

    recovery_log = (
        isolated_db.query(OAIHarvestLog)
        .filter(OAIHarvestLog.repository_id == repo.id, OAIHarvestLog.stage == "TOKEN_RECOVERY")
        .first()
    )
    assert recovery_log is not None


# ---------------------------------------------------------------------------
# 9. Safe Redirects & SSRF Redirect Blocking
# ---------------------------------------------------------------------------
def test_safe_redirect_and_ssrf_redirect_blocked():
    final_url = "https://www.kampus.example/server/oai/request"

    def ok_redir_handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "kampus.example":
            return httpx.Response(301, headers={"Location": final_url + "?verb=Identify"})
        q = parse_qs(urlparse(str(req.url)).query)
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Redirected DSpace 7", final_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListSets":
            return httpx.Response(200, text=_xml_sets([]))
        if verb == "ListRecords":
            return httpx.Response(200, text=_xml_records(_dc_record("oai:r:1", "Artikel Redirect Aman")))
        return httpx.Response(404)

    client_ok = httpx.Client(transport=httpx.MockTransport(ok_redir_handler))
    rep = run_connection_wizard("http://kampus.example/server/oai/request", client=client_ok, resolve_dns=False)
    assert rep["ok"] is True
    assert rep["effective_url"].startswith("https://www.kampus.example/server/oai/request")

    # Evil redirect to 127.0.0.1 MUST be blocked by SSRF check!
    client_evil = httpx.Client(
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})
        )
    )
    rep_evil = run_connection_wizard("https://evil.kampus.example/oai", client=client_evil, resolve_dns=False)
    assert rep_evil["ok"] is False
    st2 = next(s for s in rep_evil["stages"] if s["step"] == 2)
    assert st2["status"] == "FAIL" and st2["error_code"] == "SSRF_BLOCKED"


# ---------------------------------------------------------------------------
# 10. Timeout Preserves Partial Progress & Saved Cursor
# ---------------------------------------------------------------------------
def test_timeout_mid_harvest_preserves_page1_progress(isolated_db):
    oai_url = "https://slow.kampus.example/oai/request"

    def handler(req: httpx.Request) -> httpx.Response:
        q = parse_qs(urlparse(str(req.url)).query)
        verb = q.get("verb", [""])[0]
        tok = q.get("resumptionToken", [None])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Slow Repo", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            if tok == "tok-page-2":
                raise httpx.ReadTimeout("Simulated read timeout on page 2")
            return httpx.Response(
                200,
                text=_xml_records(_dc_record("oai:slow:1", "Artikel Sebelum Timeout"), token="tok-page-2"),
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Slow Repo", base_url=oai_url, repo_type="dspace_legacy")
    isolated_db.add(repo)
    isolated_db.commit()

    with pytest.raises(OAIPMHProtocolError) as exc_info:
        harvest_oai_repository(isolated_db, repo, max_records=10, download_pdfs=False, client=client, resolve_dns=False)
    assert exc_info.value.error_code == "TIMEOUT"

    isolated_db.refresh(repo)
    assert repo.status == "ERROR"
    assert repo.harvest_state == "ERROR"
    assert repo.resumption_token == "tok-page-2"
    assert repo.records_harvested == 1


# ---------------------------------------------------------------------------
# 11. Inaccessible PDF (403) Kept as Metadata Only + Retry Failed Recovery
# ---------------------------------------------------------------------------
def test_pdf_inaccessible_then_retry_failed_succeeds(isolated_db):
    oai_url = "https://mixed.kampus.example/cgi/oai2"
    pdf_url = "https://mixed.kampus.example/99/1/artikel.pdf"
    pdf_bytes = _sample_pdf_bytes(
        "Evaluasi kebijakan literasi digital dan integritas publikasi ilmiah di lingkungan fakultas teknik secara mendalam."
    )
    allow_pdf = {"open": False}

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str.endswith("/robots.txt"):
            return httpx.Response(404)
        if url_str == pdf_url:
            if allow_pdf["open"]:
                return httpx.Response(200, content=pdf_bytes, headers={"Content-Type": "application/pdf"})
            return httpx.Response(403, text="Forbidden")
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Mixed Access Repo", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            return httpx.Response(
                200,
                text=_xml_records(
                    _dc_record("oai:mixed:99", "Evaluasi Kebijakan Literasi Digital", urls=[pdf_url])
                ),
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Mixed Repo", base_url=oai_url, repo_type="eprints")
    isolated_db.add(repo)
    isolated_db.commit()

    # Run 1: PDF returns 403 -> NEVER indexed as full-text!
    s1 = harvest_oai_repository(isolated_db, repo, max_records=5, download_pdfs=True, client=client, resolve_dns=False)
    assert s1["records_harvested"] == 1
    assert s1["fulltext_indexed"] == 0
    assert s1["failed_records"] == 1
    assert repo.fulltext_indexed == 0
    assert repo.failed_records_count == 1
    assert isolated_db.query(Document).count() == 0

    # Run 2: PDF becomes open -> retry_failed recovers & indexes it!
    allow_pdf["open"] = True
    retry_res = retry_failed_oai_records(isolated_db, repo, limit=10, client=client, resolve_dns=False)
    assert retry_res["retried"] == 1
    assert retry_res["recovered_indexed"] == 1
    assert retry_res["still_failed"] == 0
    isolated_db.refresh(repo)
    assert repo.fulltext_indexed == 1
    assert repo.failed_records_count == 0
    assert isolated_db.query(Document).count() == 1


# ---------------------------------------------------------------------------
# 12. Duplicate DOI Deduplication Across Records
# ---------------------------------------------------------------------------
def test_duplicate_doi_deduplicated(isolated_db):
    oai_url = "https://dup.kampus.example/oai/request"
    pdf_a = "https://dup.kampus.example/bitstream/1/paper_a.pdf"
    pdf_b = "https://dup.kampus.example/bitstream/2/paper_b.pdf"
    pdf_bytes = _sample_pdf_bytes(
        "Penelitian kuantitatif pengaruh kualitas tata kelola data akademik terhadap akurasi sistem deteksi kesamaan dokumen ilmiah."
    )

    def handler(req: httpx.Request) -> httpx.Response:
        url_str = str(req.url)
        q = parse_qs(urlparse(url_str).query)
        if url_str.endswith("/robots.txt"):
            return httpx.Response(404)
        if url_str in {pdf_a, pdf_b}:
            return httpx.Response(200, content=pdf_bytes, headers={"Content-Type": "application/pdf"})
        verb = q.get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Dup Repo", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            xml = _dc_record(
                "oai:dup:1",
                "Pengaruh Kualitas Tata Kelola Data Akademik",
                doi="10.5555/shared.doi.2026",
                urls=[pdf_a],
            ) + _dc_record(
                "oai:dup:2",
                "Versi Duplikat dengan DOI Sama",
                doi="10.5555/shared.doi.2026",
                urls=[pdf_b],
            )
            return httpx.Response(200, text=_xml_records(xml))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Dup DOI Repo", base_url=oai_url, repo_type="dspace_legacy")
    isolated_db.add(repo)
    isolated_db.commit()

    summary = harvest_oai_repository(isolated_db, repo, max_records=10, download_pdfs=True, client=client, resolve_dns=False)
    assert summary["fulltext_indexed"] == 1
    assert summary["duplicates_skipped"] == 1
    assert isolated_db.query(Document).count() == 1

    rec2 = (
        isolated_db.query(OAIHarvestRecord)
        .filter(OAIHarvestRecord.repository_id == repo.id, OAIHarvestRecord.oai_identifier == "oai:dup:2")
        .first()
    )
    assert rec2 is not None and rec2.status == "DUPLICATE"


# ---------------------------------------------------------------------------
# 13. API End-to-End Regressions (Bug #1, Bug #2, Edit, Pause, Records, Logs)
# ---------------------------------------------------------------------------
def test_oai_api_endpoints_and_regressions(tmp_path, monkeypatch):
    db_path = tmp_path / "api_oai.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()

    # Patch harvest_oai_repository in API layer to avoid live network in unit API test
    import app.api.oai as oai_api

    monkeypatch.setattr(
        oai_api,
        "harvest_oai_repository",
        lambda db, repo, **kw: {
            "repository": repo.name,
            "records_harvested": 3,
            "fulltext_indexed": 2,
            "metadata_only": 1,
            "status": "VERIFIED",
        },
    )

    with TestClient(app) as tc:
        # Reference endpoints
        refs = tc.get("/api/oai/reference-endpoints")
        assert refs.status_code == 200
        assert len(refs.json()) >= 1

        # Regression for Critical Bug #1: repo_type="OAI-PMH" used to return 422!
        create_res = tc.post(
            "/api/oai/repositories",
            json={
                "name": "Repositori Uji API",
                "base_url": "https://repo.kampus.example/server/oai/request",
                "repo_type": "OAI-PMH",
            },
        )
        assert create_res.status_code == 201, create_res.text
        repo_data = create_res.json()
        repo_id = repo_data["id"]
        assert repo_data["platform_detected"] == "dspace7"

        # Edit repository via PUT
        put_res = tc.put(
            f"/api/oai/repositories/{repo_id}",
            json={"name": "Repositori DSpace 7 Diedit", "selected_set": "col_skripsi"},
        )
        assert put_res.status_code == 200
        assert put_res.json()["name"] == "Repositori DSpace 7 Diedit"
        assert put_res.json()["selected_set"] == "col_skripsi"

        # Regression for Critical Bug #2: POST /harvest with NO JSON body used to return 422!
        harv_res = tc.post(f"/api/oai/repositories/{repo_id}/harvest")
        assert harv_res.status_code == 200, harv_res.text
        assert harv_res.json()["summary"]["records_harvested"] == 3

        # Pause endpoint
        pause_res = tc.post(f"/api/oai/repositories/{repo_id}/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["repository"]["harvest_state"] == "PAUSED"

        # Detail, records, logs endpoints
        assert tc.get(f"/api/oai/repositories/{repo_id}").status_code == 200
        assert tc.get(f"/api/oai/repositories/{repo_id}/records").status_code == 200
        logs_res = tc.get(f"/api/oai/repositories/{repo_id}/logs")
        assert logs_res.status_code == 200
        assert len(logs_res.json()) >= 3  # CREATE + UPDATE + PAUSE

        # Delete
        del_res = tc.delete(f"/api/oai/repositories/{repo_id}")
        assert del_res.status_code == 200 and del_res.json()["deleted"] is True


# ---------------------------------------------------------------------------
# 14. Pause & Resume Preserves Cursor Across Sessions
# ---------------------------------------------------------------------------
def test_pause_and_resume_preserves_cursor(isolated_db):
    oai_url = "https://resume.kampus.example/oai/request"

    def handler(req: httpx.Request) -> httpx.Response:
        q = parse_qs(urlparse(str(req.url)).query)
        verb = q.get("verb", [""])[0]
        tok = q.get("resumptionToken", [None])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_xml_identify("Resumable Repo", oai_url))
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_xml_formats(["oai_dc"]))
        if verb == "ListRecords":
            if tok == "cursor-page-2":
                return httpx.Response(
                    200,
                    text=_xml_records(_dc_record("oai:res:2", "Rekaman Sesi Lanjutan"), token=None),
                )
            return httpx.Response(
                200,
                text=_xml_records(_dc_record("oai:res:1", "Rekaman Sesi Pertama"), token="cursor-page-2"),
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = OAIRepository(name="Resume Repo", base_url=oai_url, repo_type="dspace_legacy")
    isolated_db.add(repo)
    isolated_db.commit()

    # Session 1 stops at max_records=1, saving resumption_token="cursor-page-2"
    s1 = harvest_oai_repository(isolated_db, repo, max_records=1, download_pdfs=False, client=client, resolve_dns=False)
    assert s1["records_harvested"] == 1
    assert s1["has_more"] is True
    assert repo.resumption_token == "cursor-page-2"

    # Session 2 resumes from saved cursor-page-2 and completes!
    s2 = harvest_oai_repository(isolated_db, repo, max_records=5, download_pdfs=False, resume=True, client=client, resolve_dns=False)
    assert s2["records_harvested"] == 1
    assert s2["has_more"] is False
    isolated_db.refresh(repo)
    assert repo.records_harvested == 2
    assert repo.resumption_token is None

