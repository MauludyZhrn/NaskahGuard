# NaskahGuard — Phase 10.2: Laporan Implementasi & Pengujian Tesseract OCR Lokal

> **Tanggal Verifikasi**: 25 November 2026  
> **Mesin OCR**: Tesseract OCR `v5.4.0.20240606` + `pytesseract 0.3.13` + `Pillow 12.3.0`  
> **Bahasa Terpasang**: `eng` (Bahasa Inggris), `ind` (Bahasa Indonesia), `osd`  
> **Artefak Hasil**: [phase10_2_ocr_eval.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_ocr_eval.json)  
> **Skrip & Tes**: [ocr.py](file:///d:/Projects/NaskahGuard/backend/app/ingestion/ocr.py), [test_phase10_2_ocr_and_completion.py](file:///d:/Projects/NaskahGuard/backend/tests/test_phase10_2_ocr_and_completion.py), [run_phase10_2_ocr_eval.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase10_2_ocr_eval.py)

---

## 1. Arsitektur OCR Lokal (Opsional & Aman)

- **Deteksi Otomatis Biner Windows**: `_discover_tesseract_binary()` memeriksa urutan `NG_TESSERACT_CMD` → `PATH` → `%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe` → `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- **Prapemrosesan Otomatis untuk Pindaian Berkualitas Rendah**: Apabila hasil pass pertama menghasilkan `confidence < 0.78` atau teks sangat sedikit, `_preprocess_for_low_quality()` menjalankan konversi grayscale, `autocontrast`, upscaling aman, `MedianFilter(size=3)`, dan `SHARPEN`, lalu memilih hasil dengan kepercayaan tertinggi.
- **Tidak Merusak Parsing PDF Digital**: Halaman PDF dengan teks digital (`>= 20` karakter non-spasi) tetap diekstrak langsung oleh `PyMuPDF` tanpa menjalankan OCR (`confidence = 1.0`).
- **Transparansi di UI & API**:
  - Halaman **Pengaturan** (`/settings`) menampilkan badge ketersediaan OCR beserta pesan nyata `Tesseract OCR aktif (eng, ind, osd).`.
  - Kartu **Detail Dokumen** pada laporan menampilkan metode ekstraksi (`Teks Langsung`, `OCR (N hlm)`, `Teks + OCR (N hlm)`, atau `Pindaian (OCR Nonaktif)`) beserta persentase `extraction_confidence`.

---

## 2. Hasil Pengujian 5 Skenario Nyata (`run_phase10_2_ocr_eval.py`)

| No | Skenario Uji | Metode Terdeteksi | Halaman OCR | Confidence | Word Recall | Waktu (ms) | Status |
|---|---|---|---|---|---|---|---|
| 1 | **PDF Pindaian — Bahasa Indonesia** | `OCR` | `[1]` | **`0.9427`** (`94.3%`) | **`1.0000`** | `710.61` | **LULUS** |
| 2 | **PDF Pindaian — Bahasa Inggris** | `OCR` | `[1]` | **`0.9260`** (`92.6%`) | **`1.0000`** | `745.04` | **LULUS** |
| 3 | **PDF Campuran (Hlm 1 Teks Digital + Hlm 2 Gambar Scan)** | `MIXED` | `[2]` | **`0.9427`** (`94.3%`) | **`1.0000`** | `692.24` | **LULUS** |
| 4 | **PDF Pindaian Berkualitas Rendah (Blur + Noise + Kontras Rendah)** | `OCR` | `[1]` | **`0.9436`** (`94.4%`) | **`1.0000`** | `791.42` | **LULUS** |
| 5 | **Regresi PDF Teks Digital Murni (Tanpa OCR)** | `TEXT` | `[]` | **`1.0000`** (`100%`) | **`1.0000`** | `76.56` | **LULUS** |

Selain itu, pengujian unit `test_local_ocr_five_scenarios` juga memverifikasi bahwa ketika `NG_OCR_ENABLED=false`, PDF hasil scan mengembalikan status `OCR_UNAVAILABLE` lengkap dengan `ocr_warning` tanpa crash, sementara PDF teks digital tetap berjalan normal (`TEXT`, `1.0`).
