"""AI Detection Model Registry, compatibility metadata, and optional HF adapter state."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, get_settings

BUILTIN_MODEL_ID = "ng-id-stylo-lm-v1"


def _package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _artifact_path(model_id: str) -> Path:
    return Path(BASE_DIR) / "app" / "data" / "models" / f"{model_id.replace('-', '_')}.json"


def _cache_dir() -> Path:
    cfg = get_settings()
    path = Path(getattr(cfg, "AI_LOCAL_CACHE_DIR", Path(BASE_DIR) / "data" / "models"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_model_catalog() -> list[dict[str, Any]]:
    has_torch = _package_available("torch")
    has_transformers = _package_available("transformers")
    builtin_file = _artifact_path(BUILTIN_MODEL_ID)
    hf_cache = _cache_dir()

    fast_detect_ready = has_torch and has_transformers and (hf_cache / "ng_fast_detect_curv_en").exists()
    enc_ready = has_torch and has_transformers and (hf_cache / "ng_mdistilbert_enc_v1").exists()

    return [
        {
            "id": BUILTIN_MODEL_ID,
            "name": "NaskahGuard Calibrated Stylometry + N-gram LM v1",
            "family": "Statistical N-gram Entropy + Academic Stylometry",
            "source_reference": "Terinspirasi prinsip entropi/chunking IsItAI (MIT) & fitur stilometri akademik lokal",
            "license": "Apache-2.0 / Built-in",
            "tier": "BUILTIN_CPU",
            "languages": ["id", "en"],
            "indonesian_support": "Terkalibrasi penuh untuk Bahasa Indonesia dan Bahasa Inggris akademik",
            "requirements": {
                "runtime": "CPU standar (tanpa GPU)",
                "min_ram_mb": 64,
                "disk_mb": 2,
                "offline_capable": True,
                "dependencies_installed": True,
            },
            "installed": builtin_file.exists(),
            "status": "READY" if builtin_file.exists() else "NEEDS_CALIBRATION",
            "artifact_path": str(builtin_file),
            "limitations": [
                "Bersifat indikatif probabilistik, bukan detektor deterministik.",
                "Teks di bawah 80 kata dikembalikan sebagai TIDAK CUKUP BUKTI.",
            ],
        },
        {
            "id": "ng-fast-detect-curv-en",
            "name": "Fast-DetectGPT Conditional Curvature Adapter (Opsional)",
            "family": "Zero-Shot LM Curvature (Fast-DetectGPT)",
            "source_reference": "Croups/is-it-ai (MIT License) & DetectGPT (MIT License)",
            "license": "MIT / HuggingFace model weights",
            "tier": "OPTIONAL_HF",
            "languages": ["en", "id (terbatas — belum dikalibrasi khusus ID)"],
            "indonesian_support": "Terbatas: kurvatur model kausal default lebih stabil untuk Bahasa Inggris; membutuhkan kalibrasi tambahan untuk Bahasa Indonesia",
            "requirements": {
                "runtime": "Python >=3.10 + torch + transformers (~3.2 GB RAM CPU)",
                "min_ram_mb": 3200,
                "disk_mb": 1600,
                "offline_capable": True,
                "dependencies_installed": has_torch and has_transformers,
                "missing_packages": [p for p, ok in (("torch", has_torch), ("transformers", has_transformers)) if not ok],
            },
            "installed": fast_detect_ready,
            "status": "READY" if fast_detect_ready else ("DEPS_MISSING" if not (has_torch and has_transformers) else "NOT_DOWNLOADED"),
            "artifact_path": str(hf_cache / "ng_fast_detect_curv_en"),
            "limitations": [
                "Memerlukan PyTorch + Transformers serta RAM minimal 3,2 GB pada CPU.",
                "Tidak otomatis aktif agar NaskahGuard tetap ringan di Windows standar.",
            ],
        },
        {
            "id": "ng-mdistilbert-enc-v1",
            "name": "Multilingual DistilBERT Encoder Classifier (Opsional)",
            "family": "Transformer Sequence Classification",
            "source_reference": "Pola evaluasi encoder multibahasa (mELECTRA / DistilBERT, mBERT benchmark)",
            "license": "Apache-2.0 (model dasar)",
            "tier": "OPTIONAL_HF",
            "languages": ["en", "fr (belum fine-tuned untuk Bahasa Indonesia)"],
            "indonesian_support": "Tidak disarankan sebagai model utama Bahasa Indonesia sebelum fine-tuning korpus ID",
            "requirements": {
                "runtime": "torch + transformers (~1.1 GB RAM CPU; GPU disarankan untuk dokumen panjang)",
                "min_ram_mb": 1100,
                "disk_mb": 560,
                "offline_capable": True,
                "dependencies_installed": has_torch and has_transformers,
                "missing_packages": [p for p, ok in (("torch", has_torch), ("transformers", has_transformers)) if not ok],
            },
            "installed": enc_ready,
            "status": "READY" if enc_ready else ("DEPS_MISSING" if not (has_torch and has_transformers) else "NOT_DOWNLOADED"),
            "artifact_path": str(hf_cache / "ng_mdistilbert_enc_v1"),
            "limitations": [
                "Tidak menyertakan bobot terlatih khusus Bahasa Indonesia secara bawaan.",
                "Butuh unduhan model eksternal secara manual bila pengguna ingin menguji encoder lokal.",
            ],
        },
    ]


def get_active_model_id(db=None) -> str:
    if db is not None:
        from app.models import AppSetting
        row = db.query(AppSetting).filter(AppSetting.key == "ai_active_model").first()
        if row and isinstance(row.value, dict) and row.value.get("model_id"):
            return str(row.value["model_id"])
    cfg = get_settings()
    return str(getattr(cfg, "AI_DEFAULT_MODEL", BUILTIN_MODEL_ID))


def list_models(db=None) -> dict[str, Any]:
    active_id = get_active_model_id(db)
    catalog = get_model_catalog()
    for item in catalog:
        item["active"] = item["id"] == active_id
    return {
        "active_model_id": active_id,
        "models": catalog,
    }


def activate_model(model_id: str, db=None) -> dict[str, Any]:
    catalog = {m["id"]: m for m in get_model_catalog()}
    if model_id not in catalog:
        raise ValueError(f"Model '{model_id}' tidak terdaftar.")
    target = catalog[model_id]
    if not target["installed"]:
        missing = target["requirements"].get("missing_packages") or []
        if missing:
            raise RuntimeError(
                f"Model '{model_id}' memerlukan paket Python opsional ({', '.join(missing)}) yang belum terpasang di lingkungan lokal."
            )
        raise RuntimeError(
            f"Bobot lokal untuk '{model_id}' belum tersedia di {target['artifact_path']}. Unduh atau verifikasi model terlebih dahulu."
        )
    if db is not None:
        from app.models import AppSetting
        row = db.query(AppSetting).filter(AppSetting.key == "ai_active_model").first()
        if row is None:
            db.add(AppSetting(key="ai_active_model", value={"model_id": model_id}))
        else:
            row.value = {"model_id": model_id}
        db.commit()
    return {"active_model_id": model_id, "model": target}


def verify_model(model_id: str) -> dict[str, Any]:
    catalog = {m["id"]: m for m in get_model_catalog()}
    if model_id not in catalog:
        raise ValueError(f"Model '{model_id}' tidak terdaftar.")
    target = catalog[model_id]
    if model_id == BUILTIN_MODEL_ID:
        from app.ai_detection.detector import ensure_calibrated_model_loaded
        model = ensure_calibrated_model_loaded()
        return {
            "model_id": model_id,
            "verified": True,
            "installed": True,
            "calibration_version": model.get("version"),
            "validation_summary": model.get("validation_metrics", {}),
            "message": "Model kalibrasi lokal terverifikasi siap digunakan secara luring.",
        }
    return {
        "model_id": model_id,
        "verified": bool(target["installed"]),
        "installed": bool(target["installed"]),
        "requirements": target["requirements"],
        "message": (
            "Model opsional siap digunakan."
            if target["installed"]
            else "Dependensi opsional atau file bobot lokal belum tersedia; gunakan model bawaan CPU atau pasang torch + transformers secara eksplisit."
        ),
    }
