"""Optional local Tesseract OCR wrapper with honest availability reporting."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from app.config import get_settings

try:
    import pytesseract  # type: ignore
except ImportError:
    pytesseract = None  # type: ignore


@dataclass(frozen=True)
class OCRStatus:
    available: bool
    message: str


def get_ocr_status() -> OCRStatus:
    settings = get_settings()
    if not settings.OCR_ENABLED:
        return OCRStatus(available=False, message="OCR dinonaktifkan oleh konfigurasi.")
    if pytesseract is None:
        return OCRStatus(available=False, message="Paket Python pytesseract belum terpasang.")
    cmd = settings.TESSERACT_CMD.strip() or shutil.which("tesseract")
    if not cmd:
        return OCRStatus(
            available=False,
            message="Biner Tesseract OCR tidak ditemukan di PATH sistem.",
        )
    pytesseract.pytesseract.tesseract_cmd = cmd
    return OCRStatus(available=True, message=f"Tesseract OCR tersedia ({cmd}).")


def ocr_png_bytes(png_bytes: bytes, lang: str = "ind+eng") -> tuple[str, float]:
    """Run OCR on PNG image bytes and return (text, confidence 0..1)."""
    status = get_ocr_status()
    if not status.available or pytesseract is None:
        raise RuntimeError(status.message)

    from io import BytesIO
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Pillow belum terpasang untuk konversi gambar OCR.") from exc

    img = Image.open(BytesIO(png_bytes))
    try:
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    except Exception:
        data = pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)

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
        if conf >= 0:
            confs.append(conf / 100.0)

    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return " ".join(words), round(avg_conf, 4)
