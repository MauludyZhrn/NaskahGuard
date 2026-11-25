# Laporan Pengujian Repositori Akademik & OAI-PMH Harvester — Phase 10.3

**Tanggal Pengujian:** 25 November 2026  
**Suite Unit & Integrasi Mock:** `backend/tests/test_phase10_3_oai_repositories.py`  
**Suite Pengujian Live Publik:** `benchmark/run_phase10_3_live_oai_harvest.py`  
**Bukti JSON Live:** `benchmark/results/phase10_3_live_oai_harvest.json`

---

## 1. Ringkasan Hasil Pengujian

- **Total Pytest Backend (Regresi + Phase 10.3):** `56 passed, 1 skipped, 0 failed` (`11.82s`)
- **Kasus Uji Mock Baru (Phase 10.3):** `14 fungsi uji` mencakup **19 skenario protokol, platform, ketahanan, keamanan, dan API E2E** — seluruhnya **LULUS (PASS)**.
- **Uji Panen Live Nyata (`https://oaipmh.arxiv.org/oai`, `set=cs`):** **LULUS (PASS)** dengan Wizard 8/8 `READY`, 3/3 PDF diunduh & diindeks ke SQLite, serta uji kemiripan langsung terhadap dokumen hasil panen menghasilkan `85.89%` (`140` kata cocok, `document_compared=1`).

---

## 2. Matriks Skenario Pengujian Mock (19 Kasus)

| # | Skenario | Fungsi Pengujian | Hasil | Verifikasi Utama |
|---|---|---|---|---|
| 1 | Pola Endpoint DSpace 7 (`/server/oai/request`) | `test_endpoint_patterns_and_non_destructive_cleaning` | PASS | Terdeteksi sebagai `dspace7`; pembersihan `?verb=...` non-destruktif |
| 2 | Auto-detect DSpace 7 & Bitstream PDF (`/server/api/core/bitstreams/.../content`) | `test_dspace7_auto_detect_and_bitstream_harvest` | PASS | Deteksi otomatis dari root portal + panen & indeks PDF bitstream |
| 3 | DSpace Lama (`/oai/request`, `/dspace-oai/request`) & `/bitstream/` | `test_legacy_dspace_dim_and_bitstream_harvest` | PASS | Terdeteksi `dspace_legacy`, baca metadata `dim` & unduh `/bitstream/` |
| 4 | OJS (`/index.php/{journal}/oai`, `/{journal}/oai`) + `citation_pdf_url` | `test_ojs_landing_citation_pdf_discovery` | PASS | Temukan PDF publik dari meta tag `<meta name="citation_pdf_url">` pada halaman artikel |
| 5 | EPrints (`/cgi/oai2`) & Wizard 8 Tahap Lengkap + Pratinjau | `test_eprints_8_stage_wizard_and_preview` | PASS | 8/8 tahap PASS (`READY`), pratinjau metadata & DOI tervalidasi |
| 6 | Endpoint Valid + Regresi API Bug #1 (`repo_type="OAI-PMH"`) | `test_oai_api_endpoints_and_regressions` | PASS | `POST /api/oai/repositories` mengembalikan `201` (sebelumnya `422`) |
| 7 | Regresi API Bug #2 (`POST /harvest` tanpa body) + Edit `PUT` + Logs | `test_oai_api_endpoints_and_regressions` | PASS | `POST /harvest` kosong mengembalikan `200`; `PUT`, `pause`, `records`, `logs`, `DELETE` lulus |
| 8 | Endpoint Tidak Valid (HTTP 404, Skema `ftp://`, SSRF `127.0.0.1`) | `test_invalid_endpoint_ssrf_and_html_instead_of_xml` | PASS | `HTTP_404`, `INVALID_URL`, `SSRF_BLOCKED` terdeteksi di tahap yang tepat |
| 9 | Respons HTML alih-alih XML (`text/html`) | `test_invalid_endpoint_ssrf_and_html_instead_of_xml` | PASS | Tahap 2 PASS (HTTP 200), Tahap 3 FAIL dengan kode `HTML_RESPONSE` + saran Bahasa Indonesia |
| 10 | Format Metadata Tidak Didukung (`cannotDisseminateFormat`) | `test_legacy_dspace_dim_and_bitstream_harvest` | PASS | Wizard memberi `WARN`, harvester bernegosiasi otomatis ke `dim` |
| 11 | Tanpa Hierarki Koleksi (`noSetHierarchy`) | `test_legacy_dspace_dim_and_bitstream_harvest` | PASS | Tahap 5 `WARN` (tidak gagal fatal), repositori tetap bisa dipanen |
| 12 | Repositori Kosong (`noRecordsMatch`) | `test_empty_repository_no_records_match` | PASS | Diselesaikan anggun (`status="VERIFIED"`, `records_harvested=0`, tidak crash) |
| 13 | Paginasi Multi-Halaman dengan `resumptionToken` | `test_pagination_expired_token_recovery_and_deleted_records` | PASS | 2 halaman diproses berurutan (`pages_fetched=2`) |
| 14 | `resumptionToken` Kedaluwarsa (`badResumptionToken`) | `test_pagination_expired_token_recovery_and_deleted_records` | PASS | Pemulihan otomatis (`TOKEN_RECOVERY` di log) tanpa kehilangan rekaman sebelumnya |
| 15 | Rekaman Dihapus (`<header status="deleted">`) | `test_pagination_expired_token_recovery_and_deleted_records` | PASS | Tercatat `status="DELETED"`, tidak pernah diindeks sebagai full-text |
| 16 | Redirect Aman (`301`) & Blokir Redirect SSRF (`302 -> 127.0.0.1`) | `test_safe_redirect_and_ssrf_redirect_blocked` | PASS | Redirect publik valid diikuti; redirect ke loopback diblokir di Tahap 2 (`SSRF_BLOCKED`) |
| 17 | Timeout di Tengah Panen (`httpx.ReadTimeout`) | `test_timeout_mid_harvest_preserves_page1_progress` | PASS | Progres halaman 1 & `resumption_token` tetap tersimpan di SQLite untuk dilanjutkan |
| 18 | PDF Tidak Dapat Diakses (`403`) + Pemulihan via `retry_failed` | `test_pdf_inaccessible_then_retry_failed_succeeds` | PASS | Tidak pernah dianggap full-text saat 403; berhasil terindeks setelah `retry_failed` |
| 19 | Duplikat DOI + Kontrol Jeda/Lanjut (*Pause/Resume*) | `test_duplicate_doi_deduplicated`, `test_pause_and_resume_preserves_cursor` | PASS | DOI ganda ditandai `DUPLICATE` (0 duplikat di `documents`); cursor terjaga antar sesi |

