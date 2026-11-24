"""Phase 9 Realistic Academic Similarity Detection Benchmark (12 Ground-Truth Scenarios).

Evaluates NaskahGuard's multi-layer detection & attribution engine across:
1. Exact copies
2. Near-exact edited text
3. Paraphrased Indonesian passages (affix + synonym changes)
4. Reordered paragraphs & clauses
5. Citation overlap (excluded when exclude_citations=True)
6. Bibliography overlap (excluded when exclude_bibliography=True)
7. Indonesian academic text
8. English academic text
9. Cross-source duplication (exclusive attribution — zero double-counting)
10. Unrelated text sharing technical jargon (true negative guard)
11. Metadata-only source (never treated as full-text compared)
12. Restricted / no-access source (ACCESS_DENIED — zero false match)

Outputs Precision, Recall, F1-score, FPR, FNR, Retrieval P@5, Retrieval R@5,
Full-Text Acquisition Success Rate, and Processing Latency to
`benchmark/results/phase9_detection_benchmark.json`.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.exact import RawMatch, find_exact_matches
from app.engine.exclusions import build_exclusion_mask
from app.engine.lexical import find_lexical_matches
from app.engine.near_exact import find_near_exact_matches
from app.engine.scoring import compute_scores
from app.ingestion.pdf import PageSpan
from app.ingestion.segment import segment_document
from app.ingestion.structure import annotate_structure
from app.ingestion.tokenize import tokenize_with_offsets
from app.models import Segment
from app.schemas import CheckSettingsSchema
from app.sources.base import SourceRecord
from app.sources.ranking import score_candidate_relevance


def _prep(doc_id: str, text: str):
    toks = tokenize_with_offsets(text)
    pages = [PageSpan(number=1, char_start=0, char_end=len(text))]
    raw_segs = segment_document(text, pages, toks)
    annotate_structure(text, pages, raw_segs)
    segs = [
        Segment(
            document_id=doc_id,
            page_number=s.page_number,
            paragraph_number=s.paragraph_number,
            sentence_number=s.sentence_number,
            section_label=s.section_label,
            zone=s.zone,
            char_start=s.char_start,
            char_end=s.char_end,
            token_start=s.token_start,
            token_end=s.token_end,
            original_text=s.original_text,
            normalized_text=s.normalized_text,
        )
        for s in raw_segs
    ]
    return toks, segs


@dataclass
class Scenario:
    name: str
    submission_text: str
    sources: list[tuple[str, str, str]]  # (src_id, access_status, text)
    expected_positive: bool
    include_lexical: bool = False


def build_scenarios() -> list[Scenario]:
    src_id_a = (
        "Pengembangan sistem deteksi kemiripan dokumen akademik berbasis indeks sidik jari Winnowing "
        "memungkinkan pemeriksaan skripsi mahasiswa secara cepat akurat dan transparan di lingkungan kampus."
    )
    src_en_b = (
        "Deterministic winnowing fingerprinting combined with token-level seed extension enables verifiable "
        "academic manuscript similarity auditing without exposing private student submissions to external servers."
    )
    return [
        Scenario(
            "1_exact_copy",
            f"BAB I PENDAHULUAN\n\n{src_id_a}\n\nBagian penutup paragraf asli penulis sendiri yang berbeda topik.",
            [("src-a", "FULLTEXT", src_id_a)],
            expected_positive=True,
        ),
        Scenario(
            "2_near_exact",
            "BAB II TINJAUAN PUSTAKA\n\nPengembangan aplikasi pendeteksi kemiripan dokumen akademik berbasis metode sidik jari Winnowing "
            "memungkinkan pengujian skripsi mahasiswa secara cepat, tepat, dan transparan di lingkungan universitas.",
            [("src-a", "FULLTEXT", src_id_a)],
            expected_positive=True,
        ),
        Scenario(
            "3_indonesian_paraphrase",
            "BAB III METODOLOGI\n\nPenelitian ini memanfaatkan metode survei lapangan guna memperlihatkan dampak kenaikan biaya logistik antarpulau.",
            [("src-p", "FULLTEXT", "Untuk menunjukkan pengaruh peningkatan biaya logistik antarpulau, riset ini menggunakan metode survei lapangan.")],
            expected_positive=True,
            include_lexical=True,
        ),
        Scenario(
            "4_reordered_paragraphs",
            f"BAB IV PEMBAHASAN\n\n{src_en_b}\n\n{src_id_a}",
            [("src-mix", "FULLTEXT", f"{src_id_a}\n\n{src_en_b}")],
            expected_positive=True,
        ),
        Scenario(
            "5_citation_overlap_excluded",
            'BAB II KAJIAN TEORI\n\nMenurut Santoso (2023), "Pengembangan sistem deteksi kemiripan dokumen akademik berbasis indeks sidik jari Winnowing memungkinkan pemeriksaan skripsi mahasiswa secara cepat akurat dan transparan di lingkungan kampus."',
            [("src-a", "FULLTEXT", src_id_a)],
            expected_positive=False,  # Direct quote excluded when exclude_quotes=True!
        ),
        Scenario(
            "6_bibliography_overlap_excluded",
            "BAB I ISI\n\nAnalisis mandiri penulis mengenai tata kelola perpustakaan digital modern di daerah terpencil.\n\n"
            "DAFTAR PUSTAKA\n\nSchleimer, S., Wilkerson, D. S., & Aiken, A. (2003). Winnowing local algorithms for document fingerprinting in proceedings of SIGMOD international conference.",
            [("src-bib", "FULLTEXT", "Schleimer, S., Wilkerson, D. S., & Aiken, A. (2003). Winnowing local algorithms for document fingerprinting in proceedings of SIGMOD international conference.")],
            expected_positive=False,
        ),
        Scenario(
            "7_indonesian_academic_text",
            f"BAB I PENDAHULUAN\n\n{src_id_a}",
            [("src-a", "FULLTEXT", src_id_a)],
            expected_positive=True,
        ),
        Scenario(
            "8_english_academic_text",
            f"CHAPTER 1 INTRODUCTION\n\n{src_en_b}",
            [("src-en", "FULLTEXT", src_en_b)],
            expected_positive=True,
        ),
        Scenario(
            "9_cross_source_duplication",
            f"BAB III HASIL\n\n{src_id_a}",
            [("src-dup-1", "FULLTEXT", src_id_a), ("src-dup-2", "FULLTEXT", src_id_a)],
            expected_positive=True,
        ),
        Scenario(
            "10_unrelated_technical_jargon",
            "BAB III METODE\n\nModel regresi statistik kuantitatif menguji validitas dan reliabilitas variabel hipotesis populasi petani padi.",
            [("src-irr", "FULLTEXT", "Arsitektur database sistem menggunakan model probabilitas distribusi statistik dan validitas sampel jaringan sensor.")],
            expected_positive=False,
            include_lexical=True,
        ),
        Scenario(
            "11_metadata_only_source",
            f"BAB I PENDAHULUAN\n\n{src_id_a}",
            [("src-meta", "METADATA_ONLY", "")],
            expected_positive=False,  # Metadata-only has no fulltext -> must NOT fabricate a match!
        ),
        Scenario(
            "12_no_access_fulltext",
            f"BAB I PENDAHULUAN\n\n{src_id_a}",
            [("src-denied", "ACCESS_DENIED", "")],
            expected_positive=False,  # Restricted source -> must NOT fabricate a match!
        ),
    ]


def main() -> None:
    t0 = time.perf_counter()
    scenarios = build_scenarios()

    tp = fp = tn = fn = 0
    ft_candidates = 0
    ft_acquired = 0
    cross_source_no_double_count = True
    details = []

    for sc in scenarios:
        sub_toks, sub_segs = _prep("sub", sc.submission_text)
        sub_norms = [t.norm for t in sub_toks]
        cfg = CheckSettingsSchema(
            min_match_words=6,
            exclude_bibliography=True,
            exclude_quotes=True,
            exclude_citations=True,
            include_lexical_in_index=sc.include_lexical,
        )
        tok_triples = [[t.norm, t.char_start, t.char_end] for t in sub_toks]
        mask = build_exclusion_mask(sc.submission_text, tok_triples, sub_segs, cfg)

        all_matches: list[RawMatch] = []
        ft_compared = 0
        meta_cnt = 0
        denied_cnt = 0

        for sid, status, stext in sc.sources:
            if status in {"FULLTEXT", "ACCESS_DENIED"}:
                ft_candidates += 1
            if status == "METADATA_ONLY":
                meta_cnt += 1
                continue
            if status == "ACCESS_DENIED":
                denied_cnt += 1
                continue

            ft_acquired += 1
            ft_compared += 1
            src_toks, src_segs = _prep(sid, stext)
            src_norms = [t.norm for t in src_toks]
            ex = find_exact_matches(sub_norms, src_norms, sid, min_match_words=6)
            nr = find_near_exact_matches(sub_norms, src_norms, sid, ex, min_match_words=6)
            covered = set()
            for m in ex + nr:
                covered.update(m.counted_token_indices)
            lx = find_lexical_matches(sub_segs, src_segs, covered, min_words=6)
            all_matches.extend(ex + nr + lx)

        scoring = compute_scores(
            all_matches=all_matches,
            token_mask=mask,
            settings=cfg,
            threshold_low=15.0,
            threshold_high=30.0,
            full_text_sources_compared=ft_compared,
            metadata_only_sources=meta_cnt,
            access_denied_sources=denied_cnt,
        )
        si = scoring.metrics["similarity_index"]
        detected = si > 0.0

        if sc.name == "9_cross_source_duplication":
            # Verify matched_words never exceeds total eligible words (zero double-counting across src-dup-1 & src-dup-2)
            if scoring.metrics["matched_words"] > scoring.metrics["eligible_words"] or round(sum(s.contribution_pct for s in scoring.source_summaries), 2) != si:
                cross_source_no_double_count = False

        if sc.expected_positive and detected:
            tp += 1
        elif sc.expected_positive and not detected:
            fn += 1
        elif (not sc.expected_positive) and detected:
            fp += 1
        else:
            tn += 1

        details.append(
            {
                "scenario": sc.name,
                "expected_positive": sc.expected_positive,
                "detected_positive": detected,
                "similarity_index_pct": si,
                "matched_words": scoring.metrics["matched_words"],
                "eligible_words": scoring.metrics["eligible_words"],
                "fulltext_compared": ft_compared,
            }
        )

    precision = round(tp / max(1, tp + fp), 4)
    recall = round(tp / max(1, tp + fn), 4)
    f1 = round((2 * precision * recall) / max(1e-9, precision + recall), 4)
    fpr = round(fp / max(1, fp + tn), 4)
    fnr = round(fn / max(1, fn + tp), 4)

    # Retrieval P@5 & R@5 check
    rel_pool = [
        SourceRecord("openalex", "r1", "Deteksi Kemiripan Dokumen Akademik Sidik Jari Winnowing", abstract="Pemeriksaan skripsi mahasiswa cepat dan transparan.", oa_pdf_url="https://x.org/1.pdf"),
        SourceRecord("doaj", "r2", "Winnowing Fingerprinting for University Thesis Integrity", abstract="Token seed extension academic manuscript similarity.", oa_pdf_url="https://x.org/2.pdf"),
        SourceRecord("europe_pmc", "r3", "Evaluasi Kemiripan Leksikal dan Morfologi Bahasa Indonesia", abstract="Imbuhan dan sinonim pada deteksi kemiripan teks.", oa_pdf_url="https://x.org/3.pdf"),
        SourceRecord("arxiv", "r4", "Citation and Bibliography Exclusion in Plagiarism Reports", abstract="Transparent adjusted vs raw similarity index.", oa_pdf_url="https://x.org/4.pdf"),
        SourceRecord("openalex", "i1", "Astrophysical Supernova Neutrino Emission Spectra", abstract="Core collapse stellar evolution models."),
        SourceRecord("arxiv", "i2", "Plate Tectonics Subduction Zones in Mesozoic Era", abstract="Geophysical mantle convection."),
    ]
    kw = {"deteksi", "kemiripan", "dokumen", "akademik", "winnowing", "skripsi", "similarity", "thesis", "citation"}
    ranked = sorted(
        (score_candidate_relevance(r, doc_title="Deteksi Kemiripan Dokumen Akademik Winnowing", doc_keywords=kw, matched_query="winnowing academic similarity") for r in rel_pool),
        key=lambda x: -x.relevance_score,
    )
    top5 = [x.record.external_id for x in ranked[:5]]
    rel_hits = sum(1 for x in top5 if x.startswith("r"))
    ret_p5 = round(rel_hits / 5.0, 4)
    ret_r5 = round(rel_hits / 4.0, 4)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    report = {
        "benchmark": "phase9-academic-similarity-detection",
        "mode": "offline_ground_truth_benchmark",
        "scenarios_count": len(scenarios),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "false_positive_rate": fpr,
            "false_negative_rate": fnr,
            "retrieval_precision_at_5": ret_p5,
            "retrieval_recall_at_5": ret_r5,
            "fulltext_acquisition_success_rate": round(ft_acquired / max(1, ft_candidates), 4),
            "cross_source_zero_double_counting": cross_source_no_double_count,
            "processing_time_ms": elapsed_ms,
        },
        "scenarios": details,
        "disclaimer": "Benchmark ini mengukur akurasi mesin open-source NaskahGuard pada korpus ground-truth terkontrol dan tidak mengklaim kesetaraan database tertutup Turnitin.",
    }
    out = ROOT / "benchmark" / "results" / "phase9_detection_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
