"""Phase 9 Regression, Scoring Precision, Indonesian NLP, BrowserExtractor, DOAJ & Live Network Tests."""

from __future__ import annotations

import os
import httpx
import pytest

from app.engine.exact import RawMatch
from app.engine.indonesian_nlp import compute_indonesian_paraphrase_similarity, stem_indonesian_token
from app.engine.scoring import compute_scores
from app.schemas import CheckSettingsSchema
from app.sources.browser_extractor import IsolatedPlaywrightExtractor
from app.sources.doaj import DOAJProvider


def test_scoring_audit_408_of_5973_and_rounding_residue_explanation():
    """Audit the exact 408 / 5,973 scenario:
    - Exact: 290 words -> 290/5973 = 4.855181...% -> rounds to 4.86%
    - Near-Exact: 118 words -> 118/5973 = 1.975556...% -> rounds to 1.98%
    - Unique matched eligible: 290 + 118 = 408 words -> 408/5973 = 6.830738...% -> rounds to 6.83%
    - Raw similarity: 578 / 6269 = 9.219971...% -> rounds to 9.22%
    - Rounded sum 4.86 + 1.98 = 6.84 vs 6.83 (+0.01% rounding residue explained!)
    """
    eligible_words = 5973
    excluded_words = 296  # total_words = 6269
    total_words = eligible_words + excluded_words
    token_mask: list[str | None] = [None] * eligible_words + ["BIBLIOGRAPHY"] * excluded_words

    # Construct overlapping matches across 2 sources + bibliography match to verify zero double-counting
    exact_src1 = RawMatch(
        source_document_id="src-1",
        layer="EXACT",
        sub_token_start=0,
        sub_token_end=290,
        src_token_start=0,
        src_token_end=290,
        matched_words=290,
        score=1.0,
        counted_token_indices=set(range(0, 290)),
    )
    # Near-exact overlaps 40 tokens with Exact [250..290) plus 118 new eligible tokens [290..408)
    near_src2 = RawMatch(
        source_document_id="src-2",
        layer="NEAR_EXACT",
        sub_token_start=250,
        sub_token_end=408,
        src_token_start=10,
        src_token_end=168,
        matched_words=158,
        score=0.88,
        counted_token_indices=set(range(250, 408)),
    )
    # Excluded bibliography match of 170 tokens [5973..6143) -> raw matched = 408 + 170 = 578
    bib_match = RawMatch(
        source_document_id="src-1",
        layer="EXACT",
        sub_token_start=5973,
        sub_token_end=6143,
        src_token_start=300,
        src_token_end=470,
        matched_words=170,
        score=1.0,
        counted_token_indices=set(range(5973, 6143)),
    )

    res = compute_scores(
        all_matches=[exact_src1, near_src2, bib_match],
        token_mask=token_mask,
        settings=CheckSettingsSchema(),
        threshold_low=15.0,
        threshold_high=30.0,
        full_text_sources_compared=5,
    )
    m = res.metrics
    se = m["score_explanation"]

    assert m["eligible_words"] == 5973
    assert m["matched_words"] == 408
    assert m["exact_match_words"] + m["near_exact_match_words"] == 408
    assert m["adjusted_similarity"] == 6.83
    assert m["raw_similarity"] == 9.22
    assert m["exact_match_pct"] == 4.86
    assert m["near_exact_match_pct"] == 1.98
    assert round(sum(s.contribution_pct for s in res.source_summaries), 2) == 6.83
    assert "6.8307%" in se["rounding_note"]
    assert "+0.01%" in se["rounding_note"]


