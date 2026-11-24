# AGENT_REPORT — NaskahGuard

Laporan log pengembangan proyek **NaskahGuard** (Academic Plagiarism & Similarity Detection Intelligence System).

## Ringkasan Pelaksanaan per Fase

### Fase 0 — Riset, Audit Repositori, Skill, dan Dokumentasi (Selesai)
- Inisialisasi repositori Git di `d:\Projects\NaskahGuard`, penambahan `.gitignore` dan `LICENSE` (Apache-2.0).
- Audit 7 repositori referensi di `research/vendor/` (`noplag-engine`, `academicguard`, `awesome-academic-skills`, `mineru-skill`, `ai-skill-scholar`, `tufte-data-viz`, `ui-ux-pro-max-skill`) — terdokumentasi di [docs/research/REPO_AUDIT.md](docs/research/REPO_AUDIT.md).
- Instalasi 4 Agent Skills ke `.agents/skills/`: `mineru`, `scholar-search`, `tufte-data-viz`, `ui-ux-pro-max`.
- Pembuatan [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) serta 11 dokumen arsitektur/spesifikasi di `docs/` lengkap dengan diagram Mermaid (arsitektur, data flow, document processing, similarity detection, source discovery, scoring, dan ERD).

### Fase 1 — Fondasi Backend, DB, dan Ingesti Dokumen (Selesai)
- Konfigurasi Pydantic (`backend/app/config.py`) dengan `APP_NAME` yang dapat diubah melalui `NG_APP_NAME` dan `VITE_APP_NAME`.
- Skema database SQLAlchemy 2 + Alembic (`backend/alembic/versions/0001_initial.py`) mendukung SQLite WAL (default Windows siap pakai) dan PostgreSQL (`pg_trgm` GIN trigram + opsi `pgvector`).
- Pipeline ingesti (`backend/app/ingestion/`): validasi ekstensi/MIME/magic bytes/ukuran streaming, anti path-traversal, ekstraksi PDF (`PyMuPDF` + fallback `pypdf` non-AGPL), fallback OCR lokal opsional (`Tesseract`), `python-docx` (dengan estimasi pemisah halaman), TXT (`utf-8-sig`/`cp1252`), normalisasi Unicode tanpa mengubah teks asli, tokenisasi offset karakter eksak, segmentasi kalimat/paragraf, deteksi bahasa ID/EN/mixed, serta deteksi zona (`BODY`, `BIBLIOGRAPHY`, `TOC`, `COVER`) & bab.
- CLI (`backend/app/cli.py`: `import-corpus`, `purge-retention`), worker antrean latar belakang (`backend/app/worker.py`), retensi data, audit log, rate limiter, dan validasi keamanan startup.

### Fase 2 — Mesin Similarity Multi-Lapis & Scoring (Selesai)
- `backend/app/engine/`: hash 64-bit Blake2b (`hashing.py`), Winnowing `k=5, w=4` + DF stop-gram filtering (`winnowing.py`), MinHash `128` permutasi + LSH (`minhash_lsh.py`), Lapisan 1 Exact Matching (`exact.py`), Lapisan 2 Near-Exact seed-and-extend + `SequenceMatcher` konservatif (`near_exact.py`), Lapisan 3 Lexical TF-IDF `char_wb (3,5)` + BM25 (`lexical.py`), Lapisan 4 Semantic opsional (`semantic.py`), masker pengecualian (`exclusions.py`), atribusi eksklusif anti-hitung-ganda (`attribution.py`), perhitungan `SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%` (`scoring.py`), dan adapter loopback Noplag Engine (`noplag_adapter.py`).

### Fase 3 — Penemuan Sumber Terbuka (Selesai)
- `backend/app/sources/`: antarmuka `SourceProvider` (`base.py`), `LocalCorpusProvider`, `OpenAlexProvider`, `CrossrefProvider` (`METADATA_ONLY`), `ArxivProvider` (jeda >= 3 detik), `PubMedCentralProvider` (metadata E-utilities), serta pemeriksaan `robots.txt` (`robots.py`). Pencarian eksternal nonaktif secara default dan hanya mengirim judul + maksimal 10 frasa kunci TF-IDF.

