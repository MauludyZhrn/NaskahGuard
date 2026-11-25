"""Phase 10.4.1 Mock & Integration Tests: UNDIP EPrints Integration, Policy Enforcement & 4 Error Categories."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_session_factory, init_db
from app.main import create_app
from app.models import Document, OAIHarvestLog, OAIHarvestRecord, OAIRepository, RepositoryCatalogEntry
from app.sources.oai_catalog import ensure_catalog_seeded, promote_catalog_entry_to_personal, test_catalog_entry as probe_catalog
from app.sources.oai_pmh import (
    OAIPMHProtocolError,
    clean_oai_base_url,
    harvest_oai_repository,
    run_connection_wizard,
)


def _undip_identify_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <Identify>
    <repositoryName>Undip Repository</repositoryName>
    <baseURL>https://eprints2.undip.ac.id/cgi/oai2</baseURL>
    <protocolVersion>2.0</protocolVersion>
    <adminEmail>lisensi@live.undip.ac.id</adminEmail>
    <earliestDatestamp>2019-12-30T01:04:29Z</earliestDatestamp>
    <deletedRecord>persistent</deletedRecord>
    <granularity>YYYY-MM-DDThh:mm:ssZ</granularity>
  </Identify>
</OAI-PMH>"""


def _undip_formats_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListMetadataFormats>
    <metadataFormat><metadataPrefix>didl</metadataPrefix></metadataFormat>
    <metadataFormat><metadataPrefix>mets</metadataPrefix></metadataFormat>
    <metadataFormat><metadataPrefix>oai_bibl</metadataPrefix></metadataFormat>
    <metadataFormat><metadataPrefix>oai_dc</metadataPrefix></metadataFormat>
    <metadataFormat><metadataPrefix>rdf</metadataPrefix></metadataFormat>
    <metadataFormat><metadataPrefix>uketd_dc</metadataPrefix></metadataFormat>
  </ListMetadataFormats>
</OAI-PMH>"""


def _undip_sets_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListSets>
    <set><setSpec>7374617475733D707562</setSpec><setName>Status = Published</setName></set>
    <set><setSpec>7375626A656374733D666562</setSpec><setName>Economics and Business</setName></set>
  </ListSets>
</OAI-PMH>"""


def _undip_list_records_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:eprints2.undip.ac.id:107</identifier>
        <datestamp>2020-02-01T10:00:00Z</datestamp>
        <setSpec>7374617475733D707562</setSpec>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:relation>https://eprints2.undip.ac.id/id/eprint/107/</dc:relation>
          <dc:title>Chinese zodiac effect and precious metals returns</dc:title>
          <dc:creator>Kusumaningrum, Hermin</dc:creator>
          <dc:date>2019</dc:date>
          <dc:type>Article</dc:type>
          <dc:rights>UNDIP Repository Policy</dc:rights>
          <dc:identifier>https://eprints2.undip.ac.id/id/eprint/107/1/Chinese%20zodiac%20effect.pdf</dc:identifier>
        </oai_dc:dc>
      </metadata>
    </record>
    <resumptionToken completeListSize="45000">metadataPrefix%3Doai_dc%26offset%3D108</resumptionToken>
  </ListRecords>
