"""Phase 10.2 OCR Benchmark & Verification Runner (5 real Tesseract OCR scenarios)."""
from __future__ import annotations

import io
import json
import random
import sys
import tempfile
import time
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ingestion.ocr import get_ocr_status
from app.ingestion.pdf import extract_pdf

OUT_JSON = ROOT / "benchmark" / "results" / "phase10_2_ocr_eval.json"


def _font(size: int = 36):
    for cand in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf"):
        if Path(cand).is_file():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def _img(lines: list[str], degrade: bool = False) -> bytes:
    im = Image.new("RGB", (1440, 520), color=(244, 242, 238) if degrade else (255, 255, 255))
    dr = ImageDraw.Draw(im)
    f = _font(36)
    y = 60
    ink = (72, 72, 72) if degrade else (12, 12, 12)
    for ln in lines:
        dr.text((70, y), ln, fill=ink, font=f)
        y += 62
    if degrade:
        rng = random.Random(102)
        px = im.load()
        for _ in range(5000):
            v = rng.randint(135, 225)
            px[rng.randint(0, im.width - 1), rng.randint(0, im.height - 1)] = (v, v, v)
        im = im.filter(ImageFilter.GaussianBlur(radius=0.85))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _word_recall(expected: str, actual: str) -> float:
    exp_w = [w.strip(".,;:!?").lower() for w in expected.split() if w.strip(".,;:!?")]
    act_s = {w.strip(".,;:!?").lower() for w in actual.split() if w.strip(".,;:!?")}
    if not exp_w:
        return 0.0
    hits = sum(1 for w in exp_w if w in act_s)
    return round(hits / len(exp_w), 4)


def main() -> int:
    st = get_ocr_status()
    scenarios_out = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        id_lines = [
            "Penelitian kemiripan dokumen akademik",
            "berbasis korpus lokal di perguruan tinggi",
            "menjaga integritas karya ilmiah mahasiswa.",
        ]
        en_lines = [
            "Academic integrity verification relies on",
            "transparent document comparison against",
            "open scholarly archives and local corpora.",
        ]
        deg_lines = [
            "Evaluasi mutu arsip pindaian berkualitas rendah",
            "tetap terbaca menggunakan prapemrosesan gambar.",
        ]

        specs = [
            ("1_scanned_pdf_indonesian", [("image", _img(id_lines, False))], " ".join(id_lines)),
            ("2_scanned_pdf_english", [("image", _img(en_lines, False))], " ".join(en_lines)),
            (
                "3_mixed_text_and_image_pdf",
                [("text", "Halaman pertama berisi teks digital asli tentang metode penelitian kuantitatif."), ("image", _img(id_lines, False))],
                "Halaman pertama berisi teks digital asli tentang metode penelitian kuantitatif. " + " ".join(id_lines),
            ),
            ("4_low_quality_noisy_blurred_scan", [("image", _img(deg_lines, True))], " ".join(deg_lines)),
            ("5_native_digital_pdf_regression", [("text", "Dokumen PDF teks digital murni berjalan cepat tanpa OCR.")], "Dokumen PDF teks digital murni berjalan cepat tanpa OCR."),
        ]

        for name, pages, expected in specs:
            pdf_p = tmp / f"{name}.pdf"
            doc = fitz.open()
            for kind, payload in pages:
                pg = doc.new_page(width=595.28, height=841.89)
                if kind == "image":
                    pg.insert_image(fitz.Rect(36, 72, 559, 290), stream=payload)
                else:
                    pg.insert_textbox(fitz.Rect(54, 72, 540, 480), str(payload), fontsize=12, fontname="helv")
            doc.save(str(pdf_p))
            doc.close()

            t0 = time.perf_counter()
            ext = extract_pdf(pdf_p)
            ms = round((time.perf_counter() - t0) * 1000.0, 2)
            scenarios_out.append({
                "scenario": name,
                "extraction_method": ext.extraction_method,
                "ocr_pages": ext.ocr_pages,
                "extraction_confidence": ext.extraction_confidence,
                "word_recall": _word_recall(expected, ext.text),
                "extracted_chars": len(ext.text),
                "latency_ms": ms,
                "extracted_preview": ext.text[:180],
            })

    summary = {
        "ocr_status": {
            "available": st.available,
            "message": st.message,
            "binary_path": st.binary_path,
            "languages": st.languages,
        },
        "scenarios": scenarios_out,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
