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

---

## Phase 10 — Complete UI/UX Rebuild & Local-First AI Writing Detection

### Ringkasan Perubahan
1. **Audit Repositori AI Detection & Agent Skill Baru**:
   - Mengaudit `eric-mitchell/detect-gpt` (MIT), `Croups/is-it-ai` (MIT), dan `ae-saouiqui/ai-text-detection` (tanpa file `LICENSE`) untuk kompatibilitas Windows CPU, kalibrasi, serta dukungan Bahasa Indonesia.
   - Mendokumentasikan panduan & standar kalibrasi pada [.agents/skills/ai-writing-detection/SKILL.md](.agents/skills/ai-writing-detection/SKILL.md).
2. **Engine Deteksi Tulisan AI Terkalibrasi (`backend/app/ai_detection/`)**:
   - Engine bawaan CPU-first `ng-id-stylo-lm-v1` (fitur *burstiness*, MATTR, penanda retorika LLM, jangkar konteks/sitasi, serta model entropi karakter 4-gram yang dilatih ketat pada `train` + *temperature scaling* pada `validation`).
   - API Manajemen Model (`/api/models`, `/verify`, `/activate`), migrasi Alembic `0003_phase10_ai_detection.py` (`checks.mode` & `checks.ai_report`), serta mode pemeriksaan `PLAGIARISM_ONLY`, `AI_ONLY`, dan `COMBINED` yang menjaga skor AI tetap terpisah dari `similarity_index`.
3. **Rebuild Total UI/UX (`shadcn/ui` + Tailwind CSS + `Lucide React` Only)**:
   - Seluruh 15 rute antarmuka dibangun seragam dalam gaya *Swiss Modernism 2.0*, bebas emoji, dilengkapi tooltip penjelasan istilah, 5 jawaban ringkas laporan, pemisahan visual ketat Laporan Plagiasi vs Laporan AI pada mode Gabungan, serta halaman baru `Deteksi Tulisan AI`, `Laporan Gabungan`, `Analitik AI`, dan `Manajemen Model`.
4. **Verifikasi Aktual Phase 10**:
   - Pytest lengkap: **36 passed, 1 skipped** (`test_live_internet_providers_explicit`).
   - Benchmark Plagiasi (12 skenario): **Precision `1,0000`**, **Recall `1,0000`**, **F1 `1,0000`**, **FPR `0,0000`**.
   - Benchmark AI ID+EN (`test` n=72): **ROC-AUC `0,9537`**, **F1 (`p>=0,68`) `0,8529`**, **`strict_ai_likely_fpr = 0,0`**, rata-rata **`1,17 ms`/dokumen**; seluruh 5 uji ketahanan *false positive* & batas `< 80` kata lulus.
   - Pemeriksaan emoji UI: **`0` temuan**; TypeScript & Vite `npm run build`: **exit 0**; Playwright UI QA 17 pengecekan (`1440×900`, `768×1024`, `390×844`, Light & Dark): **17/17 lulus (`0` overflow, `0` console error)** dengan bukti screenshot *before/after*.


---

## Phase 10.1 & 10.2 — Feature Activation Audit, Independent AI Validation, Local OCR & Web Search Completion

### Ringkasan Perubahan & Verifikasi Aktual
1. **Audit Aktivasi Fitur Phase 10.1**:
   - Mendokumentasikan status jujur 15 fitur pada [PHASE10_1_FEATURE_AUDIT.md](docs/PHASE10_1_FEATURE_AUDIT.md), [AI_DETECTION_STATUS.md](docs/AI_DETECTION_STATUS.md), dan [PHASE10_1_TEST_RESULTS.md](docs/PHASE10_1_TEST_RESULTS.md).
