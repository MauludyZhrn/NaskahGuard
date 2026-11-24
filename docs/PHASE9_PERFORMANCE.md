# Audit & Optimasi Performa Pipeline NaskahGuard (Phase 9)

Dokumen ini menganalisis penyebab durasi pemeriksaan panjang (~11 menit 10 detik pada skenario pencarian eksternal besar di versi sebelumnya) dan merinci optimasi arsitektural yang diterapkan pada Phase 9 tanpa menghapus satu pun tahap analisis.

## 1. Diagnosis Bottleneck Utama (Sebelum Phase 9)

1. **Eksekusi Kueri Provider Sekuensial (`O(Providers × Queries)`)**:
   - Pada Phase 8, loop pencarian berjalan berurutan per provider lalu per kueri. Dengan profil `BALANCED` (24 kueri) × 4 provider akademik = **96 permintaan HTTP berurutan**.
   - Provider `arXiv` mewajibkan jeda sopan 3 detik per permintaan: `24 × 3 detik = 72 detik` hanya untuk tidur (*sleep*), ditambah waktu tunggu jaringan setiap permintaan! Pada profil `DEEP` (48 kueri), ini memakan > 3–8 menit sebelum crawling dimulai.
2. **Tidak Ada Early-Abort ketika Provider Timeout Beruntun**:
   - Jika satu provider mengalami gangguan jaringan/timeout (mis. 15 detik), ke-24 kueri tetap dicoba satu per satu (`24 × 15s = 360 detik`).
3. **Cold-Start Koneksi HTTP & Indeksasi Ulang Konten Identik**:
   - Koneksi TLS dibuat berulang kali saat mengunduh kandidat, dan dua URL cermin (*mirror*) dengan isi byte PDF/HTML identik dapat diekstrak dua kali sebelum deduplikasi.

## 2. Optimasi yang Diterapkan pada Phase 9 ([registry.py](file:///d:/Projects/NaskahGuard/backend/app/sources/registry.py) & [cache.py](file:///d:/Projects/NaskahGuard/backend/app/sources/cache.py))

1. **Konkurensi Terbatas Lintas Provider (`ThreadPoolExecutor`)**:
   - Provider independen (`OpenAlex`, `Europe PMC`, `DOAJ`, `Crossref`, `arXiv`) dijalankan secara paralel dalam worker terpisah, sementara setiap provider tetap mematuhi *rate limit* internalnya sendiri.
2. **Kuota Kueri Spesifik Provider (`_PROVIDER_MAX_QUERIES`)**:
   - `arXiv` dibatasi maksimal **6 kueri peringkat tertinggi** per pemeriksaan (maksimal ~18 detik jeda sopan, bukan 144 detik), sementara `OpenAlex` tetap melayani hingga 48 kueri cepat.
   - Kueri yang dilewati dicatat secara jujur dalam `search_coverage.queries_skipped`.
3. **Deteksi Gangguan Dini (*Consecutive Error Early-Abort*)**:
   - Jika suatu provider gagal/timeout 2 kali berturut-turut dalam satu pemeriksaan, sisa antrean kueri ke provider tersebut dihentikan lebih awal agar tidak membekukan pipeline.
4. **Empat Lapisan Cache In-Memory (`TTLCache`)**:
   - `provider_query_cache` (TTL 30 menit): Mencegah pengiriman ulang kueri identik ke provider yang sama.
   - `url_crawl_cache` (TTL 60 menit): Menyimpan hasil crawl URL kanonis.
   - `doi_resolution_cache` (TTL 120 menit): Memetakan DOI langsung ke `document_id` lokal yang sudah terindeks.
   - `content_hash_cache` (TTL 120 menit): Memetakan SHA-256 byte unduhan langsung ke `document_id` lokal sehingga berkas mirror tidak diekstrak/diindeks ulang.
5. **Connection Pooling (`httpx.Client` Keep-Alive)**:
   - Worker pengunduhan berbagi pool koneksi HTTP (`max_keepalive_connections=8, max_connections=12`) untuk memangkas *handshake* TLS berulang.

## 3. Transparansi Waktu per Tahap (`stage_timings_ms`)

Tidak ada *fake progress* di NaskahGuard. Setiap laporan menyimpan dan menampilkan durasi nyata per tahap di accordion **"Rincian Waktu Pemrosesan per Tahap"**:
- `query_generation_ms`
- `provider_search_ms`
- `crawling_and_download_ms`
- `extraction_and_indexing_ms`
- `candidate_retrieval_ms`
- `matching_alignment_ms`
- `scoring_and_attribution_ms`
- `total_pipeline_ms`
