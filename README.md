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


---

## Pembaruan Phase 8 — Product Refinement, UI/UX Redesign & Search Intelligence

- **Desain UI/UX (`ui-ux-pro-max`)**: Design tokens terpusat (`tokens.css` & `theme.css`), Light & Dark Mode konsisten, **Collapsible Sidebar** (`260px`/`72px` + persistensi `localStorage` + mobile drawer), halaman baru **Repositori Akademik (`/repositories`)** dan **Analitik (`/analytics`)**, serta navigasi 8-tab laporan 1 baris responsif.
- **Transparansi Skor & Cakupan**: Accordion **"Bagaimana skor dihitung?"** (rumus nyata backend, Exact/Near/Lexical, overlap removal, Raw vs Adjusted), 9 metrik sumber terpisah tanpa ambiguitas, format durasi manusiawi Bahasa Indonesia, dan rincian waktu tahapan (`stage_timings_ms`).
- **Optimasi Intelijen Pencarian**: Multi-Query Generator berprofil (`QUICK` ≤ 8, `BALANCED` ≤ 24, `DEEP` ≤ 48) dengan distribusi per bab, Search Quality Ranking (`HIGHLY_RELEVANT`–`UNRELATED`), TTL cache URL/DOI, konkurensi crawl terbatas, telemetri kesehatan provider (`/api/providers`), serta panduan opsional [docker-compose.searxng.yml](docker-compose.searxng.yml).
- **Dokumentasi Phase 8**: [UI_UX_DESIGN_SYSTEM.md](docs/UI_UX_DESIGN_SYSTEM.md), [SEARCH_OPTIMIZATION.md](docs/SEARCH_OPTIMIZATION.md), [SEARCH_BENCHMARK.md](docs/SEARCH_BENCHMARK.md), [FRONTEND_COMPONENT_GUIDE.md](docs/FRONTEND_COMPONENT_GUIDE.md), [PHASE8_QA_REPORT.md](docs/PHASE8_QA_REPORT.md), dan [PHASE8_SEARCH_AUDIT.md](docs/research/PHASE8_SEARCH_AUDIT.md).


---

## Pembaruan Phase 9 — Advanced Design System, Browser Intelligence & Detection Engine Upgrade

- **Agent Skills Terintegrasi**: `ui-ux-pro-max`, `shadcn`, `magic-ui`, `scrapling-official`, `mineru`, `scholar-search`, dan `tufte-data-viz` aktif di `.agents/skills/`.
- **Modernisasi UI/UX (`shadcn/ui` + `Magic UI` Selektif)**:
  - Konfigurasi Tailwind non-destruktif (`components.json`, alias `@/*`, variabel semantik Light/Dark), 19 komponen primitif resmi `shadcn/ui`, serta motion mikro `NumberTicker` & `BlurFade` yang menghormati `prefers-reduced-motion`.
  - **Perbaikan Laporan Kemiripan**: Penghapusan total navigasi ganda pada desktop (`1600px`, `1440px`, `1280px`, `768px`, `390px`), tata letak ringkasan skor proporsional, accordion **"Penjelasan Perhitungan Similarity"** (termasuk nilai presisi sebelum pembulatan & penjelasan selisih pembulatan `0,01%`), 9 kategori transparansi sumber terpisah, paginasi tabel kecocokan, dialog detail sumber, serta *sticky toolbar* pada viewer perbandingan.
- **Browser Intelligence & Pencarian Live**:
  - Antarmuka modular `IsolatedPlaywrightExtractor` (`extract()` & `health_check()`) dengan isolasi konteks penuh, follow otomatis `citation_pdf_url` OA, serta hasil benchmark 22 URL terhadap Crawl4AI & Scrapling.
  - Penambahan provider Open Access **DOAJ** (`doaj.py`) dan endpoint diagnostik konektivitas nyata `POST /api/providers/diagnostics`.
- **Mesin Deteksi Bahasa Indonesia & Performa**:
  - Modul `indonesian_nlp.py` (imbuhan, sinonim akademik, urutan klausa, dan pelindung *false-positive* istilah teknis).
  - Eksekusi kueri paralel lintas provider + 4 lapisan `TTLCache` + reuse koneksi HTTP.
- **Dokumentasi Phase 9**: [PHASE9_BROWSER_AUDIT.md](docs/research/PHASE9_BROWSER_AUDIT.md), [PHASE9_SEARCH_DESIGN.md](docs/PHASE9_SEARCH_DESIGN.md), [PHASE9_DETECTION_DESIGN.md](docs/PHASE9_DETECTION_DESIGN.md), [PHASE9_PERFORMANCE.md](docs/PHASE9_PERFORMANCE.md), [PHASE9_UI_QA.md](docs/PHASE9_UI_QA.md), [PHASE9_BENCHMARK.md](docs/PHASE9_BENCHMARK.md), dan [THIRD_PARTY_COMPONENTS.md](docs/THIRD_PARTY_COMPONENTS.md).

---

## Pembaruan Phase 10 — Rebuild UI/UX Lengkap & Deteksi Tulisan AI Lokal

- **Redesign Antarmuka Total (`shadcn/ui` + Tailwind CSS + `Lucide React` Only)**:
  - Penyeragaman desain *Swiss Modernism 2.0* across semua halaman (Light & Dark Mode, bilah samping 5 kelompok terstruktur tanpa navigasi ganda desktop, zero emoji ikon).
  - Penyederhanaan istilah Bahasa Indonesia teknis (*Indeks Kemiripan*, *Kata yang Cocok*, *Jumlah Kata yang Diperiksa*, *Hanya Informasi Referensi*) disertai **Ringkasan 5 Pertanyaan Utama** di atas laporan.
- **3 Mode Pemeriksaan Terpisah (`PLAGIARISM_ONLY`, `AI_ONLY`, `COMBINED`)**:
  - Pilihan mode eksplisit di halaman **Pemeriksaan Baru** (`/new-check`) sebelum mengunggah berkas; skor AI **tidak pernah** dicampur ke **Indeks Kemiripan Plagiasi**.
- **Engine Deteksi Tulisan AI Lokal (`backend/app/ai_detection/`)**:
  - Engine CPU luring bawaan `ng-id-stylo-lm-v1` (entropi n-gram karakter + *burstiness* + stilometri ID/EN) lengkap dengan analisis per paragraf, batas minimum 80 kata (`INSUFFICIENT_DATA`), manajemen model (`/models`), serta peringatan keterbatasan probabilistik.
- **Dokumentasi & Skill Phase 10**: [ai-writing-detection](.agents/skills/ai-writing-detection/SKILL.md), [UI_REDESIGN.md](docs/UI_REDESIGN.md), [AI_DETECTION_ARCHITECTURE.md](docs/AI_DETECTION_ARCHITECTURE.md), [AI_DETECTION_BENCHMARK.md](docs/AI_DETECTION_BENCHMARK.md), [AI_DETECTION_LIMITATIONS.md](docs/AI_DETECTION_LIMITATIONS.md), dan [PHASE10_QA_REPORT.md](docs/PHASE10_QA_REPORT.md).
