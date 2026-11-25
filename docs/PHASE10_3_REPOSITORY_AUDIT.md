# Audit Keandalan Repositori Akademik & OAI-PMH Harvester — NaskahGuard Phase 10.3

**Tanggal Audit:** 25 November 2026  
**Cakupan Audit:**
- `backend/app/sources/oai_pmh.py`
- `backend/app/api/oai.py`
- `backend/app/models.py`
- `backend/alembic/versions/` (`0001_initial.py`, `0002_phase7_discovery.py`, `0003_phase10_ai_detection.py`)
- `frontend/src/pages/RepositoriesPage.tsx`
- `backend/tests/test_phase7_discovery.py`

---

## 1. Ringkasan Eksekutif

Audit berbasis kode aktual (tanpa asumsi) menemukan **8 akar penyebab nyata** mengapa fitur *Academic Repository Manager* dan *OAI-PMH Harvester* sebelumnya gagal saat digunakan secara langsung oleh pengguna — termasuk **2 bug kritis (HTTP 422)** yang menyebabkan tombol **Simpan Repositori** dan **Panen** di antarmuka selalu gagal 100%, serta 6 kelemahan protokol, ketahanan panen, skema basis data, dan UX.

---

## 2. Daftar Akar Penyebab Terbukti

### Bug Kritis #1 — Penambahan Repositori dari UI Selalu Gagal (HTTP 422)
- **Bukti kode:**
  - `frontend/src/pages/RepositoriesPage.tsx:54` mengirim `repo_type: "OAI-PMH"`.
  - `backend/app/api/oai.py:22` memvalidasi `repo_type: str = Field(default="ojs", pattern="^(ojs|dspace|eprints|other)$")`.
- **Dampak:** Setiap kali pengguna mengisi formulir dan menekan **Simpan Repositori**, backend FastAPI/Pydantic langsung menolak permintaan dengan `422 Unprocessable Entity` karena `"OAI-PMH"` tidak cocok dengan regex `^(ojs|dspace|eprints|other)$`.

### Bug Kritis #2 — Tombol Panen (`Panen`) dari UI Selalu Gagal (HTTP 422) + Salah Field Ringkasan
- **Bukti kode:**
  - `frontend/src/pages/RepositoriesPage.tsx:88-90` memanggil `POST /api/oai/repositories/{id}/harvest` **tanpa request body JSON**.
  - `backend/app/api/oai.py:110` mendefinisikan `body: OAIHarvestRequest` sebagai parameter wajib (tidak memiliki nilai bawaan `None`), sehingga FastAPI mengembalikan `422 Unprocessable Entity` (`Field required: body`).
  - Selain itu, `RepositoriesPage.tsx:87,92` membaca `res.summary?.records_seen`, padahal backend (`oai_pmh.py:335`) mengembalikan `records_harvested`.
- **Dampak:** Fitur panen tidak pernah dapat dijalankan dari antarmuka web, dan seandainya berhasil, jumlah entri akan selalu terbaca `0`.

### Bug #3 — Redirect HTTP Ditolak Mentah-Mentah (`follow_redirects=False`)
- **Bukti kode:** `backend/app/sources/oai_pmh.py:53` memanggil `client.get(safe_url, params=params, headers=..., follow_redirects=False)` lalu langsung `resp.raise_for_status()`.
- **Dampak:** Sangat banyak repositori kampus (OJS, DSpace, EPrints) melakukan redirect standar `301`/`302`/`308` (mis. `http://` → `https://`, `kampus.ac.id` → `www.kampus.ac.id`, atau `/oai` → `/oai/`). Penolakan redirect tanpa evaluasi *hop-by-hop* menyebabkan koneksi valid gagal secara tiba-tiba. (Tetap wajib menjaga proteksi SSRF pada setiap *hop* redirect.)

### Bug #4 — Tidak Ada Penanganan HTML-alih-alih-XML dan Error OAI-PMH Tidak Terstruktur
- **Bukti kode:** `backend/app/sources/oai_pmh.py:55-59` langsung menjalankan `ET.fromstring(resp.text)` tanpa memeriksa `Content-Type` atau pola halaman HTML (`<!doctype html>`, `<html`), dan semua kode error OAI-PMH hanya melempar `ValueError` generik.
- **Dampak:**
  - Jika pengguna memasukkan URL halaman utama portal alih-alih endpoint OAI-PMH, parser XML melempar pesan teknis mentah seperti `syntax error` / `mismatched tag` tanpa solusi.
  - Kode error standar OAI-PMH (`badArgument`, `badVerb`, `badResumptionToken`, `cannotDisseminateFormat`, `noRecordsMatch`, `noSetHierarchy`, `noMetadataFormats`) tidak diterjemahkan ke pesan Bahasa Indonesia dan rekomendasi perbaikan.
  - Respons `noRecordsMatch` pada panen inkremental atau repositori kosong menjatuhkan seluruh status repositori menjadi `ERROR` alih-alih diselesaikan secara anggun.

### Bug #5 — Hardcoded `oai_dc`, Tanpa Negosiasi `metadataPrefix`, Tanpa Pemilihan Koleksi (`setSpec`)
- **Bukti kode:** `backend/app/models.py:252-268` dan `backend/app/sources/oai_pmh.py:244-249`.
- **Dampak:**
  - Repositori yang tidak menyediakan `oai_dc` (atau memakai `oai_etdms`, `qdc`, `dim`, `mods`, `arXiv`) gagal total dengan `cannotDisseminateFormat`.
  - Pengguna tidak dapat memilih koleksi/jurnal (`setSpec`) maupun melihat pratinjau metadata sebelum memanen.

