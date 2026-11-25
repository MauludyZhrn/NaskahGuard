"""Optional local Tesseract OCR wrapper with auto-discovery, preprocessing, and honest availability reporting."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from app.config import get_settings

try:
    import pytesseract  # type: ignore
except ImportError:
    pytesseract = None  # type: ignore


@dataclass(frozen=True)
class OCRStatus:
    available: bool
    message: str
    binary_path: str | None = None
    languages: list[str] = field(default_factory=list)


def _discover_tesseract_binary() -> str | None:
    settings = get_settings()
    explicit = settings.TESSERACT_CMD.strip()
    if explicit and Path(explicit).is_file():
        return explicit

    found_in_path = shutil.which("tesseract")
    if found_in_path:
        return found_in_path

    # Common Windows local & system installation paths
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app) / "Programs" / "Tesseract-OCR" / "tesseract.exe" if local_app else None,
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for cand in candidates:
        if cand is not None and cand.is_file():
            return str(cand)
    return None


def _list_tesseract_languages(cmd: str) -> list[str]:
    try:
        proc = subprocess.run(
            [cmd, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        lines = [ln.strip() for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
        return [ln for ln in lines if not ln.lower().startswith("list of available") and " " not in ln and len(ln) <= 16]
    except Exception:
        return []


def get_ocr_status() -> OCRStatus:
    settings = get_settings()
    if not settings.OCR_ENABLED:
        return OCRStatus(available=False, message="OCR dinonaktifkan oleh konfigurasi.")
    if pytesseract is None:
        return OCRStatus(available=False, message="Paket Python pytesseract belum terpasang.")
    cmd = _discover_tesseract_binary()
    if not cmd:
        return OCRStatus(
            available=False,
            message="Biner Tesseract OCR tidak ditemukan di PATH sistem maupun direktori standar.",
        )
    pytesseract.pytesseract.tesseract_cmd = cmd
    langs = _list_tesseract_languages(cmd)
    lang_str = ", ".join(langs[:6]) if langs else "default"
    return OCRStatus(
        available=True,
        message=f"Tesseract OCR aktif ({lang_str}).",
        binary_path=cmd,
        languages=langs,
    )


def _run_tesseract_pass(img, lang: str, config: str = "--oem 1 --psm 6") -> tuple[str, float]:
    assert pytesseract is not None
    try:
        data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    except Exception:
        data = pytesseract.image_to_data(img, lang="eng", config=config, output_type=pytesseract.Output.DICT)

    words: list[str] = []
    confs: list[float] = []
    n_boxes = len(data.get("text", []))
    for i in range(n_boxes):
        txt = (data["text"][i] or "").strip()
        conf_raw = str(data.get("conf", ["-1"])[i])
        try:
            conf = float(conf_raw)
        except ValueError:
            conf = -1.0
        if txt:
            words.append(txt)
        if conf >= 0 and txt:
            confs.append(conf / 100.0)

    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return " ".join(words), round(avg_conf, 4)


def _preprocess_for_low_quality(img):
    """Lightweight Pillow cleanup for noisy/low-contrast scanned documents."""
    from PIL import ImageFilter, ImageOps  # type: ignore

    gray = ImageOps.grayscale(img)
    boosted = ImageOps.autocontrast(gray, cutoff=1)
    # Upscale small/low-DPI images for sharper glyph edges
    w, h = boosted.size
    if w < 1400:
        scale = min(2.0, 1600.0 / max(1, w))
        boosted = boosted.resize((int(w * scale), int(h * scale)))
    cleaned = boosted.filter(ImageFilter.MedianFilter(size=3))
    sharpened = cleaned.filter(ImageFilter.SHARPEN)
    return sharpened


def ocr_png_bytes(png_bytes: bytes, lang: str = "ind+eng") -> tuple[str, float]:
    """Run local Tesseract OCR on PNG image bytes and return (text, confidence 0..1)."""
    status = get_ocr_status()
    if not status.available or pytesseract is None:
        raise RuntimeError(status.message)

    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Pillow belum terpasang untuk konversi gambar OCR.") from exc

    # Pick available language pair cleanly
    avail_langs = set(status.languages)
    if avail_langs:
        requested = [p for p in lang.split("+") if p in avail_langs]
        effective_lang = "+".join(requested) if requested else ("eng" if "eng" in avail_langs else next(iter(avail_langs)))
    else:
        effective_lang = lang

    img = Image.open(BytesIO(png_bytes))
    raw_text, raw_conf = _run_tesseract_pass(img, effective_lang)

    # If raw scan has low confidence or sparse text (blur/noise/low-contrast), retry with cleaned grayscale
    if raw_conf < 0.78 or len(raw_text.split()) < 8:
        try:
            prep_img = _preprocess_for_low_quality(img)
            prep_text, prep_conf = _run_tesseract_pass(prep_img, effective_lang)
            if (prep_conf > raw_conf and len(prep_text.split()) >= len(raw_text.split()) * 0.7) or (
                len(prep_text.split()) > len(raw_text.split()) + 5 and prep_conf >= raw_conf - 0.05
            ):
                return prep_text, prep_conf
        except Exception:
            pass

    return raw_text, raw_conf