2. **Validasi Independen AI Detector (`ng-id-stylo-lm-v1`)**:
   - Membangun dataset evaluasi independen terpisah berdasarkan `document_id` dan `source_id` (`benchmark/data/ai_detection_v2/`: `100` artikel OA pra-2022 nyata dari DOAJ & Europe PMC termasuk `31` artikel Hukum & Studi Islam Indonesia + `48` dokumen independen multikategori + `4` guardrail teks pendek).
   - Audit kalibrasi pada `validation_v2` mengonfirmasi `T = 1.3` (NLL terendah `0.2303`) dan ambang konservatif `0.68`; pada held-out `test_v2` (`n = 87`): **Precision `1.0000`**, **Recall `0.7500`**, **F1 `0.8571`**, **FPR `0.0000`**, **ROC-AUC `0.9729`**, **ECE `0.0314`**, dengan **`0` false positive** pada seluruh artikel Hukum/Islam/Formal/Terjemahan.
   - Laporan AI (Web, PDF, HTML) ditingkatkan dengan ringkasan jumlah paragraf (`Total`, `Indikasi AI`, `Indikasi Manusia`, `Tidak Pasti / Singkat`), status kalibrasi, highlight per paragraf, serta penolakan HTTP `400` untuk `ai_model_id` yang belum terpasang.
3. **Penyelesaian Internet Search, Browser Crawler, & SearXNG**:
   - Menambahkan 4 sakelar kontrol pada `/new-check` (`Pencarian Jurnal`, `Pencarian Web Umum` default OFF, `Browser Crawler Terisolasi` default OFF, `Pengambilan Full-Text`) dengan status nyata dari `GET /api/providers`.
   - Memperbaiki [docker-compose.searxng.yml](docker-compose.searxng.yml) + menambahkan [searxng/settings.yml](searxng/settings.yml) (`formats: [html, json]`) dan memperbaiki pesan `NG_SEARXNG_URL` di `providers.py`.
   - Verifikasi live publik end-to-end (`benchmark/run_phase10_2_live_web_e2e.py`, `0` korpus lokal awal): mengunduh & mengindeks **5 PDF arXiv nyata**, memverifikasi sumber cocok #1 (`MATCH_VERIFIED`, **`SI = 63.64%`**, `63/99` kata) dalam `15.65 detik`.
4. **Tesseract OCR Lokal (`v5.4.0.20240606`, `ind+eng`)**:
   - Meningkatkan `backend/app/ingestion/ocr.py` (auto-discovery Windows + prapemrosesan pindaian blur/noise) dan menampilkan status OCR serta `extraction_confidence` di UI Pengaturan & Detail Laporan.
   - Lolos **5/5 skenario OCR nyata** (`run_phase10_2_ocr_eval.py`: Scan ID `94.3%`, Scan EN `92.6%`, Mixed `94.3%`, Low-Quality `94.4%`, Digital PDF `100%`, seluruhnya `word_recall = 1.0`).
5. **QA Regresi Penuh**:
   - `pytest`: **42 passed, 1 skipped, 0 failed** (`12.35s`); `LIVE_NETWORK_TESTS=true`: **1 passed** (`23.89s`); `npm run build`: **exit 0** (`6.61s`); Playwright UI QA: **17/17 lulus** (`0` error, `0` overflow).
   - Dokumentasi lengkap: [PHASE10_2_AI_VALIDATION.md](docs/PHASE10_2_AI_VALIDATION.md), [PHASE10_2_WEB_SEARCH.md](docs/PHASE10_2_WEB_SEARCH.md), [PHASE10_2_OCR_REPORT.md](docs/PHASE10_2_OCR_REPORT.md), dan [PHASE10_2_QA_REPORT.md](docs/PHASE10_2_QA_REPORT.md).