### Fase 5 — Pelaporan Interaktif & Antarmuka Frontend (Selesai)
- Pelaporan backend (`backend/app/reports/`): JSON, HTML mandiri dengan grafik SVG, dan PDF menggunakan ReportLab (`pdf_report.py`) lengkap dengan identitas pemeriksaan, metodologi, grafik, daftar sumber, cuplikan, alur data aktual, dan pernyataan keterbatasan.
- Frontend React + TypeScript + Vite (`frontend/`) berbahasa Indonesia penuh (mode terang & gelap, responsif, prinsip Tufte & aksesibilitas): Dasbor, Pemeriksaan Baru, Riwayat Pemeriksaan, Pustaka Dokumen, Korpus Sumber, Laporan Kemiripan, Detail Laporan 6 tab (Ringkasan, Perbandingan Dokumen dua panel sinkron, Sumber, Analitik Recharts, Alur Pemeriksaan 12 tahap data aktual, Ekspor), dan Pengaturan.

### Fase 6 — Pengujian, Benchmark, & Verifikasi (Selesai)
- **Pytest (`backend/.venv/Scripts/python.exe -m pytest -v`)**: **23 passed** (mencakup seluruh 17 tes Fase 1–6 ditambah 6 tes Fase 7: SSRF guard, Intelligent Query Generator, HTML/XML extraction, OpenAlex + Europe PMC + SearXNG + Source Deduplication, OAI-PMH Harvester & Registry API, serta isolated Playwright Chromium context).
- Perbaikan pada `build_viewer_payload` (`backend/app/reports/builder.py`): memastikan segmen teks yang masuk masker pengecualian (seperti `BIBLIOGRAPHY`) selalu diprioritaskan tampil sebagai `EXCLUDED` pada viewer agar konsisten dengan perhitungan Adjusted SI.

### Fase 7 — Global Web & Academic Source Intelligence + OAI-PMH Harvester (Selesai)
- **Audit & Diagnosis**: Terdokumentasi pada [docs/research/PHASE7_DIAGNOSIS.md](docs/research/PHASE7_DIAGNOSIS.md).
- **Skema & Migrasi Alembic (`0002_phase7_discovery.py`)**: Penambahan kolom deduplikasi pada `documents` (`canonical_url`, `normalized_title`, `license`, `indexing_status`, `alternate_urls`), tabel `source_acquisitions`, dan tabel `oai_repositories`.
- **Intelligent Query Generator (`app/sources/query_generator.py`)**: Mengekstrak kueri frasa eksak, keyword TF-IDF, dan DOI secara progresif dari zona `BODY` saja (bebas daftar pustaka/frasa umum).
- **Provider & Akuisisi Full-Text**: Upgrade `OpenAlexProvider` (`locations` + OA + Content API), penambahan `EuropePMCProvider` (full-text JATS XML), pelestarian `PubMedCentralProvider` & `ArxivProvider` & `CrossrefProvider`, penambahan `SearXNGWebSearchProvider` & `OfficialWebSearchAPIProvider` (`app/sources/web_search.py`), SSRF defense-in-depth (`app/sources/ssrf.py`), Playwright Chromium crawler terisolasi + HTML boilerplate stripping (`app/sources/crawler.py`, `app/ingestion/html_extractor.py`, `app/ingestion/xml_extractor.py`), dan deduplikasi multi-sinyal (`app/sources/dedup.py`).
- **OAI-PMH Harvester (`app/sources/oai_pmh.py`, `app/api/oai.py`)**: Mendukung `Identify`, `ListMetadataFormats`, `ListSets`, `ListRecords` dengan `resumptionToken`, `GetRecord`, panen inkremental berbasis datestamp, serta indeksasi PDF publik ke korpus lokal.
- **Upgrade Frontend**: Pengaturan pencarian eksternal pada `NewCheckPage`, halaman baru `Monitor Penemuan` (`DiscoveryMonitorPage`), manajemen repositori OAI-PMH di `CorpusPage`, serta tab `Bukti Pencarian Internet` dan `Cakupan Pencarian` pada `ReportDetailPage`.
- **Evaluasi Phase 7 (`benchmark/run_phase7_eval.py`)**: `fulltext_acquisition_success_rate=1.0`, `similarity_index=78.67%`, `sources_matched=2`.
- **Benchmark 12 Kasus Sintetis (`backend/.venv/Scripts/python.exe benchmark/run_benchmark.py`)**:
  - `EXACT`: Precision = **1.0000**, Recall = **1.0000**, F1 = **1.0000**, FPR = **0.0000**, FNR = **0.0000**.
  - `NEAR_EXACT` (gabungan): Precision = **0.9805**, Recall = **0.9934**, F1 = **0.9869**, FPR = **0.0333**, FNR = **0.0066**.
  - `LEXICAL`: Precision = **1.0000**, Recall = **1.0000**, F1 = **1.0000**, FPR = **0.0000**, FNR = **0.0000**.
  - Rincian tersimpan di `benchmark/results/latest.json` dan [docs/TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md).
