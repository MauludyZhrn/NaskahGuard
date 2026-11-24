# Strategi Pengujian & Evaluasi Benchmark — NaskahGuard

## 1. Pengujian Unit & Integrasi (`pytest`)
Seluruh pengujian dijalankan secara offline (tanpa akses jaringan) menggunakan `backend/.venv/Scripts/python -m pytest -q`:
- **Validasi & Keamanan**: Penolakan ekstensi tidak valid, magic bytes palsu, berkas biner disamarkan sebagai TXT, batas ukuran unggahan, sanitasi nama file & pencegahan path traversal, autentikasi token, dan penolakan startup non-loopback tanpa `API_TOKEN`.
- **Ingesti & Offset**: Ekstraksi PDF (fixture dibuat programatik via PyMuPDF), DOCX (`python-docx`), dan TXT; verifikasi invarian `original_text[char_start:char_end]` cocok persis dengan token aslinya; pelestarian teks asli; deteksi zona (`BIBLIOGRAPHY`, `TOC`, `COVER`, `BODY`).
- **Mesin Similarity**: Determinisme Winnowing, pencocokan Exact 100% pada dokumen identik, akurasi Exact pada potongan kalimat, deteksi Near-Exact pada substitusi/penghapusan ringan, deduplikasi overlap dua sumber (invarian: jumlah kontribusi == Adjusted SI), efek pengecualian pada Adjusted SI vs Raw SI, filter frasa umum, dan status keterbatasan cakupan saat korpus kosong.
- **Adapter Sumber Eksternal (Mock)**: Pengujian `OpenAlex`, `Crossref`, `arXiv`, dan `PMC` melalui `httpx.MockTransport` termasuk pelaporan `METADATA_ONLY`, penolakan `ACCESS_DENIED`, dan pencatatan `provider_queries`.
- **End-to-End API**: Siklus lengkap via FastAPI `TestClient` (unggah korpus -> unggah submission -> jalankan pemeriksaan -> tunggu `COMPLETED` -> cek laporan & viewer -> ekspor PDF berheader `%PDF-`, HTML, JSON -> `DELETE` menghapus seluruh turunan).

## 2. Benchmark Evaluasi 12 Kasus Sintetis (`benchmark/run_benchmark.py`)
Benchmark menghasilkan 12 skenario ber-ground-truth tingkat token dalam Bahasa Indonesia dan Inggris:
1. Dua dokumen identik (*Exact*).
2. Dokumen dengan beberapa kalimat salinan persis (*Exact*).
3. Dokumen dengan susunan kata sedikit berubah / substitusi ringan (*Near-Exact*).
4. Paragraf dengan penggantian sinonim (*Lexical / Near-Exact*).
5. Paragraf dengan kesamaan makna / parafrase (*Semantic / Lexical*).
6. Kutipan langsung dengan sitasi benar (*Exclusion verification*).
7. Daftar pustaka yang sama (*Bibliography exclusion*).
8. Frasa akademik umum di banyak dokumen (*Stop-gram & common phrase filter*).
9. Dua sumber dengan rentang kecocokan saling tumpang tindih (*Overlap attribution*).
10. Dokumen dengan simulasi hasil OCR buruk / noise karakter (*Degraded OCR resilience*).
11. Dokumen tanpa sumber pembanding (*Coverage honesty*).
12. Dokumen multibahasa ID-EN (*Multilingual handling*).

Metrik yang diukur secara nyata: **Precision**, **Recall**, **F1-Score**, **False Positive Rate (FPR)**, **False Negative Rate (FNR)** per lapisan (`EXACT`, `NEAR_EXACT`, `LEXICAL`), waktu pemrosesan (ms), dan memori puncak (`tracemalloc`).

> **Catatan Kejujuran:** Angka di bawah merupakan hasil eksekusi aktual `backend/.venv/Scripts/python.exe benchmark/run_benchmark.py` terhadap 12 kasus sintetis (`benchmark/results/latest.json`), bukan klaim generalisasi pada korpus eksternal seperti PAN-PC-11. Modul semantik (`L4`) tidak aktif pada run default ini.

### Ringkasan Metrik per Lapisan (12 Kasus Sintetis)

| Lapisan | Precision | Recall | F1-Score | FPR | FNR |
|---|---:|---:|---:|---:|---:|
| `EXACT` | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| `NEAR_EXACT` (gabungan `EXACT` + `NEAR_EXACT`) | 0.9805 | 0.9934 | 0.9869 | 0.0333 | 0.0066 |
| `LEXICAL` | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| `SEMANTIC` | - | - | - | - | - |

### Rincian per Kasus Uji

