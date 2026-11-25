# NaskahGuard — Phase 10.1: Feature Activation & UI Audit

> **Tanggal Audit**: 25 November 2026  
> **Lingkup**: Pemeriksaan menyeluruh kode sumber aktual (`backend/`, `frontend/`, `benchmark/`), pengujian otomatis (`pytest`), verifikasi penyedia internet langsung, dan QA antarmuka Playwright di Windows (`Python 3.10.11`).  
> **Prinsip Audit**: Tidak ada fitur yang ditandai `ACTIVE` tanpa bukti implementasi kode dan eksekusi uji yang diamati langsung.

---

## 1. Tabel Status Fitur End-to-End

| No | Fitur | Status | File Implementasi & API Endpoint | Fungsi Pipeline & Bukti Uji | Kesenjangan / Catatan Teknis |
|---|---|---|---|---|---|
| 1 | **Plagiarism Detection** | **ACTIVE** | `backend/app/engine/{exact,near_exact,lexical,indonesian_nlp,winnowing,minhash_lsh}.py`, `pipeline.py`; `POST /api/checks`, `GET /api/checks/{id}` | `run_check_pipeline` -> `find_exact_matches`, `find_near_exact_matches`, `find_lexical_matches`. Terbukti di `test_engine.py`, `test_api_e2e.py`, `test_phase8_scoring_and_search.py`, `test_phase9_upgrade.py` (**PASSED**), dan `run_phase9_detection_benchmark.py` (`12/12` skenario, `F1=1.0`). | Lapisan 4 Semantik (`semantic.py`) bersifat opsional dan berstatus `NOT_CONFIGURED` secara bawaan (`SEMANTIC_ENABLED=False`, `sentence-transformers` tidak terpasang). |
| 2 | **Internet Search** | **PARTIAL** | `backend/app/sources/{openalex,europe_pmc,crossref,arxiv,doaj,pmc,web_search,registry}.py`; `GET /api/providers`, `POST /api/providers/diagnostics` | `discover_external_sources` -> `_run_provider_queries_worker`. API akademik terbuka (`OpenAlex`, `CrossRef`, `Europe PMC`, `DOAJ`, `arXiv`) **ACTIVE** (lolos uji mock + uji live `test_live_internet_providers_explicit` `PASSED` dalam 23.89s). | Pencarian web umum (`SearXNGWebSearchProvider`, `OfficialWebSearchAPIProvider`) berstatus **`NOT_CONFIGURED`** (`NG_SEARXNG_URL` & `NG_WEB_SEARCH_API_URL` kosong di `config.py:62-64`), dan `NewCheckPage.tsx` belum memiliki sakelar UI untuk `enable_web_search`. |
| 3 | **Browser Crawler** | **PARTIAL** | `backend/app/sources/{crawler,browser_extractor,robots,ssrf}.py` | `IsolatedPlaywrightExtractor` & `fetch_public_url` (`_fetch_with_playwright` memakai Chromium ephemeral `storage_state=None`, blokir SSRF per route). Terbukti di `test_playwright_isolated_browser_context_available` & `phase9_crawler_benchmark.json` (`22` kategori URL sintetik, sukses `1.0`). | `enable_browser_crawler` bernilai `False` secara default (`schemas.py:25`, `NewCheckPage.tsx:78`) dan belum tersedia sakelar pengaktif di UI `Pemeriksaan Baru`. |
| 4 | **Full-text Extraction** | **PARTIAL** | `backend/app/ingestion/{pdf,docx_extractor,txt,html_extractor,xml_extractor,ocr,structure}.py` | `extract_pdf` (`pymupdf`), `extract_docx`, `extract_txt`, `extract_html_text_and_meta`, `annotate_structure`. Terbukti di `test_ingestion.py` (3/3 **PASSED** termasuk variasi tajuk Bibliography), `test_phase7_discovery.py`, `test_api_e2e.py`. | OCR dokumen pindaian (`ocr.py`) berstatus **`NOT_CONFIGURED`** (`pytesseract=False` di `.venv`); halaman pindaian memberi peringatan `OCR_UNAVAILABLE`. |
| 5 | **Source Indexing** | **ACTIVE** | `backend/app/ingestion/service.py`, `backend/app/sources/{oai_pmh,dedup}.py`; `POST /api/corpus`, `POST /api/oai/repositories/{id}/harvest` | `index_document_for_corpus` mengindeks token, segmen, dan sidik jari Winnowing ke SQLite. Terbukti di `test_api_e2e.py`, `test_phase7_discovery.py` (deduplikasi + panen OAI-PMH **PASSED**). | — |
| 6 | **Similarity Scoring** | **ACTIVE** | `backend/app/engine/{scoring,exclusions}.py`, `backend/app/ingestion/structure.py` | `build_exclusion_mask` + `compute_scores` (pencegahan hitung ganda lintas lapisan & lintas sumber, pengecualian Daftar Pustaka/Bibliography, Sitasi, Kutipan, Daftar Isi, Frasa Umum). Terbukti di `test_phase8_scoring_and_search.py` & `test_phase9_upgrade.py`. | — |
| 7 | **Source Attribution** | **ACTIVE** | `backend/app/engine/scoring.py`, `backend/app/models.py` (`CheckSource`, `Match`), `backend/app/reports/builder.py`; `GET /api/checks/{id}/sources/{sid}/viewer` | Menetapkan `rank`, kepemilikan token eksklusif tertinggi, `contribution_pct`, kategori sumber (`Publikasi`, `Internet`, `Korpus Lokal`), dan palet warna 12 sumber konsisten. Terbukti di `test_institutional_reports.py` (**PASSED**). | — |
| 8 | **PDF Report** | **ACTIVE** | `backend/app/reports/pdf_report.py`; `GET /api/checks/{id}/export.pdf` | `render_pdf_bytes` membangun Sampul, Ringkasan Integritas, Daftar Sumber Berwarna, Halaman AI Terpisah, lalu melapisi halaman asli PDF via PyMuPDF dengan sorotan transparan & pil bernomor di tepi kiri (`Halaman X dari Y`). Terbukti di `test_institutional_reports.py` + render PNG 6 halaman. | Untuk berkas non-PDF (DOCX/TXT) menggunakan penataan paragraf ReportLab berpenanda margin kiri. |
| 9 | **HTML Report** | **ACTIVE** | `backend/app/reports/html_report.py`, `templates/report.html`; `GET /api/checks/{id}/export.html` | `render_html_bytes` merender lembar multi-bagian Ivory Burgundy + `@media print` termasuk pil tepi kiri & laporan AI terpisah. Terbukti di `test_phase10_ai_detection.py` & `test_institutional_reports.py` (**PASSED**). | — |
| 10 | **JSON Export** | **ACTIVE** | `backend/app/reports/json_report.py`; `GET /api/checks/{id}/export.json` | `render_json_bytes` mengekspor struktur lengkap `build_full_report`. Terbukti di `test_api_e2e.py` (**PASSED**). | — |
| 11 | **Interactive Report** | **ACTIVE** | `frontend/src/pages/ReportDetailPage.tsx`; `GET /api/checks/{id}/report`, `/viewer`, `/sources/{sid}/viewer` | Menampilkan kartu Detail Dokumen, Ringkasan Integritas, Daftar Sumber Utama berwarna klik-ke-sumber, penampil `Naskah Berpenanda` dua kolom, grafik per bab, dan diagram alur 12 tahap. Diverifikasi oleh Playwright QA (`17/17` lulus). | — |
| 12 | **Integrity Flags** | **ACTIVE** | `backend/app/reports/integrity_flags.py`, `builder.py` | `detect_integrity_flags` mendeteksi substitusi huruf homoglyph Sirilik/Yunani di dalam kata Latin serta karakter lebar-nol (zero-width), tanpa salah menandai aksara Arab. Terbukti di `test_institutional_reports.py` (**PASSED**). | — |
| 13 | **AI Writing Detection** | **PARTIAL** | `backend/app/ai_detection/{detector,features,model_registry,dataset_builder}.py`, `backend/app/api/models_mgmt.py`; `POST /api/checks`, `GET /api/models` | Mesin lokal `ng-id-stylo-lm-v1` aktif end-to-end (unggah -> paragraf -> inferensi -> DB -> UI -> PDF/HTML/JSON). Detail lengkap pada `docs/AI_DETECTION_STATUS.md`. | Ditandai **PARTIAL** karena: (1) validasi Bahasa Indonesia & Inggris baru memakai korpus kurasi/sintetik internal, bukan dataset publik/nyata independen; (2) dua model opsional HuggingFace berstatus `DEPS_MISSING` (`torch`/`transformers` belum terpasang). |
| 14 | **Combined Examination** | **ACTIVE** | `backend/app/engine/pipeline.py:475-486`, `frontend/src/pages/ReportDetailPage.tsx:530-564` | Menjalankan Plagiarism Engine (tahap 1–11) secara penuh lalu `analyze_document_ai()` secara terpisah tanpa mencampurkan `similarity_index` dan `ai_likelihood_pct`. Terbukti di `test_phase10_ai_detection.py` (**PASSED**). | — |
| 15 | **Lucide React Icons** | **ACTIVE** | `frontend/src/components/` & `frontend/src/pages/*.tsx` | Seluruh 18 berkas TSX pengimpor ikon memakai `lucide-react` secara eksklusif; pemindaian otomatis menemukan `0` karakter emoji dan `0` pustaka ikon campuran (`heroicons`/`fontawesome`/`react-icons`). | — |