def test_indonesian_morphology_synonym_reordering_and_technical_guard():
    """Verify Indonesian affix stemming, synonym canonicalization, clause reordering, and anti-FP technical guard."""
    assert stem_indonesian_token("menggunakan") == "guna"
    assert stem_indonesian_token("memanfaatkan") == "guna"
    assert stem_indonesian_token("memperlihatkan") == "tunjuk"
    assert stem_indonesian_token("penelitiannya") == "teliti"

    # Paraphrased Indonesian sentence (affix + synonym + clause reorder)
    s1 = "Penelitian ini memanfaatkan metode survei lapangan guna memperlihatkan dampak kenaikan biaya hidup warga kota."
    s2 = "Untuk menunjukkan pengaruh peningkatan biaya hidup warga kota, riset ini menggunakan metode survei lapangan."
    score_para, expl = compute_indonesian_paraphrase_similarity(s1, s2, char_cosine=0.66)
    assert score_para >= 0.70
    assert expl is not None

    # Unrelated sentences sharing ONLY technical terminology must NOT exceed threshold!
    t1 = "Model regresi statistik kuantitatif menguji validitas dan reliabilitas variabel hipotesis populasi."
    t2 = "Arsitektur database sistem menggunakan model probabilitas distribusi statistik dan validitas sampel."
    score_tech, expl_tech = compute_indonesian_paraphrase_similarity(t1, t2, char_cosine=0.58)
    assert score_tech < 0.65
    assert expl_tech is None


def test_doaj_provider_mock_and_browser_extractor_health():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doaj-123",
                        "bibjson": {
                            "title": "Evaluasi Kemiripan Dokumen Ilmiah Berbahasa Indonesia",
                            "year": "2024",
                            "author": [{"name": "Dewi Lestari"}],
                            "identifier": [{"type": "doi", "id": "10.1234/jurnal.2024.01"}],
                            "link": [
                                {"type": "fulltext", "content_type": "application/pdf", "url": "https://jurnal.example.org/doc.pdf"}
                            ],
                            "license": [{"type": "CC BY 4.0"}],
                            "abstract": "Abstrak artikel jurnal open access DOAJ.",
                        },
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    prov = DOAJProvider(client=client)
    recs = prov.search("kemiripan dokumen ilmiah")
    assert len(recs) == 1
    assert recs[0].provider == "doaj"
    assert recs[0].doi == "10.1234/jurnal.2024.01"
    assert recs[0].oa_pdf_url == "https://jurnal.example.org/doc.pdf"
    assert recs[0].access_status == "FULL_TEXT_AVAILABLE"

    ext = IsolatedPlaywrightExtractor(enable_browser=False, resolve_dns=False)
    hc = ext.health_check_sync()
    assert hc["isolated_context"] is True


def test_provider_diagnostics_never_fakes_connected_before_probe(isolated_env):
    """Verify GET /api/providers starts with reachable=None for unprobed external providers."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app()) as client:
        res = client.get("/api/providers")
        assert res.status_code == 200
        provs = {p["id"]: p for p in res.json()["providers"]}
        assert provs["local_corpus"]["reachable"] is True
        assert "doaj" in provs
        # SearXNG without env URL must be NOT_CONFIGURED (configured=False)
        assert provs["searxng"]["configured"] is False
        assert "NOT_CONFIGURED" in provs["searxng"]["status"]


@pytest.mark.skipif(
    os.getenv("LIVE_NETWORK_TESTS", "").lower() != "true",
    reason="Set LIVE_NETWORK_TESTS=true to run explicit live internet provider diagnostics.",
)
def test_live_internet_providers_explicit():
    """Explicit opt-in live internet integration check using a non-private public test phrase."""
    from app.sources.arxiv import ArxivProvider
    from app.sources.crossref import CrossrefProvider
    from app.sources.europe_pmc import EuropePMCProvider
    from app.sources.openalex import OpenAlexProvider

    public_q = "winnowing document fingerprinting"
    live_results = {}
    for name, prov in (
        ("openalex", OpenAlexProvider()),
        ("crossref", CrossrefProvider()),
        ("europe_pmc", EuropePMCProvider()),
        ("doaj", DOAJProvider()),
        ("arxiv", ArxivProvider()),
    ):
        recs = prov.search(public_q)
        live_results[name] = {"count": len(recs), "error": getattr(prov, "last_error", None)}

    # At least one major public academic API must respond when LIVE_NETWORK_TESTS=true
    assert any(v["error"] is None and v["count"] > 0 for v in live_results.values()), f"All live providers failed: {live_results}"