- **Smoke Test (`backend/.venv/Scripts/python.exe scripts/smoke_test.py`)**: Lulus (`Report=NG-20261124-0001 SI=31.31% MatchedWords=31/99 PDFBytes=6362`).
- **Live Server Probe**: `uvicorn app.main:app --host 127.0.0.1 --port 8019` mengembalikan HTTP 200 JSON valid pada `/api/health`.
- **Frontend Build (`tsc --noEmit` & `npm run build`)**: Lulus tanpa error.

## Keterbatasan Lingkungan & Implementasi Saat Ini
1. **PostgreSQL, Tesseract, dan Docker tidak terpasang** di mesin host; seluruh eksekusi dan verifikasi berjalan di atas SQLite (mode WAL). Skema PostgreSQL (`pg_trgm` GIN) telah disiapkan pada migrasi Alembic tetapi belum diuji terhadap server PostgreSQL hidup.
2. **Noplag Engine** diaudit sebagai referensi arsitektur dan disediakan adapter HTTP khusus loopback (`app/engine/noplag_adapter.py`), namun tidak dijalankan secara langsung karena membutuhkan PostgreSQL + Python 3.12+.
3. **OCR & Modul Semantik** tidak diaktifkan secara default karena membutuhkan biner Tesseract dan paket berat `sentence-transformers` (`backend/requirements-optional.txt`); sistem melaporkan status ketersediaan secara jujur di API, UI, dan PDF.
4. **Adapter PubMed Central (PMC)** saat ini menyediakan pencarian metadata E-utilities (`METADATA_ONLY`); pengambilan arsip penuh XML/PDF OA subset PMC belum diimplementasikan.
5. **Nomor Halaman DOCX** diestimasi berdasarkan pemisah halaman eksplisit OOXML karena DOCX tidak menyimpan tata letak halaman tetap.
6. **Lisensi PyMuPDF (AGPL-3.0)** didokumentasikan pada [docs/THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md) dan dapat dialihkan ke `NG_PDF_BACKEND=pypdf` (BSD-3-Clause).

## Langkah Selanjutnya yang Disarankan
1. Uji migrasi dan performa indeks GIN `pg_trgm` serta `bigint[]` pada instance PostgreSQL 15+.
2. Pasang Tesseract OCR (`ind+eng`) dan `sentence-transformers` bila membutuhkan pemindaian PDF gambar dan pencarian kandidat semantik Lapisan 4.
3. Lakukan evaluasi lanjutan pada korpus publik beranotasi besar seperti PAN-PC-11 atau repositori ilmiah lokal kampus.


---

## Phase 8 — Product Refinement, UI/UX Redesign & Search Intelligence Optimization

### Ringkasan Perubahan
1. **UI/UX Redesign (`ui-ux-pro-max`)**:
   - Design token terpusat di `frontend/src/styles/tokens.css` & `frontend/src/styles/theme.css` (Primary `#1E3A5F`, Secondary `#334155`, Accent `#B45309`, Light `#F8FAFC`, Dark `#0F172A`/`#1E293B`).
   - Collapsible Sidebar (`260px`/`72px`, persistensi `localStorage`, tooltip, grup navigasi independen, mobile drawer + backdrop) di `Layout.tsx`.
   - Redesign `DashboardPage`, `NewCheckPage` (4 bagian + profil `QUICK/BALANCED/DEEP` + badge ketersediaan provider + accordion Pengaturan Lanjutan), `ReportDetailPage` (8-tab 1 baris + mobile select, accordion "Bagaimana skor dihitung?", 9 metrik sumber terpisah, Expand/Collapse All, `formatDuration`), dan `DiscoveryMonitorPage` (tabel kesehatan provider).
   - Halaman baru `RepositoriesPage` (`/repositories`) dan `AnalyticsOverviewPage` (`/analytics`).
2. **Search Intelligence & Backend Transparency**:
   - `backend/app/sources/query_generator.py`: profil `QUICK`/`BALANCED`/`DEEP` dengan distribusi *round-robin* lintas bab.
   - `backend/app/sources/ranking.py` & `backend/app/sources/cache.py`: peringkat relevansi kandidat & TTL cache URL/DOI.
   - `backend/app/sources/registry.py`: konkurensi crawl terbatas (`ThreadPoolExecutor(max_workers=4)`) & `stage_timings_ms`.
   - `backend/app/engine/scoring.py` & `pipeline.py`: `score_explanation` transparan & 9 metrik `source_metrics`.
   - `backend/app/api/providers.py` & `dashboard.py`: telemetri kesehatan provider nyata & data tren dasbor.
   - Opsional: `docker-compose.searxng.yml`.