### Komponen Opsional Terkait Lainnya
| Komponen | Status | Lokasi & Keterangan |
|---|---|---|
| Semantic Layer 4 (`SentenceTransformer`) | `NOT_CONFIGURED` | `backend/app/engine/semantic.py`, `NG_SEMANTIC_ENABLED=False`, `sentence_transformers=False` di `.venv`. |
| Noplag External Engine Adapter | `NOT_CONFIGURED` | `backend/app/engine/noplag_adapter.py`, `NG_NOPLAG_ENGINE_URL=""`. |

---

## 2. Audit Antarmuka (UI/UX & Aksesibilitas)

Pemeriksaan dilakukan melalui inspeksi kode statis (`frontend/src/**`), build TypeScript (`tsc -b && vite build`), pengujian Playwright visual (`benchmark/run_phase10_ui_qa.py`), dan pengujian interaksi langsung (`verify_ui_interactions.py`):

| Kriteria Audit UI | Hasil | Bukti Pengamatan |
|---|---|---|
| **Ikon `lucide-react` tunggal (tanpa emoji)** | **LOLOS** | 18 berkas di `frontend/src` mengimpor dari `lucide-react`; `0` karakter emoji (`[\U0001F300-\U0001FAFF\u2600-\u27BF]`) ditemukan; tidak ada Heroicons/FontAwesome/react-icons. |
| **Konsistensi `shadcn/ui`** | **LOLOS** | 20 komponen dasar tersedia di `frontend/src/components/ui/` (`accordion`, `alert`, `alert-dialog`, `badge`, `button`, `card`, `collapsible`, `dialog`, `dropdown-menu`, `input`, `label`, `progress`, `select`, `separator`, `skeleton`, `switch`, `table`, `tabs`, `textarea`, `tooltip`) dan digunakan seragam pada seluruh 11 halaman. |
| **Penggunaan `Magic UI` selektif** | **LOLOS** | Hanya `BlurFade` (transisi masuk CSS ringan pada container halaman) dan `NumberTicker` (angka ringkasan pada Dasbor, Analitik, dan Detail Laporan) yang dipakai tanpa efek berlebihan. |
| **Penerapan `ui-ux-pro-max`** | **LOLOS** | Palet **Ivory Burgundy** (`#F8F5F0` / `#EDE6DD` / `#6E1F2F` / `#1B1416` / `#9A8F89`), tipografi editorial `Newsreader` + `Plus Jakarta Sans`, hierarki heading jelas, tidak ada kartu statistik berlebihan, responsif di `1440px`, `768px`, dan `390px` (`horizontal_overflow: false`). |
| **Bahasa Indonesia menyeluruh** | **LOLOS** | Seluruh label navigasi, formulir, status, tooltip, dan laporan berbahasa Indonesia. Catatan kecil: beberapa istilah teknis akademis umum seperti `DOI`, `URL`, `OAI-PMH`, `PDF/HTML/JSON`, dan kata bilingual `Bibliography` sengaja dipertahankan agar akrab bagi peneliti. |
| **Mode Terang & Mode Gelap** | **LOLOS** | Terverifikasi lewat tombol `"Ubah tema tampilan"` (`data-theme` berubah `dark` <-> `light`) serta tangkapan layar `17_dashboard_dark.png` & `20_dashboard_dark_collapsed.png`. |
| **Collapse Sidebar & Accordion** | **LOLOS** | Uji Playwright interaktif pada `/new-check` mencatat: Accordion `"Pengaturan Sumber & Pengecualian Plagiasi"` berubah `aria-expanded: false -> true` dan menampilkan sakelar `"Kecualikan Daftar Pustaka / Bibliography"` (`BIB_VISIBLE: True`); grup navigasi `"PEMERIKSAAN"` berubah `aria-expanded: true -> false`. |