10. **Phase 10.3 — Academic Repository Reliability & OAI-PMH Harvesting Upgrade**:
   - Audit berbasis kode ([PHASE10_3_REPOSITORY_AUDIT.md](docs/PHASE10_3_REPOSITORY_AUDIT.md)) membuktikan 2 bug kritis HTTP 422 pada alur tambah repositori (`repo_type="OAI-PMH"`) dan panen (POST tanpa body), ditambah 6 kelemahan protokol, redirect, penanganan error, resumability, dan UI.
   - Migrasi Alembic `0004_phase10_3_oai_upgrade.py` memperluas `oai_repositories` secara *backward-compatible* dan menambah tabel `oai_harvest_records` serta `oai_harvest_logs`.
   - Upgrade `backend/app/sources/oai_pmh.py` & `backend/app/api/oai.py`: dukungan penuh DSpace 7, DSpace lama, OJS, EPrints, dan OAI-PMH umum; deteksi otomatis non-destruktif; redirect aman *hop-by-hop* dengan validasi SSRF; Wizard Uji Koneksi 8 tahap dengan solusi Bahasa Indonesia untuk seluruh error OAI-PMH (`badArgument`, `badVerb`, `badResumptionToken`, `cannotDisseminateFormat`, `noRecordsMatch`, `noSetHierarchy`, `noMetadataFormats`, `HTML_RESPONSE`, dll.); panen tahan gangguan dengan penyimpanan per halaman, pemulihan `badResumptionToken`, kontrol *Pause/Resume*, *Retry Failed*, dedup DOI/URL/hash, dan pemisahan ketat 7 tahap funnel (metadata vs full-text).
   - Desain ulang UI `RepositoriesPage.tsx`, komponen `OAIWizardView.tsx`, dan halaman baru `RepositoryDetailPage.tsx` (`/repositories/:repoId`).
   - Terverifikasi penuh: `56 passed, 1 skipped` pytest (14 fungsi uji baru mencakup 19 skenario Phase 10.3), panen live nyata ke `https://oaipmh.arxiv.org/oai` (`set=cs`: Wizard 8/8 `READY`, 3/3 PDF diunduh & diindeks lokal, uji plagiasi menghasilkan `85.89%` SI dengan `document_compared=1`), `npm run build` sukses, dan `18/18` Playwright UI QA lulus.
   - Dokumentasi lengkap: [PHASE10_3_REPOSITORY_AUDIT.md](docs/PHASE10_3_REPOSITORY_AUDIT.md), [PHASE10_3_REPOSITORY_TESTS.md](docs/PHASE10_3_REPOSITORY_TESTS.md), dan [PHASE10_3_QA_REPORT.md](docs/PHASE10_3_QA_REPORT.md).
11. **Phase 10.4 — Indonesian Academic Repository Expansion**:
   - Migrasi Alembic `0005_phase10_4_expansion.py` menambah tabel `oai_catalog` (katalog penemuan repositori dengan status awal wajib `UNVERIFIED` sebelum diuji) dan `oai_harvest_runs` (riwayat panen per sesi), serta kolom filter & jadwal opsional pada `oai_repositories`.
   - Penambahan modul katalog (`backend/app/sources/oai_catalog.py`), peningkatan penemuan tautan PDF OJS galley (`/article/view/{id}/{galley}` → `/download/`) & landing page DSpace/EPrints, filter tahun/kata kunci/jenis dokumen/`max_downloads`, penjadwalan opsional (`worker.py`), serta provenance penuh pada `Document` (`university`, `repository_name`, `authors`, `year`, `doi`, `url`, `license`, `retrieved_at`).
   - Upgrade UI: Tab **Katalog Repositori** di `RepositoriesPage.tsx`, serta **Penjelajah Koleksi & Filter**, **Dokumen Terindeks (Provenance)**, **Rekaman Gagal**, **Riwayat Sesi Panen**, dan kartu **Panen Terjadwal Opsional** di `RepositoryDetailPage.tsx`.
   - Terverifikasi penuh: `59 passed, 1 skipped` pytest (mock & integrasi terpisah dari live), validasi platform live nyata Indonesia (`OJS UNY` & `EPrints UIN Sunan Kalijaga` tervalidasi full-text hingga uji plagiasi `94.53%` & `94.44%`; `DSpace Lama IPB` metadata-only; `DSpace 7 Demo` protokol OK; `DSpace 7 STIKOM Yos Sudarso` timeout didokumentasikan jujur), `npm run build` sukses, dan `18/18` Playwright UI QA lulus (`24` screenshot).
   - Dokumentasi lengkap: [PHASE10_4_PLATFORM_VALIDATION.md](docs/PHASE10_4_PLATFORM_VALIDATION.md), [PHASE10_4_REPOSITORY_CATALOG.md](docs/PHASE10_4_REPOSITORY_CATALOG.md), [PHASE10_4_HARVEST_REPORT.md](docs/PHASE10_4_HARVEST_REPORT.md), dan [PHASE10_4_QA_REPORT.md](docs/PHASE10_4_QA_REPORT.md).
