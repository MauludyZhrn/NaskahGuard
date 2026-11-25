# NaskahGuard — Phase 10.1: Log Hasil Pengujian Terverifikasi

> Seluruh hasil di bawah berasal dari eksekusi perintah nyata pada **25 November 2026** di workspace `d:\Projects\NaskahGuard`.

---

## 1. Suite Pengujian Backend (`pytest`)

- **Perintah**: `& "d:\Projects\NaskahGuard\backend\.venv\Scripts\python.exe" -m pytest -v --tb=short`
- **Cakupan**: `41` kasus uji terdeteksi.
- **Hasil**: **`40 passed, 1 skipped, 0 failed`** (`8.22s`).
  - `tests/test_api_e2e.py`: `4 passed` (auth non-loopback, unggah PDF/DOCX/TXT, indeks kemiripan, ekspor PDF/HTML/JSON, hapus dokumen).
  - `tests/test_engine.py`: `3 passed` (Winnowing deterministik, Exact/Near-Exact, zero double counting, pengecualian).
  - `tests/test_ingestion.py`: `3 passed` (PDF offsets, DOCX/TXT extraction, dan `test_bibliography_heading_variants_excluded` untuk 7 variasi tajuk Bibliography/Bibliografi/Works Cited/Daftar Pustaka).
  - `tests/test_institutional_reports.py`: `3 passed` (`detect_integrity_flags` homoglyph vs teks Arab, palet sumber 12 warna, E2E laporan PDF/HTML teranotasi untuk PDF & TXT).
  - `tests/test_phase10_ai_detection.py`: `5 passed` (disjoint dataset splits, guard `<80` kata, false-positive guardrails, deteksi bahasa ID/EN, E2E mode `AI_ONLY` & `COMBINED` terpisah, model registry API).
  - `tests/test_phase7_discovery.py`: `6 passed` (SSRF, query generator, HTML/XML extractors, mock OpenAlex/Europe PMC/Web acquisition, OAI-PMH, Playwright isolated BrowserContext).
  - `tests/test_phase8_scoring_and_search.py`: `4 passed` (audit angka skor, multi-query, cache TTL, provider health telemetry).
  - `tests/test_phase9_upgrade.py`: `4 passed, 1 skipped` (`test_live_internet_providers_explicit` dilewati saat `LIVE_NETWORK_TESTS` tidak disetel).
  - `tests/test_providers.py`: `3 passed` (OpenAlex, Crossref, arXiv, PMC mock transport, Noplag SSRF guard).
  - `tests/test_validators.py`: `5 passed` (traversal guard, magic-bytes check, makro DOCX, batas ukuran).

### 1.1 Verifikasi Live Internet Providers (Opt-In)
- **Perintah**: `$env:LIVE_NETWORK_TESTS="true"; & "d:\Projects\NaskahGuard\backend\.venv\Scripts\python.exe" -m pytest tests/test_phase9_upgrade.py -k "test_live_internet_providers_explicit" -v`
- **Hasil**: **`1 passed, 4 deselected`** (`23.89s`). Mengonfirmasi penyedia akademik publik (`OpenAlex`, `CrossRef`, `Europe PMC`, `DOAJ`, `arXiv`) merespons kueri publik `"winnowing document fingerprinting"`.

---

## 2. Benchmark Mesin Similarity & AI Detection

### 2.1 Offline Ground-Truth Similarity Benchmark
- **Perintah**: `& "d:\Projects\NaskahGuard\backend\.venv\Scripts\python.exe" "d:\Projects\NaskahGuard\benchmark\run_phase9_detection_benchmark.py"`
- **Artefak**: [phase9_detection_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_detection_benchmark.json)
- **Hasil**: `12` skenario terkontrol (`TP=7, FP=0, TN=5, FN=0`), `Precision=1.0`, `Recall=1.0`, `F1=1.0`, `FPR=0.0`, `cross_source_zero_double_counting=true`, waktu proses `23.71 ms`.

### 2.2 AI Writing Detection Benchmark
- **Perintah**: `& "d:\Projects\NaskahGuard\backend\.venv\Scripts\python.exe" "d:\Projects\NaskahGuard\benchmark\run_phase10_ai_benchmark.py"`
- **Artefak**: [phase10_ai_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_ai_benchmark.json)
- **Hasil** (`n=72` test split kurasi internal):
  - Pada ambang `0.50`: `Precision=0.7692`, `Recall=0.8333`, `F1=0.8000`, `FPR=0.2500`, `ROC-AUC=0.9537`, `Brier=0.1023`, `ECE=0.1465`.
  - Pada ambang produk `0.68`: `Precision=0.9062`, `Recall=0.8056`, `F1=0.8529`, `FPR=0.0833`, `strict_ai_likely_false_positives=0`.
  - Waktu proses: `83.78 ms` (`1.16 ms/dokumen`).

---

## 3. Verifikasi Build Frontend & Playwright UI QA

### 3.1 Build Produksi TypeScript + Vite
- **Perintah**: `npm run build` (`tsc -b && vite build` di `d:\Projects\NaskahGuard\frontend`)
- **Hasil**: Exit code `0`, `2692 modules transformed`, selesai dalam `6.29s`.

### 3.2 Playwright E2E Layout & Visual QA
- **Perintah**: `& "d:\Projects\NaskahGuard\backend\.venv\Scripts\python.exe" "d:\Projects\NaskahGuard\benchmark\run_phase10_ui_qa.py"`
- **Artefak**: [phase10_ui_qa.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_ui_qa.json) & `docs/screenshots/phase10_after/` (`21` tangkapan layar)
- **Hasil**: `passed=true`, **`17/17` rute & viewport lulus** (`1440px`, `768px`, `390px`), `console_errors=[]`, `page_errors=[]`, `bad_http=[]`, `dark_mode_verified=true`, `horizontal_overflow=false` di seluruh rute.

### 3.3 Verifikasi Interaksi Accordion, Collapse Sidebar, & Tema
- **Skrip**: `verify_ui_interactions.py` pada server lokal terisolasi
- **Hasil**: `ACCORDION:false->true | BIB_VISIBLE:True | NAV_COLLAPSE:true->false | THEME:dark->light` (exit code `0`).

### 3.4 Audit Statis Ikon & Dependensi Opsional
- **Ikon UI**: `0` karakter emoji di `frontend/src/**/*.{ts,tsx,css}`; seluruh ikon berasal dari `lucide-react`.
- **Paket Python Opsional di `.venv`**: `playwright: True`, `torch: False`, `transformers: False`, `sentence_transformers: False`, `pytesseract: False`.