### Bug #6 — Tidak Resumable, Tanpa Kontrol Jeda/Lanjut, Tanpa Log & Tanpa Retry Record Gagal
- **Bukti kode:** `backend/app/sources/oai_pmh.py:241-331` hanya menyimpan `repo.records_harvested` dan `repo.last_datestamp` di akhir seluruh loop (`line 321-326`), tidak menyimpan `resumptionToken`, tidak mencatat status tiap rekaman, dan tidak memiliki tabel log.
- **Dampak:**
  - Jika halaman ke-3 mengalami *timeout*, *rate limit*, atau `badResumptionToken`, seluruh progres sebelumnya hilang dan tidak bisa dilanjutkan (`Resume`).
  - Tidak ada mekanisme *Pause*, *Resume*, *Retry Failed*, maupun *Harvest Logs* yang bisa diaudit pengguna.
  - Tidak ada jeda sopan (*rate-limit delay*) antar halaman `ListRecords`.

### Bug #7 — Deteksi URL Full-Text Terlalu Sempit & Metrik Funnel Tercampur
- **Bukti kode:** `backend/app/sources/oai_pmh.py:131-158` hanya memeriksa `.pdf`, `/article/download/`, `/bitstream/` pada teks elemen XML.
- **Dampak:**
  - Melewatkan pola URL DSpace 7 (`/server/api/core/bitstreams/{uuid}/content`), atribut XML (`ref`, `href`, `url` pada DIDL/MODS/XOAI/EPrints), halaman artikel OJS (`/article/view/` dengan meta tag `citation_pdf_url`), serta pola arXiv (`/abs/` → `/pdf/`).
  - Tidak memisahkan 7 metrik funnel secara tegas: `metadata_found`, `metadata_saved`, `pdf_urls_found`, `pdf_accessible`, `fulltext_extracted`, `document_indexed`, dan `document_compared`.

### Bug #8 — Keterbatasan Skema DB, Endpoint API, dan Antarmuka Manajemen
- **Bukti kode:**
  - `backend/alembic/versions/` baru sampai revisi `0003` (`oai_repositories` hanya punya 14 kolom dasar; belum ada tabel `oai_harvest_records` dan `oai_harvest_logs`).
  - `backend/app/api/oai.py` belum menyediakan `PUT /repositories/{id}` (edit), `POST /test-connection` (uji koneksi pra-simpan 8 tahap), `POST /auto-detect`, `POST /repositories/{id}/pause`, `POST /repositories/{id}/resume`, `POST /repositories/{id}/retry-failed`, `GET /repositories/{id}/records`, `GET /repositories/{id}/logs`, dan `POST /repositories/{id}/preview`.
  - `frontend/src/pages/RepositoriesPage.tsx` belum memiliki wizard uji koneksi 8 tahap, deteksi otomatis platform, tabel 6 kolom (`Nama | Platform | Koneksi | Record | Full-text | Status`), modal edit, maupun halaman detail repositori (`/repositories/:repoId`).
  - Cakupan pengujian OAI-PMH di `backend/tests/test_phase7_discovery.py` baru menguji 1 skenario *happy-path* sederhana (tidak mencakup DSpace 7, OJS, EPrints, HTML response, `badResumptionToken`, `noRecordsMatch`, deleted records, redirect, timeout, PDF tidak dapat diakses, maupun duplikat DOI).

---

## 3. Rencana Perbaikan Terstruktur (Phase 10.3)

1. **Migrasi Database (`0004_phase10_3_oai_upgrade.py`) & ORM (`models.py`)**: Perluas `oai_repositories` secara *backward-compatible* serta tambahkan tabel `oai_harvest_records` dan `oai_harvest_logs`.
2. **Engine OAI-PMH (`backend/app/sources/oai_pmh.py`)**:
   - Dukungan endpoint DSpace 7, DSpace lama, OJS, EPrints, dan OAI-PMH umum (deteksi otomatis + input manual tanpa mengubah URL pengguna secara diam-diam sebelum diverifikasi).
   - Redirect aman *hop-by-hop* dengan validasi SSRF pada setiap tujuan.
   - Wizard Uji Koneksi 8 tahap lengkap dengan kode error, status HTTP, pesan Bahasa Indonesia, dan solusi.
   - Negosiasi `metadataPrefix`, dukungan `setSpec`, pemulihan `badResumptionToken`, penanganan `noRecordsMatch` & `deleted`, penyimpanan inkremental per halaman, kontrol *Pause/Resume*, *Retry Failed*, dedup DOI/URL/identifier, dan funnel 7 tahap yang transparan.
3. **API (`backend/app/api/oai.py`)**: Perbaiki validasi `repo_type` dan body opsional `harvest`, serta tambahkan seluruh endpoint manajemen, wizard, pratinjau, jeda/lanjut, ulangi gagal, rekaman, dan log.
4. **UI (`RepositoriesPage.tsx` & `RepositoryDetailPage.tsx`)**: Desain ulang bersih (shadcn/ui, Lucide React, Bahasa Indonesia, Ivory Burgundy) dengan Wizard 8 tahap pra-simpan, tabel 6 kolom, edit repositori, halaman detail, kontrol panen, pemilih koleksi, pratinjau metadata, dan log.
5. **Pengujian Menyeluruh**: 18+ kasus uji mock menyeluruh + minimal 1 pengujian panen **live nyata** ke repositori OAI-PMH publik resmi yang kompatibel + regresi penuh + Playwright UI QA.
