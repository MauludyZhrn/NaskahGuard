"""Regression tests for UNDIP HTTP 404 root-cause fix & 5-category UI failure diagnostics."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.sources.oai_pmh import classify_ui_failure_kind, run_connection_wizard

IDENTIFY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <responseDate>2026-11-26T00:00:00Z</responseDate>
  <request verb="Identify">https://mock.campus.ac.id/cgi/oai2</request>
  <Identify>
    <repositoryName>Mock Kampus Repository</repositoryName>
    <baseURL>https://mock.campus.ac.id/cgi/oai2</baseURL>
    <protocolVersion>2.0</protocolVersion>
  </Identify>
</OAI-PMH>"""

FORMATS_ONLY_DC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListMetadataFormats>
    <metadataFormat>
      <metadataPrefix>oai_dc</metadataPrefix>
    </metadataFormat>
  </ListMetadataFormats>
</OAI-PMH>"""

NO_RECORDS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <error code="noRecordsMatch">The combination of the values results in an empty set.</error>
</OAI-PMH>"""


def test_oai_routes_registered_without_404(isolated_env) -> None:
    """Ensure /api/oai/auto-detect, /api/oai/test-connection, /api/oai/catalog and /api/oai/repositories exist (never 404)."""
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        paths = openapi.json()["paths"]
        for required_path in (
            "/api/oai/auto-detect",
            "/api/oai/test-connection",
            "/api/oai/repositories",
            "/api/oai/catalog",
        ):
            assert required_path in paths


def test_manual_modal_add_undip_enforces_metadata_only_policy(isolated_env) -> None:
    """Manual modal submission of UNDIP must automatically enforce metadata-only policy defaults."""
    with TestClient(create_app()) as client:
        res = client.post(
            "/api/oai/repositories",
            json={
                "name": "Undip Repository (Manual)",
                "base_url": "https://eprints2.undip.ac.id/cgi/oai2",
                "repo_type": "eprints",
                "metadata_prefix": "oai_dc",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["legacy_url"] == "http://eprints.undip.ac.id/cgi/oai2"
        assert body["policy_url"] == "https://eprints2.undip.ac.id/policies.html"
        assert body["fulltext_policy"] == "METADATA_ONLY_DEFAULT"
        assert body["harvesting_permission_status"] == "METADATA_ALLOWED_FULLTEXT_RESTRICTED"
        assert body["default_download_pdfs"] is False
        assert body["request_timeout_sec"] == 45


def test_wizard_distinguishes_5_ui_failure_kinds() -> None:
    """Verify wizard metadata clearly separates OAI 404, empty records, unavailable format & policy restriction."""
    assert classify_ui_failure_kind("HTTP_404") == ("OAI_ENDPOINT_NOT_FOUND", "Endpoint OAI-PMH tidak ditemukan")
    assert classify_ui_failure_kind("noRecordsMatch") == ("EMPTY_RECORDS", "Repository tidak memiliki record")
    assert classify_ui_failure_kind("cannotDisseminateFormat") == (
        "UNAVAILABLE_METADATA_FORMAT",
        "Metadata format tidak tersedia",
    )
    assert classify_ui_failure_kind("POLICY_RESTRICTED") == (
        "FULLTEXT_POLICY_RESTRICTED",
        "Full-text dibatasi kebijakan",
    )

    def handler_404(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="404 Not Found")

    with httpx.Client(transport=httpx.MockTransport(handler_404)) as mc:
        rep_404 = run_connection_wizard(
            "https://mock.campus.ac.id/cgi/oai2",
            client=mc,
            resolve_dns=False,
        )
    assert rep_404["ok"] is False
    assert rep_404["failure_kind"] == "OAI_ENDPOINT_NOT_FOUND"
    assert rep_404["failure_kind_label"] == "Endpoint OAI-PMH tidak ditemukan"
    assert rep_404["failure_http_status"] == 404

    def handler_empty(request: httpx.Request) -> httpx.Response:
        verb = request.url.params.get("verb")
        if verb == "Identify":
            return httpx.Response(200, text=IDENTIFY_XML, headers={"content-type": "application/xml"})
        if verb == "ListMetadataFormats":
            return httpx.Response(200, text=FORMATS_ONLY_DC_XML, headers={"content-type": "application/xml"})
        if verb == "ListSets":
            return httpx.Response(200, text=NO_RECORDS_XML.replace("noRecordsMatch", "noSetHierarchy"), headers={"content-type": "application/xml"})
        return httpx.Response(200, text=NO_RECORDS_XML, headers={"content-type": "application/xml"})

    with httpx.Client(transport=httpx.MockTransport(handler_empty)) as mc:
        rep_empty = run_connection_wizard(
            "https://mock.campus.ac.id/cgi/oai2",
            metadata_prefix="uketd_dc",
            client=mc,
            resolve_dns=False,
        )
    assert rep_empty["overall_status"] == "PARTIAL"
    st4 = next(s for s in rep_empty["stages"] if s["step"] == 4)
    st6 = next(s for s in rep_empty["stages"] if s["step"] == 6)
    assert st4["failure_kind"] == "UNAVAILABLE_METADATA_FORMAT"
    assert st6["failure_kind"] == "EMPTY_RECORDS"
