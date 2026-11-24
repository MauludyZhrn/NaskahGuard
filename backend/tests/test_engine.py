"""Unit & integration tests for Winnowing, Exact, Near-Exact, Overlap Attribution, and Exclusions."""

from __future__ import annotations

from app.db import get_session_factory
from app.engine.exact import find_exact_matches
from app.engine.near_exact import find_near_exact_matches
from app.engine.pipeline import run_check_pipeline
from app.engine.winnowing import winnow_tokens
from app.ingestion.service import ingest_validated_upload
from app.ingestion.validators import validate_local_bytes
from app.models import Check, CheckSource


def test_winnowing_is_deterministic():
    tokens = "sistem deteksi kemiripan dokumen akademik menggunakan algoritma winnowing pada korpus lokal".split()
    fp1 = winnow_tokens(tokens)
    fp2 = winnow_tokens(tokens)
    assert fp1 == fp2
    assert len(fp1) > 0


def test_exact_and_near_exact_matching_algorithms():
    src = (
        "sistem pendeteksian kemiripan dokumen akademik ini dirancang untuk membantu dosen "
        "dan peneliti memeriksa keaslian karya tulis ilmiah secara transparan dan terukur"
    ).split()
    sub_exact = list(src)
    em = find_exact_matches(sub_exact, src, "src1", min_match_words=8)
    assert len(em) == 1
    assert em[0].matched_words == len(src)

    # Near-exact: substitute 2 words in the middle
    sub_near = list(src)
    sub_near[5] = "naskah"
    sub_near[12] = "mengaudit"
    em2 = find_exact_matches(sub_near, src, "src1", min_match_words=8)
    nm2 = find_near_exact_matches(sub_near, src, "src1", em2, min_match_words=8)
    assert len(em2) + len(nm2) >= 1
    covered = set()
    for m in em2 + nm2:
        covered.update(m.counted_token_indices)
    # 5 and 12 were replaced, so they should not be in counted equal blocks
    assert 5 not in covered
    assert 12 not in covered
    assert len(covered) >= 15


def _run_sync_check(db, doc_id: str, settings_dict: dict | None = None) -> Check:
    chk = Check(
        report_number=f"NG-TEST-{doc_id[:8]}",
        document_id=doc_id,
        status="QUEUED",
        stage="Antrean",
        progress=0,
        settings=settings_dict or {},
        stage_counts={},
        metrics={},
        coverage={},
    )
    db.add(chk)
    db.commit()
    run_check_pipeline(db, chk.id)
    db.refresh(chk)
    return chk


def test_pipeline_identical_partial_overlap_exclusions_and_empty_corpus(isolated_env):
    db = get_session_factory()()
    try:
        # 1. Empty corpus -> coverage limited + SI 0
        sub_only = validate_local_bytes(
            "sub_only.txt",
            "Dokumen uji pertama tanpa sumber pembanding sama sekali di dalam korpus.".encode("utf-8"),
            10_000_000,
        )
        d_sub0 = ingest_validated_upload(db, sub_only, role="SUBMISSION")
        chk0 = _run_sync_check(db, d_sub0.id)
        assert chk0.status == "COMPLETED"
        assert chk0.metrics["similarity_index"] == 0.0
        assert chk0.coverage["full_text_sources_compared"] == 0

        # 2. Add two overlapping corpus sources
        shared_sentence = "Teknologi pemrosesan bahasa alami memungkinkan komputer memahami struktur sintaksis dan semantik teks akademik secara mendalam."
        extra_a = "Metode evaluasi korpus lokal menjamin bahwa seluruh proses tetap bersifat privat dan dapat diaudit."
        extra_b = "Analisis bibliometrik mendukung pemetaan sitasi antar publikasi ilmiah terbuka di berbagai disiplin ilmu."

        c1 = validate_local_bytes("src_a.txt", f"{shared_sentence}\n\n{extra_a}".encode("utf-8"), 10_000_000)
        c2 = validate_local_bytes("src_b.txt", f"{shared_sentence}\n\n{extra_b}".encode("utf-8"), 10_000_000)
        ingest_validated_upload(db, c1, role="CORPUS", title="Sumber A")
        ingest_validated_upload(db, c2, role="CORPUS", title="Sumber B")

        # Identical to src_a -> SI 100%
        sub_ident = validate_local_bytes("ident.txt", f"{shared_sentence}\n\n{extra_a}".encode("utf-8"), 10_000_000)
        d_ident = ingest_validated_upload(db, sub_ident, role="SUBMISSION")
        chk_ident = _run_sync_check(db, d_ident.id)
        assert chk_ident.metrics["similarity_index"] == 100.0

        # Overlapping submission copying shared_sentence + unique text + bibliography + quote
        quoted = '"Teknologi pemrosesan bahasa alami memungkinkan komputer memahami struktur sintaksis."'
        sub_mix_txt = (
            f"{shared_sentence}\n\n"
            f"Kalimat orisinal penulis yang belum pernah muncul pada dokumen pembanding mana pun sebelumnya.\n\n"
            f"Kutipan berikut: {quoted} (Smith, 2023).\n\n"
            f"Daftar Pustaka\n\n{extra_b}"
        )
        sub_mix = validate_local_bytes("mix.txt", sub_mix_txt.encode("utf-8"), 10_000_000)
        d_mix = ingest_validated_upload(db, sub_mix, role="SUBMISSION")

        # With bibliography & quotes excluded
        chk_excl = _run_sync_check(
            db,
            d_mix.id,
            {
                "exclude_bibliography": True,
                "exclude_quotes": True,
                "exclude_citations": True,
                "exclude_common_phrases": True,
                "min_match_words": 8,
            },
        )
        # Invariant: sum of exclusive source contributions equals Adjusted SI
        srcs = db.query(CheckSource).filter(CheckSource.check_id == chk_excl.id).all()
        contrib_sum = round(sum(s.contribution_pct for s in srcs), 2)
        assert abs(contrib_sum - chk_excl.metrics["similarity_index"]) <= 0.05
        # Raw SI > Adjusted SI because bibliography & quote were excluded from Adjusted SI
        assert chk_excl.metrics["raw_similarity"] > chk_excl.metrics["adjusted_similarity"]
    finally:
        db.close()
