# Optimasi Intelijen Pencarian Sumber (Phase 8)

Dokumen ini merinci peningkatan mesin pencarian eksternal NaskahGuard berdasarkan temuan pada [PHASE8_SEARCH_AUDIT.md](file:///d:/Projects/NaskahGuard/docs/research/PHASE8_SEARCH_AUDIT.md).

## 1. Multi-Query Generator & Profil Intensitas (`backend/app/sources/query_generator.py`)

NaskahGuard mendukung tiga profil intensitas pencarian:
- **`QUICK`** (maks. 8 kueri): Judul + frasa inti untuk pemeriksaan cepat.
- **`BALANCED`** (maks. 24 kueri, default): Distribusi *round-robin* lintas bab/bagian dengan 7 jenis kueri (`title`, `exact_phrase`, `ngram_phrase`, `distinctive_keywords`, `academic_terminology`, `language_aware`, `similar_variation`).
- **`DEEP`** (maks. 48 kueri): Eksplorasi mendalam multi-bab untuk skripsi, tesis, dan disertasi.

**Perlindungan Privasi & Kebersihan Kueri**:
- Segmen `BIBLIOGRAPHY`, `COVER`, dan `TOC` disaring ketat sehingga tidak pernah dikirim sebagai kueri.
- Hanya frasa/istilah terpilih yang dikirim ke provider eksternal, bukan keseluruhan naskah privat.

## 2. Search Quality Ranking (`backend/app/sources/ranking.py`)

Sebelum menghabiskan kuota pengunduhan full-text atau browser crawler, setiap kandidat diberi skor relevansi berbasis tumpang tindih judul, abstrak, kata kunci dokumen, dan ketersediaan OA PDF:
- `HIGHLY_RELEVANT`
- `RELEVANT`
- `WEAK_CANDIDATE`
- `UNRELATED` (tidak diprioritaskan untuk diunduh)

> **Catatan Transparansi**: Skor relevansi pencarian **hanya** digunakan untuk prioritas akuisisi kandidat, dan **tidak pernah** digunakan sebagai skor plagiarisme.

## 3. Caching, Konkurensi Terbatas & Telemetri (`cache.py`, `registry.py`, `providers.py`)

- **TTL Cache**: `url_crawl_cache` dan `doi_resolution_cache` mencegah pengunduhan berulang URL/DOI yang sama dalam jendela waktu aktif.
- **Bounded Concurrency**: Pengunduhan/crawling berjalan paralel terbatas menggunakan `ThreadPoolExecutor(max_workers=4)` dengan tetap menghormati jeda per domain dan SSRF Guard.
- **Provider Health Telemetry**: Endpoint `GET /api/providers` mengembalikan status nyata (`configured`, `enabled`, `health`: `healthy|ready|degraded|unconfigured`, `request_count`, `result_count`, `timeout_count`, `last_successful_request`, `last_error`).
- **Stage Timings**: Setiap tahap pipeline mencatat durasi nyata dalam `metrics.stage_timings_ms`.

## 4. Opsional: SearXNG Lokal Self-Hosted

Untuk pencarian web umum tanpa API key berbayar, tersedia panduan opsional pada [docker-compose.searxng.yml](file:///d:/Projects/NaskahGuard/docker-compose.searxng.yml). NaskahGuard tetap berjalan penuh tanpa Docker/SearXNG.
