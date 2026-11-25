# NaskahGuard — Phase 10.2: Penyelesaian Internet Search, Browser Crawler, & SearXNG

> **Tanggal Verifikasi**: 25 November 2026  
> **Artefak Uji Live**: [phase10_2_live_web_e2e.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_live_web_e2e.json)  
> **Skrip Reproduksi**: [run_phase10_2_live_web_e2e.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase10_2_live_web_e2e.py)

---

## 1. Kontrol Baru pada Halaman Pemeriksaan Baru (`/new-check`)

Di dalam panel akordeon **"Pengaturan Sumber & Pengecualian Plagiasi"** pada [NewCheckPage.tsx](file:///d:/Projects/NaskahGuard/frontend/src/pages/NewCheckPage.tsx), kini tersedia kontrol penuh dengan status nyata langsung dari `GET /api/providers`:

| Kontrol UI | Kunci Settings | Default | Sumber Status Backend |
|---|---|---|---|
| **Aktifkan Pencarian Sumber Eksternal** | `use_external_sources` | **OFF (`false`)** | Sakelar induk privasi (tidak mengirim data keluar sebelum diaktifkan) |
| **Aktifkan Pencarian Jurnal & Repositori Ilmiah** | `enable_academic_search` | ON (`true`, aktif saat induk ON) | Jumlah penyedia akademik terkonfigurasi (`OpenAlex`, `Europe PMC`, `DOAJ`, `arXiv`, `Crossref`) |
| **Aktifkan Pencarian Web Umum** | `enable_web_search` | **OFF (`false`)** | Status nyata `searxng` / `web_api` (`Siap` vs `Belum Dikonfigurasi`) |
| **Aktifkan Browser Crawler Terisolasi** | `enable_browser_crawler` | **OFF (`false`)** | Status nyata `playwright_crawler` (`Playwright Siap` vs `Belum Terpasang`) |
| **Aktifkan Pengambilan Full-Text** | `enable_fulltext_download` | ON (`true`) | Mengunduh & mengindeks PDF/HTML/XML terbuka ke korpus lokal SQLite |

Selain itu, typo variabel lingkungan pada pesan status `backend/app/api/providers.py` telah diperbaiki menjadi `NG_SEARXNG_URL` agar selaras dengan `backend/app/config.py`.

---

## 2. Panduan Konfigurasi SearXNG Lokal (Docker Compose)

NaskahGuard tidak mewajibkan API pencarian web berbayar. Untuk mengaktifkan **Pencarian Web Umum** secara lokal via SearXNG:

1. Pastikan file konfigurasi sudah tersedia:
   - [docker-compose.searxng.yml](file:///d:/Projects/NaskahGuard/docker-compose.searxng.yml)
   - [searxng/settings.yml](file:///d:/Projects/NaskahGuard/searxng/settings.yml) *(mengaktifkan `formats: [html, json]` agar API JSON SearXNG aktif di localhost)*
2. Jalankan kontainer SearXNG secara lokal (terikat hanya ke `127.0.0.1:8080`):
   ```powershell
   docker compose -f docker-compose.searxng.yml up -d
   ```
3. Tambahkan pada `backend/.env`:
   ```env
   NG_SEARXNG_URL=http://127.0.0.1:8080
   ```
4. Mulai ulang backend NaskahGuard. Status **General Web Search (SearXNG Self-Hosted)** di `/discovery-monitor` dan `/new-check` akan otomatis berubah dari `Belum Dikonfigurasi` menjadi **`Siap`**.

---

## 3. Verifikasi End-to-End Live Publik (Tanpa Dummy Sources)

Skrip [run_phase10_2_live_web_e2e.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase10_2_live_web_e2e.py) menjalankan seluruh alur nyata dengan **korpus lokal kosong (`0` dokumen awal)**:

`Query → Live Search Result → HTTP/Browser Extraction → Full-Text PDF → Local SQLite Index → Similarity Matching → Report`

| Metrik Eksekusi Live | Nilai Aktual Teramati |
|---|---|
| Dokumen lokal awal (seed) | **`0`** |
| Penyedia aktif pada uji | `arxiv`, `doaj` (dengan `enable_browser_crawler=true`, `enable_fulltext_download=true`) |
| Total kueri pencarian dieksekusi | `6` kueri |
| URL unik ditemukan | `10` URL |
| Artikel publik diunduh & diindeks full-text | **`5` dokumen PDF nyata (`0` gagal)** |
| Sumber cocok terverifikasi (`MATCH_VERIFIED`) | **#1 — *JSidentify-V2: Leveraging Dynamic Memory Fingerprinting for Mini-Game Plagiarism Detection*** (`http://arxiv.org/abs/2508.01655v1`) |
| Kata cocok / Kata diperiksa | **`63 / 99` kata** |
| Indeks Kemiripan tercatat di laporan | **`63.64%`** |
| Total waktu selesai end-to-end | **`15.65 detik`** (`15.651,84 ms`) |
