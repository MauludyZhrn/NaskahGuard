"""Tests for external source discovery adapters (mocked, no network) and loopback checks."""

from __future__ import annotations

import json
import httpx
import pytest

from app.engine.noplag_adapter import NoplagAdapter
from app.sources.arxiv import ArxivProvider
from app.sources.crossref import CrossrefProvider
from app.sources.openalex import OpenAlexProvider
from app.sources.pmc import PubMedCentralProvider


def test_openalex_and_crossref_mock_transport():
    def oa_handler(request: httpx.Request) -> httpx.Response:
        if "api.openalex.org/works" in str(request.url):
            payload = {
                "results": [
                    {
                        "id": "https://openalex.org/W123",
                        "display_name": "Open Plagiarism Benchmarks",
                        "publication_year": 2024,
                        "doi": "https://doi.org/10.1234/abc",
                        "authorships": [{"author": {"display_name": "Budi Santoso"}}],
                        "best_oa_location": {
                            "pdf_url": "https://example.org/paper.pdf",
                            "landing_page_url": "https://example.org/paper",
                        },
                    }
                ]
            }
            return httpx.Response(200, json=payload)
        if "robots.txt" in str(request.url):
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/")
        if "paper.pdf" in str(request.url):
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(404)

    oa_client = httpx.Client(transport=httpx.MockTransport(oa_handler))
    oa = OpenAlexProvider(client=oa_client)
    recs = oa.search("plagiarism benchmark")
    assert len(recs) == 1
    assert recs[0].doi == "10.1234/abc"
    assert recs[0].access_status == "FULL_TEXT_AVAILABLE"
    assert oa.fetch_content(recs[0].oa_pdf_url) is None
    assert oa.last_error == "ACCESS_DENIED"

    def cr_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.5555/test",
                            "title": ["Academic Integrity Survey"],
                            "author": [{"given": "Ani", "family": "Wijaya"}],
                            "issued": {"date-parts": [[2025]]},
                            "URL": "https://doi.org/10.5555/test",
                        }
                    ]
                }
            },
        )

    cr = CrossrefProvider(client=httpx.Client(transport=httpx.MockTransport(cr_handler)))
    cr_recs = cr.search("Academic Integrity")
    assert len(cr_recs) == 1
    assert cr_recs[0].access_status == "METADATA_ONLY"
    assert cr.fetch_content(cr_recs[0].external_id) is None


def test_arxiv_and_pmc_mock_transport():
    atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2501.00001v1</id>
        <published>2025-01-05T00:00:00Z</published>
        <title>Indonesian Plagiarism Detection</title>
        <author><name>Rina Putri</name></author>
        <link title="pdf" href="https://arxiv.org/pdf/2501.00001v1.pdf" type="application/pdf"/>
      </entry>
    </feed>"""
    ax = ArxivProvider(
        client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=atom_xml))),
        min_interval_sec=0.0,
    )
    ax_recs = ax.search("Indonesian Plagiarism")
    assert len(ax_recs) == 1
    assert ax_recs[0].external_id == "2501.00001v1"

    def pmc_handler(req: httpx.Request) -> httpx.Response:
        if "esearch" in str(req.url):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["99999"]}})
        return httpx.Response(
            200,
            json={
                "result": {
                    "99999": {
                        "title": "PMC Sample Study",
                        "pubdate": "2024 May",
                        "authors": [{"name": "Doe J"}],
                        "articleids": [{"idtype": "doi", "value": "10.1000/pmc"}],
                    }
                }
            },
        )

    pmc = PubMedCentralProvider(client=httpx.Client(transport=httpx.MockTransport(pmc_handler)))
    pmc_recs = pmc.search("sample study")
    assert len(pmc_recs) == 1
    assert pmc_recs[0].access_status == "METADATA_ONLY"


def test_noplag_adapter_rejects_non_loopback_host():
    with pytest.raises(ValueError):
        NoplagAdapter("http://192.168.1.50:8001")
    adapter = NoplagAdapter("http://127.0.0.1:9999")
    assert adapter.is_configured is True