---

## 3. Rekomendasi Perbaikan Berdasarkan Prioritas

### Prioritas Tinggi (P1)
1. **Validasi AI Detection pada Korpus Dunia Nyata Independen (Khususnya Bahasa Indonesia)**:
   - Kumpulkan dataset nyata lintas sumber (skripsi/jurnal manusia terpublikasi sebelum era LLM vs keluaran aktual LLM seperti GPT-4o, Claude, Gemini, Llama dalam Bahasa Indonesia & Inggris, termasuk naskah panjang 1.500–5.000 kata dan teks terjemahan manusia) untuk menggantikan benchmark kurasi internal di `dataset_builder.py`.
   - Perbaiki penurunan kepercayaan pada prose hukum/regulasi formal (`academic_formal_human`, akurasi `0.25` pada ambang `0.50` meski `0` false positive pada ambang produk `0.68`).
2. **Penanganan Eksplisit Pilihan Model di `analyze_document_ai()`**:
   - Saat ini di `backend/app/ai_detection/detector.py:300,337`, jika pengguna mengirimkan `ai_model_id` non-bawaan secara langsung via API, sistem diam-diam mengalihkan inferensi ke `ng-id-stylo-lm-v1`. Sebaiknya API menolak `model_id` yang belum terpasang dengan pesan `400` eksplisit atau mengembalikan metadata penanda fallback yang lebih tegas di UI laporan.

### Prioritas Sedang (P2)
3. **Sakelar UI untuk Browser Crawler & Pencarian Web Umum**:
   - Tambahkan kontrol opsional pada `NewCheckPage.tsx` (di dalam Accordion lanjutan) untuk `enable_browser_crawler` dan penjelasan kondisi `NG_SEARXNG_URL` / `NG_WEB_SEARCH_API_URL`, karena saat ini keduanya tersembunyi di `DEFAULT_SETTINGS`.
4. **Panduan Instalasi Paket Opsional (OCR & Transformer)**:
   - Sediakan skrip atau instruksi instalasi opsional `pytesseract` (+ Tesseract binary Windows) untuk PDF pindaian, serta `sentence-transformers` bila pengguna memerlukan Layer 4 Semantik.

### Prioritas Rendah (P3)
5. **Pengujian Teks Terjemahan & Dokumen Multi-Bab Panjang di Benchmark AI**:
   - Tambahkan skenario teks terjemahan manusia (`ID <-> EN`) dan dokumen multi-halaman penuh (> 2.000 kata) ke `benchmark/run_phase10_ai_benchmark.py`.
