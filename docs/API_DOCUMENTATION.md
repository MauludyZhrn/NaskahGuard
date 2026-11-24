# Dokumentasi API — NaskahGuard

Seluruh endpoint berada di bawah prefix `/api`. Jika `API_TOKEN` diatur pada environment, setiap permintaan (kecuali `GET /api/health`) wajib menyertakan header `Authorization: Bearer <API_TOKEN>`.

## 1. Kesehatan & Konfigurasi
- `GET /api/health` — Status layanan backend, koneksi database, ketersediaan OCR, modul semantik, dan adapter Noplag.
- `GET /api/config` — Mengembalikan `app_name` (dari konfigurasi `APP_NAME`), batas ukuran unggah, versi, dan status fitur aktif.

## 2. Manajemen Dokumen Submission
- `POST /api/documents` — Unggah dokumen PDF, DOCX, atau TXT (`multipart/form-data`: `file`). Melakukan validasi magic bytes, ukuran, sanitasi nama file, ekstraksi teks, segmentasi, dan deteksi struktur.
- `GET /api/documents` — Daftar dokumen unggahan (`role=SUBMISSION` secara default).
- `GET /api/documents/{id}` — Detail metadata dokumen.
- `GET /api/documents/{id}/text` — Teks asli utuh beserta pemetaan halaman dan segmen.
- `GET /api/documents/{id}/file` — Unduh berkas asli dengan `Content-Disposition` aman.
- `DELETE /api/documents/{id}` — Menghapus dokumen beserta berkas fisik, hasil ekstraksi, segmen, fingerprint, riwayat pemeriksaan, match, dan laporan terkait (dicatat di `audit_logs`).

## 3. Korpus Sumber Lokal
- `POST /api/corpus` — Unggah berkas sumber ke korpus lokal beserta metadata (`title`, `authors`, `year`, `doi`, `url`, `source_type`). Otomatis membangun segmen, fingerprint Winnowing, dan signature MinHash.
- `GET /api/corpus` — Daftar dokumen dalam korpus (`role` in `CORPUS`, `EXTERNAL`).
- `GET /api/corpus/stats` — Statistik korpus (jumlah dokumen, total kata, total fingerprint, distribusi bahasa & tipe sumber).

## 4. Pemeriksaan & Laporan
- `POST /api/checks` — Memulai pemeriksaan baru (`{ "document_id": "...", "settings": {...} }`). Mengembalikan HTTP `202 Accepted` berisi `check_id` dan `report_number` (`NG-YYYYMMDD-XXXX`).
- `GET /api/checks` — Daftar riwayat pemeriksaan.
- `GET /api/checks/{id}` — Status pemeriksaan (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`), persentase progres, tahap aktif, dan `stage_counts`.
- `GET /api/checks/{id}/report` — Laporan JSON lengkap (overview, metrics, coverage, sources, matches, stage_counts, analytics per bab & per halaman).
- `GET /api/checks/{id}/viewer` — Segmen teks submission non-overlap dengan prioritas warna (`EXACT > NEAR_EXACT > LEXICAL > SEMANTIC > EXCLUDED`) dan referensi `match_ids`.
- `GET /api/checks/{id}/sources/{source_id}/viewer` — Teks sumber dan rentang highlight sisi sumber untuk pemeriksaan tertentu.
- `GET /api/checks/{id}/export.pdf` — Unduh laporan dalam format PDF (ReportLab).
- `GET /api/checks/{id}/export.html` — Unduh laporan HTML mandiri dengan grafik SVG inline.
- `GET /api/checks/{id}/export.json` — Unduh laporan JSON terstruktur.

## 5. Dasbor, Provider, Monitor Penemuan, OAI-PMH, Pengaturan, dan Audit
- `GET /api/dashboard` — Agregasi nyata jumlah dokumen diperiksa, rata-rata SI, laporan terbaru, statistik korpus, dan aktivitas audit terkini.
- `GET /api/providers` — Status adapter lokal, akademik (OpenAlex, Europe PMC, arXiv, Crossref), web search (SearXNG, Official Web API), Playwright crawler, OAI-PMH, dan Noplag opsional.
- `GET /api/providers/monitor` — Data pemantauan langsung kueri, akuisisi URL (`source_acquisitions`), dan status indeksasi (`?check_id=...`).
- `GET /api/oai/repositories`, `POST /api/oai/repositories`, `POST /api/oai/repositories/{id}/verify`, `POST /api/oai/repositories/{id}/harvest`, `DELETE /api/oai/repositories/{id}` — Manajemen dan panen repositori akademik Indonesia berbasis OAI-PMH 2.0.
- `GET /api/settings` & `PUT /api/settings` — Baca dan ubah pengaturan default pengecualian serta ambang batas operasional.
- `GET /api/audit` — Log aktivitas audit sistem.
