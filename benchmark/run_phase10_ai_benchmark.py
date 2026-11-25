"""Phase 10 AI Writing Detection Benchmark & Calibration Runner.

1. Saves train / validation / test / false_positive_stress splits into `benchmark/data/ai_detection/`.
2. Trains + calibrates NaskahGuard AI Detector strictly on train + validation splits.
3. Evaluates strictly on unseen held-out test split and false-positive stress suite.
4. Outputs Precision, Recall, F1, FPR, FNR, ROC-AUC, ECE, Brier Score, per-language (ID vs EN),
   and per-category performance to `benchmark/results/phase10_ai_benchmark.json`.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss, precision_recall_fscore_support, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai_detection.dataset_builder import build_all_splits, save_dataset_splits
from app.ai_detection.detector import analyze_document_ai, fit_and_save_model


def _expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 5) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for idx in range(n_bins):
        lo, hi = bins[idx], bins[idx + 1]
        if idx == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        count = int(np.sum(mask))
        if count == 0:
            continue
        acc = float(np.mean(y_true[mask]))
        conf = float(np.mean(y_prob[mask]))
        ece += (count / max(1, n)) * abs(acc - conf)
    return round(float(ece), 4)


def _compute_binary_metrics(rows: list[dict], probs: list[float], threshold: float = 0.50) -> dict:
    y_true = np.array([int(r["label"]) for r in rows], dtype=int)
    y_prob = np.array(probs, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)

    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))

    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    fpr = fp / max(1, fp + tn)
    fnr = fn / max(1, fn + tp)
    auc = float(roc_auc_score(y_true, y_prob)) if len(set(y_true.tolist())) == 2 else None
    brier = float(brier_score_loss(y_true, y_prob))
    ece = _expected_calibration_error(y_true, y_prob)

    return {
        "count": int(len(rows)),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "fpr": round(float(fpr), 4),
        "fnr": round(float(fnr), 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "brier_score": round(brier, 4),
        "ece": ece,
    }


def main() -> int:
    data_dir = ROOT / "benchmark" / "data" / "ai_detection"
    manifest = save_dataset_splits(data_dir)
    artifact = fit_and_save_model()
    splits = build_all_splits()

    test_rows = splits["test"]
    test_probs: list[float] = []
    test_details: list[dict] = []

    t0 = time.perf_counter()
    for row in test_rows:
        res = analyze_document_ai(str(row["text"]))
        prob = (float(res["ai_likelihood_pct"]) / 100.0) if res["score_available"] and res["ai_likelihood_pct"] is not None else 0.5
        test_probs.append(prob)
        test_details.append({
            "id": row["id"],
            "category": row["category"],
            "lang": row["lang"],
            "label": row["label"],
            "pred_classification": res["classification"],
            "ai_likelihood_pct": res["ai_likelihood_pct"],
            "uncertainty_pct": res["uncertainty_pct"],
        })
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    overall = _compute_binary_metrics(test_rows, test_probs, threshold=0.50)
    strict_threshold = _compute_binary_metrics(test_rows, test_probs, threshold=0.68)
    human_docs = [d for d in test_details if int(d["label"]) == 0]
    strict_ai_false_positives = sum(1 for d in human_docs if d["pred_classification"] == "AI_LIKELY")
    strict_decision_fpr = round(strict_ai_false_positives / max(1, len(human_docs)), 4)

    by_lang: dict[str, dict] = {}
    for lang_code in sorted({str(r["lang"]) for r in test_rows}):
        idx_rows = [r for r in test_rows if r["lang"] == lang_code]
        idx_probs = [p for r, p in zip(test_rows, test_probs) if r["lang"] == lang_code]
        by_lang[lang_code] = _compute_binary_metrics(idx_rows, idx_probs, threshold=0.50)

    by_category: dict[str, dict] = {}
    cat_groups: dict[str, list[tuple[dict, float, dict]]] = defaultdict(list)
    for row, prob, det in zip(test_rows, test_probs, test_details):
        cat_groups[str(row["category"])].append((row, prob, det))
    for cat, items in sorted(cat_groups.items()):
        c_rows = [x[0] for x in items]
        c_probs = [x[1] for x in items]
        c_dets = [x[2] for x in items]
        pred_labels = defaultdict(int)
        for d in c_dets:
            pred_labels[str(d["pred_classification"])] += 1
        correct = sum(1 for r, p in zip(c_rows, c_probs) if int(p >= 0.50) == int(r["label"]))
        by_category[cat] = {
            "count": len(c_rows),
            "true_label": int(c_rows[0]["label"]),
            "accuracy_at_0_5": round(correct / max(1, len(c_rows)), 4),
            "mean_ai_score_pct": round(float(np.mean(c_probs)) * 100.0, 2),
            "classification_distribution": dict(pred_labels),
        }

    # Evaluate false-positive stress suite
    fp_rows = splits["false_positive_stress"]
    fp_results = []
    false_positives = 0
    short_guard_ok = True
    for row in fp_rows:
        res = analyze_document_ai(str(row["text"]))
        flagged_ai = res["classification"] == "AI_LIKELY"
        if row.get("expect_insufficient"):
            guard_passed = res["classification"] == "INSUFFICIENT_DATA"
            short_guard_ok = short_guard_ok and guard_passed
        else:
            guard_passed = not flagged_ai
            if flagged_ai:
                false_positives += 1
        fp_results.append({
            "id": row["id"],
            "category": row["category"],
            "lang": row["lang"],
            "risk_profile": row["risk_profile"],
            "classification": res["classification"],
            "ai_likelihood_pct": res["ai_likelihood_pct"],
            "guard_passed": guard_passed,
        })

    non_short_fp = [r for r in fp_rows if not r.get("expect_insufficient")]
    stress_fpr = round(false_positives / max(1, len(non_short_fp)), 4)

    summary = {
        "model_id": artifact["model_id"],
        "model_version": artifact["version"],
        "dataset_manifest": manifest["splits"],
        "calibration": {
            "temperature": artifact["temperature"],
            "validation_metrics": artifact["validation_metrics"],
        },
        "test_overall": overall,
        "test_at_product_threshold_0_68": {
            **strict_threshold,
            "strict_ai_likely_false_positives": strict_ai_false_positives,
            "strict_ai_likely_fpr": strict_decision_fpr,
        },
        "test_by_language": by_lang,
        "test_by_category": by_category,
        "false_positive_stress": {
            "total_cases": len(fp_rows),
            "false_positive_rate_strict_ai": stress_fpr,
            "short_text_guard_passed": short_guard_ok,
            "cases": fp_results,
        },
        "latency": {
            "total_ms": elapsed_ms,
            "avg_ms_per_doc": round(elapsed_ms / max(1, len(test_rows)), 2),
        },
    }

    out_path = ROOT / "benchmark" / "results" / "phase10_ai_benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
