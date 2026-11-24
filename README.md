# NaskahGuard

Sistem Pemeriksa Kemiripan Dokumen Akademik Mandiri, Transparan, dan Open-Source (*Local-First*).

> **Catatan Penting:** NaskahGuard bukan pengganti Turnitin/iThenticate dan tidak mengklaim identik dengan layanan tersebut maupun memiliki akses ke basis data tertutup penerbit/institusi.

## Fitur Utama
- **Ingesti Terstruktur**: PDF berbasis teks (`PyMuPDF` / opsi `pypdf` non-AGPL), fallback OCR lokal (Tesseract opsional), DOCX (`python-docx`), dan TXT (UTF-8 / CP1252). Teks asli dipertahankan utuh dengan pemetaan offset karakter presisi.
- **Mesin Deteksi 5 Lapis**:
  1. *Exact Matching*: Hash n-gram kata dengan perluasan rentang maksimal.
  2. *Near-Exact Matching*: Sidik jari Winnowing (`k=5, w=4`), MinHash/LSH (`128` permutasi), serta *seed-and-extend alignment* konservatif.
  3. *Lexical Similarity*: TF-IDF `char_wb (3,5)` + BM25 (terpisah dari skor utama secara default).
  4. *Semantic Similarity (Opsional)*: Embedding multibahasa (`sentence-transformers`), hanya sebagai kandidat tinjauan.
  5. *Source Attribution*: Pelacakan sumber lokal dan sumber terbuka resmi (OpenAlex, Crossref, arXiv, PMC — nonaktif secara default).
- **Perhitungan Skor Transparan**: `SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%` tanpa penghitungan ganda atas kata overlap, dilengkapi pengaturan pengecualian daftar pustaka, kutipan, sitasi, daftar isi, sampul, dan frasa umum.
- **Laporan Interaktif & Ekspor**: Antarmuka React berbahasa Indonesia (mode terang & gelap), penampil dua panel dengan highlight sinkron, analitik visual, diagram alur berangka nyata, serta ekspor PDF, HTML mandiri, dan JSON.

## Cara Menjalankan di Windows

### Prasyarat
- Python 3.10+
- Node.js 20+

### 1. Instalasi Otomatis
```powershell
.\scripts\setup.ps1
```

### 2. Menjalankan Aplikasi Lokal
```powershell
.\scripts\dev.ps1
```
Atau jalankan terpisah:
- Backend: `cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend; npm run dev`
- Akses UI melalui `http://127.0.0.1:5173`.

### 3. Impor Korpus Lokal via CLI
```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli import-corpus ..\samples --source-type contoh_lokal
```

## Opsi Lanjutan
- **PostgreSQL (`pg_trgm` / `pgvector`)**: Ubah `NG_DATABASE_URL` di `backend/.env` menjadi `postgresql+psycopg://user:pass@localhost:5432/naskahguard` dan pasang `psycopg[binary]`.
- **OCR Lokal (Tesseract)**: Pasang biner Tesseract OCR di Windows, tambahkan ke `PATH` (atau atur `NG_TESSERACT_CMD`), serta pasang `pytesseract` dan `Pillow`.
- **Modul Semantik**: Pasang `sentence-transformers` dari `backend/requirements-optional.txt` dan set `NG_SEMANTIC_ENABLED=true`.
- **Backend PDF Non-AGPL**: Atur `NG_PDF_BACKEND=pypdf` apabila ingin menghindari dependensi `pymupdf` (AGPL-3.0).

## Pengujian & Benchmark
```powershell
backend\.venv\Scripts\python.exe -m pytest -q
backend\.venv\Scripts\python.exe benchmark\run_benchmark.py
backend\.venv\Scripts\python.exe scripts\smoke_test.py
```

## Keterbatasan Saat Ini
1. Pengujian lingkungan saat ini berjalan di atas SQLite (PostgreSQL, Tesseract, dan Docker tidak terpasang di mesin host).
2. Nomor halaman pada berkas DOCX bersifat estimasi berbasis pemisah halaman eksplisit.
3. Modul semantik dan OCR tidak aktif secara default kecuali dependensi opsional dipasang.
4. Adapter PMC saat ini menyediakan pencarian metadata E-utilities; pengunduhan arsip XML OA penuh belum diaktifkan.