| # | Kasus Uji | Adjusted SI | Raw SI | Waktu (ms) | Memori Puncak (KB) |
|---:|---|---:|---:|---:|---:|
| 1 | Dua dokumen identik | 100.00% | 100.00% | 85.74 | 767.6 |
| 2 | Beberapa kalimat sama | 37.31% | 37.31% | 123.46 | 602.0 |
| 3 | Modifikasi kata ringan (Near-Exact) | 81.82% | 81.82% | 114.93 | 452.2 |
| 4 | Paragraf dengan sinonim (Lexical) | 0.00% | 0.00% | 115.83 | 434.0 |
| 5 | Kesamaan makna / parafrase berat | 0.00% | 0.00% | 130.63 | 434.1 |
| 6 | Kutipan langsung dengan sitasi | 0.00% | 48.08% | 134.19 | 495.0 |
| 7 | Daftar pustaka yang sama | 0.00% | 55.32% | 116.13 | 525.8 |
| 8 | Frasa umum akademik | 0.00% | 0.00% | 142.33 | 561.4 |
| 9 | Dua sumber overlap | 54.35% | 54.35% | 126.50 | 547.8 |
| 10 | Simulasi hasil OCR buruk | 85.71% | 85.71% | 113.25 | 429.5 |
| 11 | Tanpa sumber pembanding | 0.00% | 0.00% | 97.74 | 315.2 |
| 12 | Dokumen multibahasa (ID + EN) | 43.24% | 43.24% | 212.11 | 507.0 |

## 3. Evaluasi Phase 7 (`benchmark/run_phase7_eval.py`)
Pengujian terpisah (`benchmark/results/phase7_eval.json`) mengukur tahap pencarian, akuisisi PDF/HTML terbuka, penolakan akses/metadata-only, dan pencocokan akhir:
- **Search Retrieval**: `queries_executed=1`, `candidate_records=4`, `source_retrieval_precision=0.5000`, `search_and_acquisition_latency_ms=58.25 ms`.
- **Crawling & Extraction**: `fulltext_indexed=2` (1 PDF + 1 HTML), `fulltext_acquisition_success_rate=1.0000`, `metadata_only_count=2`, `access_denied_count=0`.
- **Similarity Matching**: `similarity_index=78.67%` (`exact=66.67%`, `near_exact=12.00%`), `sources_matched=2`, `total_matches=4`, `matching_processing_time_ms=65.02 ms`.


---

## Pembaruan Phase 8 — Pengujian Skor, Benchmark & Playwright UI QA

1. **Unit & Integration Test Phase 8** (`backend/tests/test_phase8_scoring_and_search.py`):
   - Memverifikasi perhitungan skor deterministik (termasuk skenario `57 / 6.227` kata eligible, pencegahan penghitungan ganda overlap Exact/Near-Exact, dan pengaruh pengecualian).
   - Memverifikasi profil kueri `QUICK`/`BALANCED`/`DEEP` dan distribusi bab.
   - Memverifikasi peringkat relevansi, TTL cache, dan endpoint telemetri `/api/providers`.
2. **Search Benchmark Deterministik** (`benchmark/run_phase8_search_benchmark.py`):
   - Menghasilkan `benchmark/results/phase8_search_benchmark.json` dengan pemisahan eksplisit antara mode offline deterministik dan status live provider.
3. **Automated Playwright UI/UX QA** (`scripts/qa_ui_playwright.py`):
   - Memverifikasi desktop (`1280×800`) dan tablet (`768×1024`), zero horizontal overflow, persistensi collapsible sidebar (`260px`/`72px`), accordion rumus skor, Dark Mode, serta zero console/page errors.


---

## Pembaruan Strategi Pengujian Phase 9

1. **Mode Pengujian Jaringan Live Eksplisit (`LIVE_NETWORK_TESTS=true`)**:
   - Pengujian unit/mock reguler tetap berjalan 100% deterministik secara offline (`31 passed`).
   - Pengujian konektivitas internet nyata dipisahkan secara eksplisit melalui variabel lingkungan `LIVE_NETWORK_TESTS=true` pada `backend/tests/test_phase9_upgrade.py` serta skrip `benchmark/run_phase9_live_verification.py`.
2. **Benchmark 3 Crawler (22 URL) & Benchmark Deteksi (12 Skenario)**:
   - `benchmark/run_phase9_crawler_benchmark.py` membandingkan `IsolatedPlaywrightExtractor`, `Crawl4AI`, dan `Scrapling`.
   - `benchmark/run_phase9_detection_benchmark.py` menguji 12 skenario ground-truth akademik.
3. **Playwright UI QA 5 Viewport + Tangkapan Layar**:
   - `scripts/qa_ui_playwright.py` memverifikasi `1600×900`, `1440×900`, `1280×800`, `768×1024`, dan `390×844` serta menyimpan tangkapan layar ke `docs/screenshots/phase9/`.
