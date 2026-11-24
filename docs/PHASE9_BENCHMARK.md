# Laporan Benchmark Komprehensif Phase 9 (Crawler, Deteksi & Live Internet)

Dokumen ini memisahkan secara tegas hasil **Benchmark Offline Terkontrol**, **Mock Integration Test**, dan **Verifikasi Live Internet Nyata** sehingga setiap klaim dapat diaudit secara independen.

---

## 1. Benchmark Tiga Arsitektur Browser/Crawler (22 URL Akademik Legal)

- **Skrip**: [run_phase9_crawler_benchmark.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase9_crawler_benchmark.py)
- **Data Hasil**: [phase9_crawler_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_crawler_benchmark.json)
- **Variasi Dataset (22 URL)**: 4 Static HTML, 4 JS-Rendered SPA, 3 Open-Access Journal, 3 OJS, 2 DSpace, 2 EPrints, 2 XML JATS, 2 Public PDF.

| Metrik | `playwright_naskahguard` (`IsolatedPlaywrightExtractor`) | `crawl4ai_local` (`AsyncWebCrawler` 0.9.6) | `scrapling_standard_http` (`Fetcher` 0.5.1, non-stealth) |
| :--- | :---: | :---: | :---: |
| **Keberhasilan Ekstraksi** | **100,0%** (22/22) | 90,91% (20/22 — gagal PDF) | 90,91% (20/22 — gagal PDF) |
| **Presisi Konten Utama** | **82,74%** | 43,51% | 39,02% |
| **Penghapusan Boilerplate** | **100,0%** | 18,18% | 18,18% |
| **Kelengkapan Teks (Recall)** | **96,21%** | 90,91% | 74,24% (tidak merender JS) |
| **Akurasi URL Kanonis** | **100,0%** | 18,18% | **100,0%** |
| **Akurasi Metadata (Judul/DOI)** | **88,64%** | 45,45% | 86,36% |
| **Rata-rata Latensi / URL** | **35,05 ms** | 2.939,73 ms | **11,66 ms** |
| **Total Waktu (22 URL)** | **2.589,87 ms** | 65.556,69 ms | **261,10 ms** |
| **Delta Memori RSS** | 29,94 MB | 5,41 MB | **0,84 MB** |

**Kesimpulan Pemilihan Engine**: `IsolatedPlaywrightExtractor` dipertahankan sebagai engine produksi tunggal karena menggabungkan kecepatan HTTP streaming pada halaman statis/XML/PDF dengan ketepatan rendering Chromium terisolasi pada halaman JS serta menjaga `backend/requirements.txt` tetap ramping.

---

## 2. Benchmark Deteksi Kemiripan Akademik (12 Skenario Ground-Truth)

- **Skrip**: [run_phase9_detection_benchmark.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase9_detection_benchmark.py)
- **Data Hasil**: [phase9_detection_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_detection_benchmark.json)
- **Skenario**: Salinan identik, suntingan hampir identik, parafrasa Bahasa Indonesia (imbuhan + sinonim), pemindahan urutan paragraf, kutipan langsung (dikecualikan), daftar pustaka (dikecualikan), teks akademik Indonesia, teks akademik Inggris, duplikasi lintas sumber, teks tidak berhubungan berjargon teknis sama, sumber metadata-only, dan sumber dibatasi akses.

| Metrik Evaluasi | Nilai Aktual |
| :--- | :---: |
| **Precision** | **`1,0000`** (`TP = 7, FP = 0`) |
| **Recall** | **`1,0000`** (`TP = 7, FN = 0`) |
| **F1-Score** | **`1,0000`** |
| **False Positive Rate (FPR)** | **`0,0000`** (`TN = 5, FP = 0`) |
| **False Negative Rate (FNR)** | **`0,0000`** |
| **Retrieval Precision@5** | **`0,8000`** |
| **Retrieval Recall@5** | **`1,0000`** |
| **Zero Double-Counting Lintas Sumber** | **`true`** |
| **Waktu Eksekusi 12 Skenario** | **`26,23 ms`** |

> **Catatan Kejujuran**: Benchmark ini mengukur ketepatan algoritma open-source NaskahGuard pada korpus uji ground-truth terkontrol, dan **tidak** mengklaim kesetaraan cakupan database tertutup Turnitin.

---

## 3. Verifikasi Live Internet Provider & End-to-End Discovery Nyata

- **Skrip**: [run_phase9_live_verification.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase9_live_verification.py) & `LIVE_NETWORK_TESTS=true pytest` ([test_phase9_upgrade.py](file:///d:/Projects/NaskahGuard/backend/tests/test_phase9_upgrade.py))
- **Data Hasil**: [phase9_live_verification.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_live_verification.json)
- **Kueri Uji Publik (Non-Privat)**: `"winnowing document fingerprinting"`

### A. Status Konektivitas Live Provider (`2026-11-24T21:26:51Z`)
| Provider / Komponen | Configured | Reachable (Live) | Kandidat | URL Ditemukan | Latensi Live | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **OpenAlex** | `true` | **`true`** | 5 | 10 | `1.754 ms` | `OK` |
| **Crossref** | `true` | **`true`** | 5 | 5 | `1.169 ms` | `OK` *(setelah perbaikan `date-parts: [[None]]`)* |
| **Europe PMC** | `true` | **`true`** | 5 | 24 | `1.069 ms` | `OK` |
| **DOAJ** | `true` | **`true`** | 5 | 5 | `452 ms` | `OK` |
| **arXiv** | `true` | **`true`** | 5 | 10 | `255 ms` | `OK` |
| **Playwright Isolated Browser** | `true` | **`true`** | - | - | `2.803 ms` | `OK` (`isolated_context: true`) |
| **SearXNG Self-Hosted** | `false` | `false` | 0 | 0 | - | **`NOT_CONFIGURED`** (Docker tidak aktif di host ini) |
| **Official Web Search API** | `false` | `false` | 0 | 0 | - | **`NOT_CONFIGURED`** (Tanpa kredensial API) |

### B. Pemeriksaan End-to-End Live Internet
- **Status Job**: `COMPLETED`
- **Kueri Dieksekusi**: `15` kueri (terdistribusi ke 5 provider akademik aktif secara paralel)
- **Respons Provider**: `32` kandidat, **`58` URL unik** ditemukan
- **Full-Text Berhasil Diunduh & Diindeks ke SQLite**: **`3` artikel ilmiah Open Access nyata** (`29` tercatat transparan sebagai `metadata_only`)
- **Total Durasi End-to-End**: **`53,52 detik`** (`query_generation: 1 ms`, `provider_search: 46.165 ms`, `crawling_and_download: 3.846 ms`, `extraction_and_indexing: 3.051 ms`).