---

## 3. Pengujian Live Nyata ke Repositori OAI-PMH Publik Resmi

Pengujian live dilakukan terhadap endpoint resmi **arXiv Public OAI-PMH** (`https://oaipmh.arxiv.org/oai`, `set=cs`) pada database SQLite terisolasi tanpa mengubah data produksi.

### A. Hasil Wizard Uji Koneksi 8 Tahap (Live)
- **Status Akhir:** `READY` (`8 lulus, 0 perhatian, 0 gagal`)
- **Nama Teridentifikasi:** `arXiv` (`platform_detected: arxiv`)
- **Format Metadata Didukung:** `oai_dc`, `arXiv`, `arXivOld`, `arXivRaw`
- **Koleksi (`ListSets`):** `100` koleksi terdeteksi
- **Uji `ListRecords`:** `1300` rekaman aktif dengan dukungan `resumptionToken`
- **Deteksi URL Full-Text:** `1300/1300` sampel memiliki URL PDF publik; uji akses sampel PDF mengembalikan `HTTP 200`

### B. Hasil Panen & Funnel 7 Tahap (Live)
- `1. metadata_found`: **3**
- `2. metadata_saved`: **3**
- `3. pdf_urls_found`: **3**
- `4. pdf_accessible`: **3**
- `5. fulltext_extracted`: **3**
- `6. document_indexed`: **3** (`oai:arXiv.org:adap-org/9807003`, `oai:arXiv.org:adap-org/9903003`, `oai:arXiv.org:astro-ph/0008307`)
- `7. document_compared`: **1**
- `failed_records`: **0**

### C. Verifikasi End-to-End Terhadap Mesin Deteksi Plagiasi
Naskah uji yang memuat kutipan dari dokumen hasil panen live *"Development and Evolution of Neural Networks in an Artificial Chemistry"* (`4.243` kata) diperiksa terhadap korpus lokal (tanpa pencarian internet eksternal):
- **Status Pemeriksaan:** `COMPLETED`
- **Similarity Index:** `85.89%` (`140` kata cocok, `1` sumber cocok)
- Membuktikan alur penuh: **OAI-PMH Live → Ekstraksi PDF → Indeks SQLite Lokal → Deteksi Kemiripan**.
