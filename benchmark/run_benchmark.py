"""Runner benchmark evaluasi 12 kasus NaskahGuard (mengukur Precision, Recall, F1, FPR, FNR, waktu, memori)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT))

from app import config, db as db_mod  # noqa: E402
from app.engine.pipeline import run_check_pipeline  # noqa: E402
from app.ingestion.service import ingest_validated_upload  # noqa: E402
from app.ingestion.validators import validate_local_bytes  # noqa: E402
from app.main import run_migrations  # noqa: E402
from app.models import Check, Match  # noqa: E402
from benchmark.cases import build_benchmark_cases  # noqa: E402


def _compute_prf(pred: set[int], gt: set[int], total_tokens: int) -> dict[str, float]:
    tp = len(pred & gt)
    fp = len(pred - gt)
    fn = len(gt - pred)
    tn = max(0, total_tokens - tp - fp - fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if len(gt) == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if len(gt) == 0 else 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "fnr": round(fnr, 4),
    }


def main() -> int:
    cases = build_benchmark_cases()
    results = []

    agg = {
        "EXACT": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "NEAR_EXACT": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "LEXICAL": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
    }

    with tempfile.TemporaryDirectory(prefix="ng_bench_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for c in cases:
            case_dir = tmp_path / f"case_{c.case_id}"
            storage = case_dir / "storage"
            storage.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{(case_dir / 'bench.db').as_posix()}"

            import os
            os.environ["NG_DATABASE_URL"] = db_url
            os.environ["NG_STORAGE_DIR"] = str(storage)
            config.get_settings.cache_clear()
            run_migrations(db_url)
            db = db_mod.get_session_factory()()

            try:
                for idx, (title, txt) in enumerate(c.corpus_docs, start=1):
                    v = validate_local_bytes(f"corp_{c.case_id}_{idx}.txt", txt.encode("utf-8"), 10_000_000)
                    ingest_validated_upload(db, v, role="CORPUS", title=title)

                v_sub = validate_local_bytes(f"sub_{c.case_id}.txt", c.submission_text.encode("utf-8"), 10_000_000)
                sub_doc = ingest_validated_upload(db, v_sub, role="SUBMISSION")

                chk = Check(
                    report_number=f"NG-BENCH-{c.case_id:02d}",
                    document_id=sub_doc.id,
                    status="QUEUED",
                    stage="Antrean",
                    progress=0,
                    settings=c.settings,
                    stage_counts={},
                    metrics={},
                    coverage={},
                )
                db.add(chk)
                db.commit()

                tracemalloc.start()
                t0 = time.perf_counter()
                run_check_pipeline(db, chk.id)
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                _, peak_bytes = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                db.refresh(chk)
                matches = db.query(Match).filter(Match.check_id == chk.id).all()

                pred_exact: set[int] = set()
                pred_near: set[int] = set()
                pred_lex: set[int] = set()
                for m in matches:
                    span = set(range(m.sub_token_start, m.sub_token_end))
                    if m.layer == "EXACT" and m.counted:
                        pred_exact.update(span)
                    elif m.layer == "NEAR_EXACT" and m.counted:
                        pred_near.update(span)
                    elif m.layer == "LEXICAL":
                        pred_lex.update(span)

                # For near-exact, compare combined textual coverage (EXACT + NEAR_EXACT) against gt_exact | gt_near_exact
                total_toks = sub_doc.word_count
                m_exact = _compute_prf(pred_exact, c.gt_exact, total_toks)
                m_near = _compute_prf(pred_exact | pred_near, c.gt_exact | c.gt_near_exact, total_toks)
                m_lex = _compute_prf(pred_lex, c.gt_lexical, total_toks)

                for layer_key, stat, gt_set in (
                    ("EXACT", m_exact, c.gt_exact),
                    ("NEAR_EXACT", m_near, c.gt_exact | c.gt_near_exact),
                    ("LEXICAL", m_lex, c.gt_lexical),
                ):
                    if gt_set or stat["fp"] > 0:
                        agg[layer_key]["tp"] += stat["tp"]
                        agg[layer_key]["fp"] += stat["fp"]
                        agg[layer_key]["fn"] += stat["fn"]
                        agg[layer_key]["tn"] += max(0, total_toks - stat["tp"] - stat["fp"] - stat["fn"])

                results.append(
                    {
                        "case_id": c.case_id,
                        "name": c.name,
                        "status": chk.status,
                        "similarity_index": chk.metrics.get("similarity_index", 0.0),
                        "raw_similarity": chk.metrics.get("raw_similarity", 0.0),
                        "exact_metrics": m_exact,
                        "near_exact_combined_metrics": m_near,
                        "lexical_metrics": m_lex,
                        "elapsed_ms": elapsed_ms,
                        "peak_memory_kb": round(peak_bytes / 1024.0, 1),
                    }
                )
            finally:
                db.close()
                db_mod.get_engine().dispose()

    summary_layers = {}
    for layer_key, counts in agg.items():
        tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        summary_layers[layer_key] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            **counts,
        }

    out_payload = {
        "total_cases": len(cases),
        "layer_summary": summary_layers,
        "cases": results,
    }
    out_dir = ROOT / "benchmark" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "latest.json"
    out_file.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Ringkasan Benchmark NaskahGuard ===")
    for lk, vals in summary_layers.items():
        print(f"Layer {lk:10s}: Precision={vals['precision']:.4f} Recall={vals['recall']:.4f} F1={vals['f1']:.4f} FPR={vals['fpr']:.4f} FNR={vals['fnr']:.4f}")
    for r in results:
        print(f"Case {r['case_id']:02d} ({r['name']}): SI={r['similarity_index']:.2f}% Raw={r['raw_similarity']:.2f}% Time={r['elapsed_ms']}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
