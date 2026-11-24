# Audit Search Intelligence Sebelum Phase 8 (`PHASE8_SEARCH_AUDIT.md`)

Tanggal Audit: 2026-11-25

Dokumen ini mengaudit implementasi pencarian sumber eksternal Phase 7 pada `backend/app/sources/` dan `backend/app/engine/pipeline.py` sebelum optimasi Phase 8 dilakukan.

## 1. Temuan Audit Mendalam

| Aspek Audit | Kondisi Phase 7 | Akar Masalah / Bottleneck | Rencana Perbaikan Phase 8 |
|---|---|---|---|
| **Jumlah & Sebaran Kueri (`query_generator.py`)** | Default `max_search_queries = 8`, mengambil maksimal 2 kalimat per bab lalu memotong ke 8 kueri teratas. | Dokumen panjang (skripsi/tesis 6–8 bab) sering hanya terwakili di 2–3 bab awal; belum ada profil intensitas (`QUICK`/`BALANCED`/`DEEP`) atau variasi *academic terminology* & *similar phrase variation*. | Tambah profil `QUICK` (8), `BALANCED` (24), `DEEP` (48), distribusi merata per bab substantif, deduplikasi kueri ketat, dan 7 kategori kueri. |
| **Status & Kesehatan Provider (`providers.py`)** | Menampilkan daftar statis + 25 kueri terakhir. | Tidak ada agregasi *health status*, `last_successful_request`, `last_error`, `request_count`, `result_count`, atau `timeout_count` per provider. SearXNG belum memiliki panduan setup lokal Docker Compose. | Tambah agregasi telemetri kesehatan provider nyata dari `provider_queries` dan sediakan `docker-compose.searxng.yml` opsional. |
| **Ranking Relevansi Kandidat (`registry.py`)** | Mengambil `records[:5]` secara berurutan dari respons provider tanpa menyaring relevansi terhadap dokumen. | Kandidat lemah/tidak relevan ikut menyedot kuota crawl (`max_crawled_urls`) dan waktu unduh; hasil metadata-only terlalu banyak menumpuk. | Implementasikan *Search Quality Ranking* (`HIGHLY_RELEVANT`, `RELEVANT`, `WEAK_CANDIDATE`, `UNRELATED`) dan skip crawling untuk `UNRELATED` / `WEAK_CANDIDATE` berprioritas rendah. |
| **Strategi Pencarian & Performa (`registry.py`, `crawler.py`)** | Eksekusi provider dan pengunduhan URL berjalan **sekuensial** satu per satu tanpa cache URL/DOI. | Pada pemeriksaan nyata dengan banyak kueri & timeout 20 detik, pencarian + crawl berurutan dapat memakan waktu ratusan detik (> 400 detik). | Implementasikan TTL cache berbasis URL & DOI (`app/sources/cache.py`), *bounded concurrency* (`ThreadPoolExecutor`) dengan tetap menghormati rate limit per domain/provider, dan pencatatan durasi tiap tahap (`stage_timings_ms`). |
| **Transparansi Skor & Cakupan (`scoring.py`, `builder.py`)** | Metrik dasar sudah benar, namun belum ada objek `score_explanation` terstruktur & pemisahan eksplisit antara *full-text fetched*, *indexed*, *compared*, dan *verified match*. | Pengguna melihat angka Raw vs Adjusted atau rasio "X / Y" tanpa penjelasan matematis langsung di laporan. | Tambah `score_explanation` langsung dari perhitungan backend, pemisahan 9 metrik sumber tanpa label ambigu, serta format durasi Bahasa Indonesia (`X menit Y detik`). |
| **Modul Semantik (`semantic.py`)** | Sudah lazy-loaded, CPU-first, nonaktif default, dan terpisah dari Textual SI. | Sudah aman; tidak perlu mengunduh model besar otomatis. Dipertahankan dengan pelaporan status jujur di pengaturan dan laporan. | Pertahankan isolasi semantik dari Textual SI. |

## 2. Verifikasi Fakta Kritis
- **Playwright bukan search engine**: Playwright hanya merender halaman web publik yang URL-nya telah ditemukan oleh provider pencarian (OpenAlex, Europe PMC, SearXNG, Web API, OAI-PMH). Bila provider web search (`NG_SEARXNG_URL` / `NG_WEB_SEARCH_API_URL`) belum dikonfigurasi, sistem wajib menyatakan secara jujur bahwa pencarian web umum tidak tersedia.
- **Metadata-only tidak pernah menjadi sumber full-text**: Hanya dokumen dengan `FULLTEXT_INDEXED` yang dibandingkan di similarity engine dan dapat mencapai status `MATCH_VERIFIED`.