3. **Verifikasi & QA**:
   - Backend pytest: **27/27 passed** (`5.64s`), termasuk `test_phase8_scoring_and_search.py`.
   - Frontend `tsc --noEmit` & `npm run build`: **exit 0**.
   - Phase 8 Search Benchmark (`benchmark/run_phase8_search_benchmark.py`): `P@5 = 0.80`, `R@5 = 1.00`, `0` kebocoran daftar pustaka, `23.64 ms` (mode deterministik offline; live internet dipisahkan secara eksplisit).
   - Automated Playwright UI QA (`scripts/qa_ui_playwright.py`): **0** horizontal overflow pada `1280×800` & `768×1024`, **0** console/page error, sidebar `260px -> 72px` tersimpan setelah reload, accordion rumus tampil, Dark Mode aktif.


---

## Phase 9 — Advanced Design System, Browser Intelligence & Detection Engine Upgrade

### Ringkasan Implementasi & Hasil Verifikasi
1. **Agent Skills (`.agents/skills/`)**:
   - Berhasil menginstal dan menerapkan `shadcn`, `magic-ui`, dan `scrapling-official` berdampingan dengan `ui-ux-pro-max`, `mineru`, `scholar-search`, dan `tufte-data-viz`.
2. **Design System Modernization & Perbaikan Halaman Laporan**:
   - Integrasi non-destruktif Tailwind CSS (`preflight: false` + pemetaan variabel HSL Light/Dark), `components.json`, 17 komponen `shadcn/ui`, serta 2 komponen motion selektif `Magic UI` (`NumberTicker`, `BlurFade`) dengan dukungan penuh `prefers-reduced-motion`.
   - **Perbaikan 6 Poin Laporan**: (1) Menghilangkan navigasi ganda desktop di seluruh 5 viewport (`1600px`, `1440px`, `1280px`, `768px`, `390px`), (2) Tata letak ringkasan skor proporsional, (3) Accordion *"Penjelasan Perhitungan Similarity"* lengkap dengan nilai presisi sebelum pembulatan & catatan selisih pembulatan `0,01%` (`408 / 5.973`), (4) 9 metrik transparansi sumber terpisah, (5) Expand/Collapse All dengan persistensi `localStorage`, (6) Paginasi tabel kecocokan, dialog detail sumber, & *sticky viewer toolbar*.
3. **Browser Intelligence, Provider DOAJ & Verifikasi Live Internet**:
   - `IsolatedPlaywrightExtractor` (`extract()` & `health_check()`) dengan follow otomatis `citation_pdf_url` OA; diadu secara empiris pada 22 URL terhadap `Crawl4AI` dan `Scrapling` (`100%` keberhasilan ekstraksi, `100%` penghapusan boilerplate, rata-rata `35,05 ms`).
   - Penambahan `DOAJProvider` (`doaj.py`), perbaikan bug live `CrossrefProvider` (`date-parts: [[None]]`), dan endpoint diagnostik live `POST /api/providers/diagnostics`.
   - **Verifikasi Live Internet Nyata**: `OpenAlex`, `Crossref`, `Europe PMC`, `DOAJ`, dan `arXiv` seluruhnya terverifikasi `OK`, serta pemeriksaan live end-to-end berhasil mengunduh dan mengindeks **3 artikel full-text OA nyata** ke SQLite dalam **53,5 detik** (`SearXNG` & `Official Web API` dilaporkan jujur sebagai `NOT_CONFIGURED`).
4. **Morfologi Bahasa Indonesia, Audit Skor & Regresi Penuh**:
   - `indonesian_nlp.py` meningkatkan deteksi parafrasa Bahasa Indonesia sekaligus menjaga `FPR = 0,00` pada jargon teknis (`F1 = 1,00` pada 12 skenario ground-truth).
   - Pytest regresi offline: **31 passed, 1 skipped (`LIVE_NETWORK_TESTS`)**; Pytest live (`LIVE_NETWORK_TESTS=true`): **5 passed**; Frontend `tsc` + `vite build`: **exit 0**; Playwright UI QA 5 viewport: **exit 0** dengan 7 tangkapan layar di `docs/screenshots/phase9/`.
