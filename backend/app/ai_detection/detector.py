"""Calibrated local-first AI Writing Detection engine.

Strictly separates probabilistic writing-style indication from plagiarism matching.
Fits scaler + regularized logistic weights ONLY on training data and validation
calibration ONLY on validation data, with explicit guardrails for short or formal texts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.ai_detection.dataset_builder import build_all_splits
from app.ai_detection.features import (
    FEATURE_ORDER,
    NgramEntropyModel,
    detect_text_language,
    extract_feature_dict,
    split_paragraphs,
    tokenize_words,
    vectorize_features,
)
from app.ai_detection.model_registry import BUILTIN_MODEL_ID
from app.config import BASE_DIR, get_settings

DEFAULT_DISCLAIMER_ID = (
    "Hasil deteksi tulisan AI merupakan indikasi statistik pola kebahasaan (probabilistik), "
    "BUKAN bukti mutlak pelanggaran akademik atau kesalahan penulis. Teks akademik formal, terjemahan baku, "
    "maupun naskah pendek dapat memengaruhi skor sehingga tetap memerlukan peninjauan manusia."
)

CLASSIFICATION_META = {
    "HUMAN_LIKELY": {
        "label_id": "Cenderung Tulisan Manusia",
        "tone": "success",
        "description": "Pola panjang kalimat, kekonkretan rujukan, dan variasi gaya lebih selaras dengan tulisan manusia.",
    },
    "MIXED_UNCERTAIN": {
        "label_id": "Campuran / Tidak Pasti",
        "tone": "warning",
        "description": "Terdapat sinyal campuran antara pola tulisan manusia dan AI, atau kepercayaan statistik belum cukup tinggi.",
    },
    "AI_LIKELY": {
        "label_id": "Terindikasi Pola Tulisan AI",
        "tone": "danger",
        "description": "Banyak paragraf menunjukkan keseragaman ritme, diksi simetris generik, dan prediktabilitas pola LLM.",
    },
    "INSUFFICIENT_DATA": {
        "label_id": "Tidak Cukup Bukti",
        "tone": "muted",
        "description": "Teks terlalu pendek atau belum memenuhi syarat minimum analisis sehingga skor tidak dapat disimpulkan secara andal.",
    },
}

_MODEL_CACHE: dict[str, Any] | None = None


def _default_model_path() -> Path:
    return Path(BASE_DIR) / "app" / "data" / "models" / "ng_id_stylo_lm_v1.json"


def fit_and_save_model(artifact_path: Path | None = None) -> dict[str, Any]:
    """Train entropy baseline + regularized generalizable classifier on train+val splits."""
    splits = build_all_splits()
    train_rows = splits["train"]
    val_rows = splits["validation"]

    lm = NgramEntropyModel.fit(train_rows)

    X_train = np.array([vectorize_features(extract_feature_dict(str(r["text"]), lm)) for r in train_rows], dtype=float)
    y_train = np.array([int(r["label"]) for r in train_rows], dtype=int)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    clf = LogisticRegression(C=0.35, max_iter=1000, random_state=42)
    clf.fit(X_train_scaled, y_train)

    X_val = np.array([vectorize_features(extract_feature_dict(str(r["text"]), lm)) for r in val_rows], dtype=float)
    y_val = np.array([int(r["label"]) for r in val_rows], dtype=int)
    val_logits = clf.decision_function(scaler.transform(X_val))

    best_temp = 1.6
    best_nll = float("inf")
    for temp in (1.3, 1.6, 1.9, 2.2, 2.5):
        probs = 1.0 / (1.0 + np.exp(-val_logits / temp))
        eps = 1e-6
        probs_clipped = np.clip(probs, eps, 1.0 - eps)
        nll = float(-np.mean(y_val * np.log(probs_clipped) + (1 - y_val) * np.log(1 - probs_clipped)))
        if nll < best_nll:
            best_nll = nll
            best_temp = temp

    val_probs = 1.0 / (1.0 + np.exp(-val_logits / best_temp))
    val_preds = (val_probs >= 0.5).astype(int)
    val_acc = float(np.mean(val_preds == y_val))

    payload: dict[str, Any] = {
        "model_id": BUILTIN_MODEL_ID,
        "version": "1.0.0",
        "feature_order": list(FEATURE_ORDER),
        "scaler_mean": [round(float(v), 6) for v in scaler.mean_],
        "scaler_scale": [round(float(v), 6) for v in scaler.scale_],
        "coef": [round(float(v), 6) for v in clf.coef_[0]],
        "intercept": round(float(clf.intercept_[0]), 6),
        "temperature": round(float(best_temp), 4),
        "thresholds": {
            "human_max": 0.38,
            "ai_min": 0.68,
            "min_doc_words": 80,
            "min_para_words": 25,
        },
        "validation_metrics": {
            "sample_count": int(len(val_rows)),
            "accuracy": round(val_acc, 4),
            "nll": round(best_nll, 4),
        },
        "ngram_lm": lm.to_dict(),
    }

    target = artifact_path or _default_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def ensure_calibrated_model_loaded(force_reload: bool = False) -> dict[str, Any]:
    global _MODEL_CACHE
    if _MODEL_CACHE is not None and not force_reload:
        return _MODEL_CACHE

    path = _default_model_path()
    if not path.exists():
        artifact = fit_and_save_model(path)
    else:
        artifact = json.loads(path.read_text(encoding="utf-8"))

    artifact["_lm"] = NgramEntropyModel.from_dict(artifact["ngram_lm"])
    _MODEL_CACHE = artifact
    return artifact


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-min(x, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(x, -60.0))
    return z / (1.0 + z)


def _score_raw_probability(feat_dict: dict[str, float], artifact: dict[str, Any]) -> tuple[float, float]:
    """Compute calibrated AI probability with false-positive guardrails & uncertainty."""
    vec = vectorize_features(feat_dict)
    mean = artifact["scaler_mean"]
    scale = artifact["scaler_scale"]
    coef = artifact["coef"]
    intercept = float(artifact["intercept"])
    temp = float(artifact.get("temperature", 1.6))

    z_feats = [(v - m) / (s if abs(s) > 1e-8 else 1.0) for v, m, s in zip(vec, mean, scale)]
    logit = intercept + sum(c * z for c, z in zip(coef, z_feats))
    raw_prob = _sigmoid(logit / max(0.5, temp))

    # Balanced stylometric & specificity calibration check:
    # Concrete field observations / dates / statutes / uneven short sentences lower false accusations,
    # whereas stacked generic LLM markers + symmetric doublets push confidence upward.
    human_credit = (
        min(0.22, feat_dict.get("cite_number_rate", 0.0) * 0.045)
        + min(0.20, feat_dict.get("human_anchor_rate", 0.0) * 0.12)
        + min(0.12, max(0.0, feat_dict.get("sentence_len_cv", 0.0) - 0.30) * 0.45)
    )
    ai_boost = (
        min(0.22, feat_dict.get("ai_marker_rate", 0.0) * 0.14)
        + min(0.16, feat_dict.get("symmetric_doublet_rate", 0.0) * 0.15)
    )

    adjusted_prob = max(0.03, min(0.97, raw_prob - human_credit + ai_boost))
    distance_from_mid = abs(adjusted_prob - 0.5) * 2.0
    uncertainty = round(max(0.09, min(0.45, 0.36 - distance_from_mid * 0.24)), 3)
    return adjusted_prob, uncertainty


def _build_signal_explanations(feat_dict: dict[str, float], prob: float) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    if feat_dict["sentence_len_cv"] < 0.26:
        signals.append({
            "key": "sentence_rhythm",
            "title": "Ritme Panjang Kalimat Seragam",
            "direction": "ai",
            "detail": f"Variasi panjang kalimat relatif datar (CV={feat_dict['sentence_len_cv']:.2f}), pola yang sering muncul pada teks generasi LLM.",
        })
    elif feat_dict["sentence_len_cv"] >= 0.34 or feat_dict["short_sentence_ratio"] >= 0.2:
        signals.append({
            "key": "sentence_rhythm",
            "title": "Variasi Panjang Kalimat Alami (Burstiness Tinggi)",
            "direction": "human",
            "detail": f"Kalimat pendek dan panjang bergantian secara alami (CV={feat_dict['sentence_len_cv']:.2f}), khas penulisan manusia.",
        })

    if feat_dict["ai_marker_rate"] >= 0.45 or feat_dict["symmetric_doublet_rate"] >= 0.4:
        signals.append({
            "key": "discourse_markers",
            "title": "Transisi & Frasa Simetris Khas LLM",
            "direction": "ai",
            "detail": "Terdapat penghubung retoris generik atau pasangan kata sifat simetris yang sering dipakai model bahasa.",
        })

    if feat_dict["human_anchor_rate"] > 0.15 or feat_dict["cite_number_rate"] >= 1.2:
        signals.append({
            "key": "empirical_specificity",
            "title": "Rujukan Spesifik & Penanda Konteks Nyata",
            "direction": "human",
            "detail": "Teks memuat angka spesifik, bulan/pasal, atau pengalaman observasi langsung yang menurunkan risiko salah deteksi.",
        })

    if not signals:
        signals.append({
            "key": "balanced_profile",
            "title": "Profil Fitur Cenderung Netral",
            "direction": "neutral" if prob < 0.68 else "ai",
            "detail": "Tidak ada satu fitur tunggal yang ekstrem; keputusan ditarik dari gabungan seluruh sinyal kebahasaan.",
        })
    return signals


def classify_paragraph(
    text: str,
    para_index: int,
    char_start: int,
    char_end: int,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    art = artifact or ensure_calibrated_model_loaded()
    lm: NgramEntropyModel = art["_lm"]
    words = tokenize_words(text)
    word_count = len(words)
    min_para_words = int(art["thresholds"].get("min_para_words", 25))

    if word_count < min_para_words:
        return {
            "paragraph_index": para_index,
            "char_start": char_start,
            "char_end": char_end,
            "word_count": word_count,
            "text": text,
            "classification": "INSUFFICIENT_DATA",
            "classification_label": CLASSIFICATION_META["INSUFFICIENT_DATA"]["label_id"],
            "ai_likelihood_pct": None,
            "uncertainty_pct": None,
            "highlighted": False,
            "reasons": ["Paragraf terlalu singkat (< 25 kata) untuk dinilai secara andal."],
        }

    feats = extract_feature_dict(text, lm)
    prob, uncertainty = _score_raw_probability(feats, art)
    pct = round(prob * 100.0, 1)

    if prob >= 0.68:
        label_code = "AI_LIKELY"
    elif prob <= 0.38:
        label_code = "HUMAN_LIKELY"
    else:
        label_code = "MIXED_UNCERTAIN"

    signals = _build_signal_explanations(feats, prob)
    reasons = [s["detail"] for s in signals[:2]]

    return {
        "paragraph_index": para_index,
        "char_start": char_start,
        "char_end": char_end,
        "word_count": word_count,
        "text": text,
        "classification": label_code,
        "classification_label": CLASSIFICATION_META[label_code]["label_id"],
        "ai_likelihood_pct": pct,
        "uncertainty_pct": round(uncertainty * 100.0, 1),
        "highlighted": label_code in ("AI_LIKELY", "MIXED_UNCERTAIN"),
        "reasons": reasons,
        "features": {
            "sentence_len_cv": feats["sentence_len_cv"],
            "ai_marker_rate": feats["ai_marker_rate"],
            "human_anchor_rate": feats["human_anchor_rate"],
        },
    }


def analyze_document_ai(text: str, model_id: str | None = None) -> dict[str, Any]:
    """Run conservative document + paragraph AI writing pattern analysis."""
    cfg = get_settings()
    art = ensure_calibrated_model_loaded()
    lm: NgramEntropyModel = art["_lm"]
    min_doc_words = int(getattr(cfg, "AI_MIN_WORDS", art["thresholds"].get("min_doc_words", 80)))
    chosen_model_id = model_id or BUILTIN_MODEL_ID

    lang_info = detect_text_language(text)
    words = tokenize_words(text)
    word_count = len(words)
    paragraphs_raw = split_paragraphs(text)

    limitations = [
        "Hasil berbasis pola statistik kebahasaan dan ritme kalimat pada tingkat dokumen dan paragraf.",
        "Teks yang disunting secara berat atau diparafrasekan ulang dapat menurunkan ketajaman klasifikasi.",
    ]
    if not lang_info["supported"]:
        limitations.append(
            f"Bahasa dominan terdeteksi sebagai '{lang_info['label']}'. Akurasi kalibrasi paling andal pada Bahasa Indonesia dan Inggris."
        )
    if chosen_model_id != BUILTIN_MODEL_ID:
        limitations.append(
            f"Model '{chosen_model_id}' dipilih; jika bobot eksternal belum terpasang, inferensi dialihkan aman ke model kalibrasi CPU bawaan."
        )

    para_results = [
        classify_paragraph(p.text, p.index, p.char_start, p.char_end, art)
        for p in paragraphs_raw
    ]

    para_summary = {
        "total_paragraphs": len(para_results),
        "ai_likely_count": sum(1 for p in para_results if p["classification"] == "AI_LIKELY"),
        "human_likely_count": sum(1 for p in para_results if p["classification"] == "HUMAN_LIKELY"),
        "uncertain_count": sum(1 for p in para_results if p["classification"] == "MIXED_UNCERTAIN"),
        "insufficient_count": sum(1 for p in para_results if p["classification"] == "INSUFFICIENT_DATA"),
    }
    calibration_meta = {
        "calibrated": True,
        "method": "Temperature Scaling + Ambang Konservatif",
        "temperature": float(art.get("temperature", 1.3)),
        "ai_threshold": float(art.get("thresholds", {}).get("ai_min", 0.68)),
        "human_threshold": float(art.get("thresholds", {}).get("human_max", 0.38)),
        "validation_metrics": art.get("validation_metrics", {}),
    }

    if word_count < min_doc_words:
        return {
            "score_available": False,
            "ai_likelihood_pct": None,
            "classification": "INSUFFICIENT_DATA",
            "classification_label": CLASSIFICATION_META["INSUFFICIENT_DATA"]["label_id"],
            "classification_description": CLASSIFICATION_META["INSUFFICIENT_DATA"]["description"],
            "confidence_label": "Tidak Cukup Bukti",
            "uncertainty_pct": None,
            "word_count": word_count,
            "min_words_required": min_doc_words,
            "language": lang_info,
            "model_used": BUILTIN_MODEL_ID,
            "requested_model": chosen_model_id,
            "calibration": calibration_meta,
            "paragraph_summary": para_summary,
            "summary_id": (
                f"Teks hanya memiliki {word_count} kata (batas minimum {min_doc_words} kata), "
                "sehingga sistem menolak menyimpulkan indikasi tulisan AI untuk menghindari tuduhan keliru."
            ),
            "signals": [],
            "paragraphs": para_results,
            "highlights": [],
            "limitations": limitations,
            "disclaimer": DEFAULT_DISCLAIMER_ID,
        }

    doc_feats = extract_feature_dict(text, lm)
    doc_prob, doc_unc = _score_raw_probability(doc_feats, art)

    analyzed_paras = [p for p in para_results if p["ai_likelihood_pct"] is not None]
    if analyzed_paras:
        total_pw = sum(p["word_count"] for p in analyzed_paras)
        weighted_para_prob = sum((float(p["ai_likelihood_pct"]) / 100.0) * p["word_count"] for p in analyzed_paras) / max(1, total_pw)
        blended_prob = (0.58 * doc_prob) + (0.42 * weighted_para_prob)
        para_probs = [float(p["ai_likelihood_pct"]) / 100.0 for p in analyzed_paras]
        has_strong_ai_para = any(pp >= 0.68 for pp in para_probs)
        has_strong_human_para = any(pp <= 0.38 for pp in para_probs)
    else:
        blended_prob = doc_prob
        has_strong_ai_para = False
        has_strong_human_para = False

    if blended_prob >= 0.68 and not (has_strong_human_para and has_strong_ai_para and blended_prob < 0.76):
        classification = "AI_LIKELY"
    elif blended_prob <= 0.38 and not has_strong_ai_para:
        classification = "HUMAN_LIKELY"
    else:
        classification = "MIXED_UNCERTAIN"

    if word_count < 110 and classification == "AI_LIKELY" and blended_prob < 0.76:
        classification = "MIXED_UNCERTAIN"

    if doc_unc <= 0.16:
        confidence_label = "Tinggi (Indikatif)"
    elif doc_unc <= 0.28:
        confidence_label = "Sedang"
    else:
        confidence_label = "Rendah / Perlu Telaah Lanjut"

    signals = _build_signal_explanations(doc_feats, blended_prob)
    highlights = [
        {
            "paragraph_index": p["paragraph_index"],
            "char_start": p["char_start"],
            "char_end": p["char_end"],
            "classification": p["classification"],
            "classification_label": p["classification_label"],
            "ai_likelihood_pct": p["ai_likelihood_pct"],
            "reasons": p["reasons"],
            "excerpt": p["text"][:220],
        }
        for p in analyzed_paras
        if p["highlighted"]
    ]

    ai_pct = round(blended_prob * 100.0, 1)
    if classification == "HUMAN_LIKELY":
        summary_id = (
            f"Secara keseluruhan pola bahasa cenderung konsisten dengan tulisan manusia "
            f"(indikasi pola AI sekitar {ai_pct}%). Tidak ditemukan dominasi pola teks generik AI."
        )
    elif classification == "MIXED_UNCERTAIN":
        summary_id = (
            f"Dokumen menunjukkan pola campuran atau tingkat keyakinan moderat "
            f"(indikasi pola AI sekitar {ai_pct}%, ketidakpastian ±{round(doc_unc * 100.0, 1)}%). "
            "Sebagian paragraf terasa seragam sementara bagian lain menunjukkan gaya alami manusia."
        )
    else:
        summary_id = (
            f"Teridentifikasi pola penulisan yang sering muncul pada teks buatan AI "
            f"(indikasi pola AI sekitar {ai_pct}% pada {len(highlights)} dari {len(analyzed_paras)} paragraf). "
            "Tetap lakukan pemeriksaan substansi karena skor ini bersifat probabilistik."
        )

    return {
        "score_available": True,
        "ai_likelihood_pct": ai_pct,
        "classification": classification,
        "classification_label": CLASSIFICATION_META[classification]["label_id"],
        "classification_description": CLASSIFICATION_META[classification]["description"],
        "confidence_label": confidence_label,
        "uncertainty_pct": round(doc_unc * 100.0, 1),
        "word_count": word_count,
        "min_words_required": min_doc_words,
        "language": lang_info,
        "model_used": BUILTIN_MODEL_ID,
        "requested_model": chosen_model_id,
        "calibration": calibration_meta,
        "paragraph_summary": para_summary,
        "summary_id": summary_id,
        "signals": signals,
        "paragraphs": para_results,
        "highlights": highlights,
        "feature_snapshot": {
            "sentence_len_cv": doc_feats["sentence_len_cv"],
            "mattr_35": doc_feats["mattr_35"],
            "opener_diversity": doc_feats["opener_diversity"],
            "ai_marker_rate": doc_feats["ai_marker_rate"],
            "symmetric_doublet_rate": doc_feats["symmetric_doublet_rate"],
            "human_anchor_rate": doc_feats["human_anchor_rate"],
            "cite_number_rate": doc_feats["cite_number_rate"],
            "char_cross_entropy": doc_feats["char_cross_entropy"],
        },
        "limitations": limitations,
        "disclaimer": DEFAULT_DISCLAIMER_ID,
    }
