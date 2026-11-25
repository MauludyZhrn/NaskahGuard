# NaskahGuard — Phase 10.2: Laporan QA & Regresi Menyeluruh

> **Tanggal Pengujian**: 25 November 2026  
> **Lingkungan**: Windows, Python `3.10.11`, SQLite WAL, PyMuPDF, Tesseract `v5.4.0.20240606` (`ind+eng`), Playwright Chromium, Node/Vite.

---

## 1. Ringkasan Eksekusi Pengujian

| Kategori Uji | Perintah / Skrip | Hasil Aktual | Artefak / Bukti |
|---|---|---|---|
| **Backend Regression Tests** | `backend\.venv\Scripts\python.exe -m pytest -v --tb=short` | **`42 passed, 1 skipped, 0 failed`** (`12.35s`) | Mencakup Phase 1–10.2, 5 skenario OCR lokal, Bibliography exclusions, laporan PDF/HTML/JSON, model guard `400`, dan Combined E2E. |
| **Live Internet Provider Tests** | `LIVE_NETWORK_TESTS=true pytest tests/test_phase9_upgrade.py -k test_live_internet_providers_explicit` | **`1 passed`** (`23.89s`) | Verifikasi respons langsung `OpenAlex`, `CrossRef`, `Europe PMC`, `DOAJ`, `arXiv`. |
| **Live Public-Source E2E Retrieval** | `benchmark\run_phase10_2_live_web_e2e.py` | **LULUS (`COMPLETED`, `15.65s`)** | `0` dokumen lokal awal -> `6` kueri -> `5` PDF publik diindeks -> **#1 arXiv `MATCH_VERIFIED`** (`63/99` kata, **`SI = 63.64%`**). [phase10_2_live_web_e2e.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_live_web_e2e.json) |
| **Independent AI Validation & Calibration** | `benchmark\run_phase10_2_ai_validation.py` | **LULUS (`152` dok, `0` leak)** | `100` artikel OA pra-2022 + `48` multikategori independen + `4` short guard. Held-out `test_v2` (`0.68`): `Precision=1.0`, `Recall=0.75`, `F1=0.8571`, `FPR=0.0`, `ROC-AUC=0.9729`, `ECE=0.0314`. [phase10_2_ai_validation.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_ai_validation.json) |
| **Local Tesseract OCR Evaluation** | `benchmark\run_phase10_2_ocr_eval.py` | **`5 / 5` skenario LULUS** | Scan ID (`94.3%`), Scan EN (`92.6%`), Mixed (`94.3%`), Low-quality noisy/blur (`94.4%`), Digital PDF regresi (`100%`), `word_recall = 1.0` seluruhnya. [phase10_2_ocr_eval.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_ocr_eval.json) |
| **Combined Examination & Export Tests** | `test_phase10_2_ocr_and_completion.py` & `test_institutional_reports.py` | **LULUS** | Plagiarism Engine & AI Engine berjalan independen pada 1 dokumen; skor tidak bercampur; PDF, HTML, JSON valid dengan ringkasan paragraf & highlight AI terpisah. |
| **Frontend Build (`tsc` + `vite`)** | `npm run build` (`frontend/`) | **Exit `0`** (`6.61s`) | `2692 modules transformed`, 0 TypeScript errors. |
| **Playwright Visual & Layout QA** | `benchmark\run_phase10_ui_qa.py` | **`passed=true` (`17/17` rute)** | `0` console error, `0` page error, `0` HTTP >= 500, `0` horizontal overflow (`1440px`, `768px`, `390px`), Dark Mode terverifikasi, `21` screenshot diperbarui di `docs/screenshots/phase10_after/`. |

---

## 2. Perubahan Status Fitur (Phase 10.1 → Phase 10.2)

| Fitur | Status Phase 10.1 | Status Phase 10.2 | Dasar Perubahan Status |
|---|---|---|---|
| **Full-text Extraction (termasuk OCR Lokal)** | `PARTIAL` | **`ACTIVE`** | Tesseract `v5.4.0` (`ind+eng`) terpasang lokal, auto-discovery Windows aktif, 5 skenario OCR (scan ID/EN, campuran, kualitas rendah, disable aman) lolos pengujian nyata. |
| **Browser Crawler & Kontrol Web Search** | `PARTIAL` | **`ACTIVE` (Jurnal & Crawler) / `NOT_CONFIGURED` (SearXNG lokal opsional)** | 4 sakelar kontrol eksplisit hadir di `/new-check` dengan status nyata `GET /api/providers`; `docker-compose.searxng.yml` + `searxng/settings.yml` diperbaiki; uji live publik E2E menemukan & mencocokkan PDF arXiv nyata (`63.64%`). |
| **AI Writing Detection** | `PARTIAL` | **`ACTIVE` (Model CPU Lokal Tervalidasi Independen; Adapter HF Tetap Opsional)** | Divalidasi pada 100 artikel OA pra-2022 (`0` FP pada Hukum/Islam/Formal/Terjemahan) + 48 sampel independen; `T=1.3` & `thr=0.68` diaudit di validation split; laporan AI ditingkatkan dengan ringkasan paragraf & highlight; model tak terpasang ditolak `400`. |
| **Combined Examination** | `ACTIVE` | **`ACTIVE`** | Diperkuat oleh pengujian E2E gabungan + verifikasi PDF/HTML/JSON terpisah. |
