# Audit Browser Crawler, Ekstraksi Konten & Arsitektur Phase 9

Dokumen ini merupakan hasil audit teknis pada **STEP 1 Phase 9** terhadap modul akuisisi web, keamanan jaringan, ekstraksi dokumen, serta integrasi pipeline NaskahGuard sebelum melakukan pemilihan/benchmark engine browser baru.

## 1. Cakupan Modul yang Diaudit

- [crawler.py](file:///d:/Projects/NaskahGuard/backend/app/sources/crawler.py) — Akuisisi HTTP streaming + fallback Playwright Chromium terisolasi.
- [ssrf.py](file:///d:/Projects/NaskahGuard/backend/app/sources/ssrf.py) — Validasi SSRF, resolusi DNS, validasi redirect per hop, dan kanonisasi URL.
- [web_search.py](file:///d:/Projects/NaskahGuard/backend/app/sources/web_search.py) — SearXNG self-hosted & Official JSON Web Search API.
- [registry.py](file:///d:/Projects/NaskahGuard/backend/app/sources/registry.py) — Orkestrator pencarian progresif, peringkat relevansi, TTL cache, dan pengunduhan konkuren.
- [html_extractor.py](file:///d:/Projects/NaskahGuard/backend/app/ingestion/html_extractor.py) & [xml_extractor.py](file:///d:/Projects/NaskahGuard/backend/app/ingestion/xml_extractor.py) — Pembersihan boilerplate HTML & ekstraksi JATS/TEI XML.
- [pipeline.py](file:///d:/Projects/NaskahGuard/backend/app/engine/pipeline.py) & [worker.py](file:///d:/Projects/NaskahGuard/backend/app/worker.py) — Eksekusi job pemeriksaan asinkron di background worker.

---

## 2. Temuan Audit pada 13 Aspek Kritis

| Aspek | Kondisi Existing (Phase 8) | Kelemahan / Bottleneck yang Ditemukan | Rencana Peningkatan Phase 9 |
| :--- | :--- | :--- | :--- |
| **1. Browser Launch Reliability** | `_fetch_with_playwright` memanggil `sync_playwright().start()` + `chromium.launch(headless=True)` baru untuk **setiap URL**. | Cold-start Chromium per halaman menambah overhead ~800–1.500 ms dan risiko gagal sesi jika banyak halaman JS diproses berurutan. | Gunakan arsitektur `BrowserExtractor` dengan *shared browser process* per batch/job namun **ephemeral `BrowserContext` terisolasi per URL** (`new_context()` bersih tanpa cookie/storage bersama). |
| **2. Dynamic Content Rendering & JS** | Memicu Playwright jika teks statis `< 180` karakter atau terdeteksi `__next_data__` / `id="root"` dengan teks `< 450` karakter. | Beberapa halaman repositori OJS/DSpace modern merender abstrak statis (> 200 karakter) tetapi memuat tautan PDF atau isi penuh melalui komponen JS. | Perbaiki heuristik deteksi konten utama, ekstraksi tautan PDF (`citation_pdf_url` & link `.pdf`), serta tunggu selektor artikel utama secara cerdas. |
| **3. HTML Text Extraction** | `BeautifulSoup` menghapus tag navigasi dan kelas berisik (`sidebar`, `cookie`, `menu`), lalu mengambil `h1..h4, p, li, blockquote`. | Mengambil seluruh `<p>` dan `<li>` di dalam `<body>` bila `<article>`/`<main>` tidak ada masih bisa menyertakan daftar tautan terkait di bagian bawah halaman jurnal. | Tambahkan *text-density scoring* per blok kontainer, ekstraksi `meta description`, `lang`, dan daftar `source_links` terstruktur. |
| **4. Redirect Handling** | Loop manual hingga 5 hop (`follow_redirects=False`) dengan validasi ulang `validate_public_url` di setiap hop. | Sudah aman terhadap redirect ke IP internal (`127.0.0.1`, `169.254.169.254`), namun `final_url` dan jumlah hop belum terekam eksplisit di hasil ekstraksi. | Ekspos `requested_url`, `final_url`, dan `http_status` secara eksplisit di objek hasil `BrowserExtractor`. |
| **5. Canonical URL Detection** | Membaca `<link rel="canonical">` dan menghapus parameter pelacakan (`utm_*`, `fbclid`, `gclid`). | `<link rel="canonical">` relatif (mis. `/article/view/123`) belum di-`urljoin` dengan `final_url`. | Resolusi `urljoin(final_url, canonical_href)` sebelum `canonicalize_url`. |
| **6. Timeout & Retry** | Retry 3x dengan *exponential backoff* (`0.5 * 2^attempt`) untuk HTTP `429`/`503` dan error soket. | Pada pencarian provider (`registry.py`), eksekusi kueri ke banyak provider masih sekuensial sehingga akumulasi latency tinggi (penyebab utama durasi ~11 menit 10 detik ketika kuota kueri besar). | Paralelkan pencarian lintas provider independen dengan *per-provider semaphore & rate limiter* + reuse koneksi HTTP. |
| **7. Memory & CPU Consumption** | Streaming byte dengan batas `limit_bytes` (`64 KB` chunk) mencegah OOM pada unduhan besar; Playwright memblokir `image`, `media`, `font`. | Peluncuran proses Chromium berulang meningkatkan spike CPU. | *Browser process pooling* terbatas dalam cakupan job + pemblokiran stylesheet/tracker non-esensial saat hanya mengekstrak teks. |
| **8. Failed Browser Sessions** | Ditangkap oleh blok `try/except` dan dikembalikan sebagai `CRAWL_FAILED` tanpa menjatuhkan worker utama. | Belum ada metode `health_check()` mandiri untuk mendiagnosis kesiapan browser dari UI. | Implementasikan `BrowserExtractor.health_check()` dan tampilkan di diagnostik provider. |
| **9. Document Download (PDF/XML)** | Deteksi *magic bytes* `%PDF-` dan header XML (`<?xml`, `<article`, `<TEI`) sudah akurat. | Halaman *landing page* jurnal (OJS/DSpace) yang memiliki meta `citation_pdf_url` belum otomatis mengikuti URL PDF OA tersebut bila HTML hanya berisi abstrak. | Ekstrak `citation_pdf_url` / tautan galley PDF resmi pada landing page OA untuk mengambil full-text PDF asli secara legal. |
| **10. Duplicate URL & Content** | Deduplikasi berbasis DOI, `canonical_url`, `normalized_title`, SHA-256 `file_hash`, dan MinHash Jaccard `>= 0.85`. | Jika dua URL berbeda menghasilkan teks identik sebelum masuk DB dalam satu batch paralel, keduanya masih bisa diekstrak bersamaan. | Tambahkan *content-hash cache* in-memory sebelum tahap indeksasi penuh. |
| **11. Robots.txt & Etika Akses** | Memeriksa `is_url_allowed` (`robots.txt`) dan jeda per domain (`CRAWL_DOMAIN_DELAY_SEC`). Menolak HTTP `401/403/451` sebagai `ACCESS_RESTRICTED`. | Sudah patuh kebijakan akses; tidak melakukan bypass CAPTCHA/paywall/stealth. | Pertahankan kepatuhan penuh; pastikan opsi crawler yang diuji (Playwright, Crawl4AI, Scrapling) hanya dievaluasi pada mode standar yang patuh aturan situs. |

---

## 3. Temuan Audit UI & Mesin Skor Terkait

1. **Bug Navigasi Ganda Desktop (`ReportDetailPage.tsx`)**:
   - `theme.css` mendefinisikan `.mobile-tab-select { display: none; }`, sedangkan `ReportDetailPage.tsx` menulis `className="tabs-mobile-select"`. Akibatnya, elemen `<select>` dan `.tabs-bar` tampil bersamaan pada layar desktop.
   - Selain itu terdapat ketidaksinkronan nama kelas antara `theme.css` dan JSX (`.accordion-header` vs `.accordion-trigger`, `var(--color-primary)` vs `var(--primary)`).
2. **Audit Perhitungan Skor (`408 / 5.973` kata eligible)**:
   - `408 / 5973 = 6,830738...%` → dibulatkan menjadi **`6,83%`**.
   - `Exact = 290 / 5973 = 4,855181...%` → dibulatkan menjadi **`4,86%`**.
   - `Near-Exact = 118 / 5973 = 1,975556...%` → dibulatkan menjadi **`1,98%`**.
   - Jumlah kata unik `290 + 118 = 408` (**tidak ada penghitungan ganda**), namun penjumlahan dua angka yang sudah dibulatkan `4,86% + 1,98% = 6,84%` tampak berselisih `0,01%` dari `6,83%`. Pada Phase 9, nilai presisi sebelum pembulatan dan penjelasan matematis selisih pembulatan ditampilkan langsung di accordion laporan.


---

## 4. Hasil Benchmark Empiris 22 URL: Playwright vs Crawl4AI vs Scrapling

Hasil eksekusi [run_phase9_crawler_benchmark.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase9_crawler_benchmark.py) ([phase9_crawler_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_crawler_benchmark.json)) pada 22 URL akademik legal (Static HTML, JS-rendered SPA, OA Journal, OJS, DSpace, EPrints, XML JATS, Public PDF):

| Engine | Keberhasilan Ekstraksi | Presisi Konten Utama | Penghapusan Boilerplate | Kelengkapan Teks (Recall) | Akurasi URL Kanonis | Akurasi Metadata | Rata-rata Latensi | Total Latensi | Delta Memori |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`playwright_naskahguard`** (`IsolatedPlaywrightExtractor`) | **100,0%** (22/22) | **82,74%** | **100,0%** | **96,21%** | **100,0%** | **88,64%** | **35,05 ms** | **2.589,87 ms** | 29,94 MB |
| **`crawl4ai_local`** (`AsyncWebCrawler` 0.9.6) | 90,91% (gagal pada biner PDF) | 43,51% | 18,18% | 90,91% | 18,18% | 45,45% | 2.939,73 ms | 65.556,69 ms | 5,41 MB |
| **`scrapling_standard_http`** (`Fetcher` 0.5.1, non-stealth) | 90,91% (gagal pada PDF) | 39,02% | 18,18% | 74,24% (meleset pada JS SPA) | **100,0%** | 86,36% | **11,66 ms** | **261,10 ms** | **0,84 MB** |

**Keputusan Arsitektur**: Mempertahankan dan meningkatkan **`IsolatedPlaywrightExtractor`** (HTTP streaming cepat + ekstraktor kepadatan HTML/JATS XML/PyMuPDF + fallback Playwright Chromium terisolasi ketika halaman membutuhkan eksekusi JavaScript) sebagai satu-satunya engine produksi utama tanpa menambahkan >100 paket transitif berat `crawl4ai` ke `backend/requirements.txt`.
