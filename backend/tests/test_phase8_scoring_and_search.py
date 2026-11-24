"""Phase 8 tests: Scoring transparency (57/6227, overlap, exclusions), multi-query profiles, ranking, TTL cache, provider health."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine.exact import RawMatch
from app.engine.scoring import compute_scores
from app.main import create_app
from app.models import Segment
from app.schemas import CheckSettingsSchema
from app.sources.base import SourceRecord
from app.sources.cache import TTLCache
from app.sources.query_generator import generate_intelligent_queries
from app.sources.ranking import score_candidate_relevance


def test_scoring_57_of_6227_and_exact_near_overlap_no_double_count():
    # 6,227 eligible tokens + 300 bibliography tokens = 6,527 total tokens
    token_mask: list[str | None] = [None] * 6227 + ["BIBLIOGRAPHY"] * 300

    # Exact match covers tokens 0..40 (40 words) on src_a
    m_exact_a = RawMatch(
        source_document_id="src_a",
        layer="EXACT",
        sub_token_start=0,
        sub_token_end=40,
        src_token_start=0,
        src_token_end=40,
        matched_words=40,
        score=1.0,
        counted_token_indices=set(range(0, 40)),
    )
    # Near-exact overlaps tokens 30..40 (already claimed by exact!) + adds 40..57 (17 new words) on src_b
    m_near_b = RawMatch(
        source_document_id="src_b",
        layer="NEAR_EXACT",
        sub_token_start=30,
        sub_token_end=57,
        src_token_start=10,
        src_token_end=37,
        matched_words=27,
        score=0.9,
        counted_token_indices=set(range(30, 57)),
    )
    # Excluded bibliography match (100 words inside bibliography zone)
    m_bib = RawMatch(
        source_document_id="src_c",
        layer="EXACT",
        sub_token_start=6250,
        sub_token_end=6350,
        src_token_start=0,
        src_token_end=100,
        matched_words=100,
        score=1.0,
        counted_token_indices=set(range(6250, 6350)),
    )

    cfg = CheckSettingsSchema(exclude_bibliography=True)
    res = compute_scores(
        all_matches=[m_exact_a, m_near_b, m_bib],
        token_mask=token_mask,
        settings=cfg,
        threshold_low=15.0,
        threshold_high=30.0,
        full_text_sources_compared=3,
    )

    # Unique matched eligible words MUST be 57 (40 exact + 17 near-exact; 10 overlap tokens NOT double-counted)
    assert res.metrics["eligible_words"] == 6227
    assert res.metrics["matched_words"] == 57
    expected_si = round((57 / 6227) * 100.0, 2)  # 0.92%
    assert res.metrics["similarity_index"] == expected_si
    assert res.metrics["raw_matched_words"] == 157  # 57 + 100 bib
    assert res.metrics["raw_similarity"] > res.metrics["adjusted_similarity"]

    # Exclusive attribution sum equals Adjusted SI
    contrib_sum = round(sum(s.contribution_pct for s in res.source_summaries), 2)
    assert abs(contrib_sum - expected_si) <= 0.02

    # Score explanation carries transparent breakdown
    expl = res.metrics["score_explanation"]
    assert expl["unique_matched_words"] == 57
    assert expl["eligible_words"] == 6227
    assert expl["exact_match_words"] == 40
    assert expl["near_exact_match_words"] == 17
    assert expl["excluded_words"] == 300
    assert "BIBLIOGRAPHY" in expl["raw_vs_adjusted_reason"]


def test_multi_query_profiles_and_per_chapter_distribution():
    segs = []
    chapters = ["BAB I Pendahuluan", "BAB II Tinjauan Pustaka", "BAB III Metode Penelitian", "BAB IV Hasil"]
    idx = 0
    for c_idx, chap in enumerate(chapters, start=1):
        for p in range(1, 4):
            idx += 1
            txt = (
                f"Metode algoritma unik bab{c_idx} paragraf{p} mengevaluasi arsitektur pencarian korpus "
                f"akademik menggunakan sidik jari winnowing dan pencocokan semantik terukur."
            )
            segs.append(
                Segment(
                    id=idx,
                    document_id="doc1",
                    page_number=c_idx,
                    paragraph_number=p,
                    sentence_number=idx,
                    char_start=0,
                    char_end=len(txt),
                    token_start=0,
                    token_end=15,
                    original_text=txt,
                    normalized_text=txt.lower(),
                    section_label=chap,
                    zone="BODY",
                )
            )

    q_quick = generate_intelligent_queries(title="Skripsi Uji", segments=segs, profile="QUICK", max_queries=8)
    q_bal = generate_intelligent_queries(title="Skripsi Uji", segments=segs, profile="BALANCED", max_queries=24)
    q_deep = generate_intelligent_queries(title="Skripsi Uji", segments=segs, profile="DEEP", max_queries=48)

    assert len(q_quick) <= 8
    assert len(q_bal) > len(q_quick)
    assert len(q_bal) <= 24
    assert len(q_deep) <= 48

    # Substantive chapters represented in BALANCED profile
    bal_chapters = {q.chapter for q in q_bal}
    for chap in chapters:
        assert chap in bal_chapters


def test_search_quality_ranking_and_ttl_cache():
    doc_kw = {"winnowing", "fingerprinting", "plagiarism", "academic", "similarity", "alignment"}
    r_high = SourceRecord(
        provider="openalex",
        external_id="W1",
        title="Winnowing Fingerprinting for Academic Plagiarism Similarity Alignment",
        abstract="We evaluate winnowing fingerprinting and alignment for academic plagiarism detection.",
        doi="10.1000/high",
        oa_pdf_url="https://oa.example.org/1.pdf",
        canonical_url="https://oa.example.org/1",
        access_status="FULL_TEXT_AVAILABLE",
    )
    r_low = SourceRecord(
        provider="searxng",
        external_id="W2",
        title="Resep Masakan Nusantara Sederhana",
        abstract="Panduan memasak soto dan rendang di rumah.",
    )

    scored_high = score_candidate_relevance(
        r_high,
        doc_title="Academic Plagiarism Similarity Alignment",
        doc_keywords=doc_kw,
        matched_query="winnowing fingerprinting academic plagiarism",
    )
    scored_low = score_candidate_relevance(
        r_low,
        doc_title="Academic Plagiarism Similarity Alignment",
        doc_keywords=doc_kw,
        matched_query="winnowing fingerprinting academic plagiarism",
    )
    assert scored_high.relevance_label == "HIGHLY_RELEVANT"
    assert scored_low.relevance_label == "UNRELATED"
    assert scored_high.relevance_score > scored_low.relevance_score

    cache: TTLCache[str] = TTLCache(ttl_seconds=10.0, max_entries=2)
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"
    cache.invalidate("k1")
    assert cache.get("k1") is None


def test_provider_health_telemetry_api(isolated_env):
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/api/providers")
        assert res.status_code == 200
        providers = res.json()["providers"]
        by_id = {p["id"]: p for p in providers}
        assert "openalex" in by_id
        assert "configured" in by_id["openalex"]
        assert "health" in by_id["openalex"]
        assert "request_count" in by_id["openalex"]
        assert by_id["searxng"]["health"] == "unconfigured"