</OAI-PMH>"""


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase10_4_1_undip.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NG_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("NG_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("NG_API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    engine = init_db(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def test_four_error_categories_and_https_port_normalization():
    # URL port :443 normalization on clean_oai_base_url without silently mutating stored DB beforehand
    cleaned, changed = clean_oai_base_url("https://eprints2.undip.ac.id:443/cgi/oai2?verb=Identify")
    assert changed is True
    assert cleaned == "https://eprints2.undip.ac.id/cgi/oai2"

    # 1. HTTP_CONNECTION_FAILURE (ConnectError / TLS_ERROR)
    def tls_fail(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed")

    rep_tls = run_connection_wizard(
        "https://broken-tls.kampus.ac.id/cgi/oai2",
        client=httpx.Client(transport=httpx.MockTransport(tls_fail)),
        resolve_dns=False,
    )
    assert rep_tls["ok"] is False
    assert rep_tls["failure_category"] == "HTTP_CONNECTION_FAILURE"
    st2 = next(s for s in rep_tls["stages"] if s["step"] == 2)
    assert st2["error_code"] == "TLS_ERROR"
    assert "CERTIFICATE_VERIFY_FAILED" in st2["message"]

    # 2. OAI_PROTOCOL_FAILURE (badVerb / HTML / OAI error)
    rep_oai = run_connection_wizard(
        "https://bad-oai.kampus.ac.id/cgi/oai2",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _r: httpx.Response(
                    200,
                    text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><error code="badVerb">Illegal verb</error></OAI-PMH>',
                )
            )
        ),
        resolve_dns=False,
    )
    assert rep_oai["ok"] is False
    assert rep_oai["failure_category"] == "OAI_PROTOCOL_FAILURE"

    # 3. METADATA_PARSING_FAILURE (XML_PARSE_ERROR)
    rep_xml = run_connection_wizard(
        "https://broken-xml.kampus.ac.id/cgi/oai2",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _r: httpx.Response(200, text="<OAI-PMH><broken-unclosed>", headers={"Content-Type": "text/xml"})
            )
        ),
        resolve_dns=False,
    )
    assert rep_xml["ok"] is False
    assert rep_xml["failure_category"] == "METADATA_PARSING_FAILURE"

    # 4. FULLTEXT_ACCESS_RESTRICTION classification
    err_pol = OAIPMHProtocolError("POLICY_RESTRICTED")
    assert err_pol.error_category == "FULLTEXT_ACCESS_RESTRICTION"


def test_undip_preset_legacy_redirect_and_metadata_only_policy(isolated_db):
    ensure_catalog_seeded(isolated_db)
    undip = (
        isolated_db.query(RepositoryCatalogEntry)
        .filter(RepositoryCatalogEntry.base_url == "https://eprints2.undip.ac.id/cgi/oai2")
        .first()
    )
    assert undip is not None
    assert undip.name == "UNDIP Institutional Repository"
    assert undip.platform == "eprints"
    assert undip.legacy_url == "http://eprints.undip.ac.id/cgi/oai2"
    assert undip.policy_url == "https://eprints2.undip.ac.id/policies.html"
    assert undip.oai_status == "UNVERIFIED"
    assert undip.default_download_pdfs is False
    assert undip.requires_verification_before_save is True
    assert undip.harvesting_permission_status == "METADATA_ALLOWED_FULLTEXT_RESTRICTED"

    pdf_download_attempted = {"called": False}

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if req.url.host == "eprints.undip.ac.id":
            return httpx.Response(
                301,
                headers={"Location": f"https://eprints2.undip.ac.id:443/cgi/oai2?{req.url.query.decode()}"},
            )
        if ".pdf" in u:
            pdf_download_attempted["called"] = True
            return httpx.Response(200, content=b"%PDF-1.4\n...")
        verb = parse_qs(urlparse(u).query).get("verb", [""])[0]
        if verb == "Identify":
            return httpx.Response(200, text=_undip_identify_xml())
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=_undip_formats_xml())
        if verb == "ListSets":
            return httpx.Response(200, text=_undip_sets_xml())
        if verb == "ListRecords":
            if parse_qs(urlparse(u).query).get("resumptionToken"):
                return httpx.Response(200, text='<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords/></OAI-PMH>')
            return httpx.Response(200, text=_undip_list_records_xml())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    # Also verify legacy 301 redirect resolves cleanly to normalized https://eprints2.undip.ac.id/cgi/oai2
    legacy_wiz = run_connection_wizard(
        "http://eprints.undip.ac.id/cgi/oai2",
        client=client,
        resolve_dns=False,
    )
    assert legacy_wiz["ok"] is True
    assert legacy_wiz["effective_url"] == "https://eprints2.undip.ac.id/cgi/oai2"
    assert legacy_wiz["record_count_estimate"] == 45000

    tested_undip, wiz = probe_catalog(isolated_db, undip, client=client, resolve_dns=False)
    assert wiz["ok"] is True
    assert tested_undip.oai_status == "VERIFIED"
    assert tested_undip.collections_count == 2
    assert tested_undip.record_count_estimate == 45000
    assert set(tested_undip.supported_formats) == {"didl", "mets", "oai_bibl", "oai_dc", "rdf", "uketd_dc"}

    repo, created_new = promote_catalog_entry_to_personal(isolated_db, tested_undip)
    assert created_new is True
    assert repo.default_download_pdfs is False
    assert repo.harvesting_permission_status == "METADATA_ALLOWED_FULLTEXT_RESTRICTED"

    # Attempt harvest EVEN with download_pdfs=True -> policy enforces metadata-only & NO robot PDF download!
    summary = harvest_oai_repository(
        isolated_db,
        repo,
        max_records=5,
        download_pdfs=True,
        client=client,
        resolve_dns=False,
    )
    assert pdf_download_attempted["called"] is False
    assert summary["records_harvested"] == 1
    assert summary["fulltext_indexed"] == 0
    assert summary["metadata_only"] == 1
    assert isolated_db.query(Document).count() == 0

    hrec = isolated_db.query(OAIHarvestRecord).filter(OAIHarvestRecord.repository_id == repo.id).first()
    assert hrec is not None
    assert hrec.oai_identifier == "oai:eprints2.undip.ac.id:107"
    assert "https://eprints2.undip.ac.id/id/eprint/107/" in (hrec.landing_urls or [])
    assert hrec.status == "PDF_FOUND"

    pol_log = (
        isolated_db.query(OAIHarvestLog)
        .filter(OAIHarvestLog.repository_id == repo.id, OAIHarvestLog.stage == "POLICY_METADATA_ONLY")
        .first()
    )
    assert pol_log is not None


def test_undip_catalog_requires_connection_test_before_save_api(tmp_path, monkeypatch):
    db_path = tmp_path / "api_undip.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NG_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("NG_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("NG_API_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()

    import app.sources.oai_catalog as cat_mod

    # Simulate network failure during forced pre-save verification -> /add MUST reject with 400!
    def fail_test(db, entry, **kw):
        entry.oai_status = "ERROR"
        entry.last_error = "[Kegagalan Koneksi HTTP / Jaringan] Simulasi offline"
        db.commit()
        return entry, {
            "ok": False,
            "failure_category": "HTTP_CONNECTION_FAILURE",
            "failure_category_label": "Kegagalan Koneksi HTTP / Jaringan",
            "failure_message": "Simulasi offline",
        }

    monkeypatch.setattr(cat_mod, "test_catalog_entry", fail_test)
    # Also ensure oai_api uses patched test_catalog_entry
    import app.api.oai as oai_api

    monkeypatch.setattr(oai_api, "test_catalog_entry", fail_test)

    with TestClient(app) as tc:
        res = tc.get("/api/oai/catalog?q=UNDIP")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        undip_item = items[0]
        assert undip_item["oai_status"] == "UNVERIFIED"
        assert undip_item["requires_verification_before_save"] is True
        assert undip_item["default_download_pdfs"] is False

        add_fail = tc.post(f"/api/oai/catalog/{undip_item['id']}/add")
        assert add_fail.status_code == 400
        assert "wajib lolos uji koneksi" in add_fail.json()["detail"].lower()
