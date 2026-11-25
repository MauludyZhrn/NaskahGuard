# Laporan Pemanenan Lanjutan, Kontrol Batas & Integrasi Korpus Lokal — Phase 10.4

**Tanggal:** 26 November 2026  
**Cakupan Kode:** `backend/app/sources/oai_pmh.py`, `backend/app/ingestion/service.py`, `backend/app/worker.py`, `backend/app/models.py`

---

## 1. Mekanisme Pemanenan Lanjutan & Kontrol Batas

1. **Panen Berdasarkan Koleksi (`set_spec`)**: Penjelajah koleksi interaktif pada `/repositories/:repoId` memungkinkan pemilihan set tertentu atau seluruh repositori.
2. **Filter Tahun Publikasi (`year_from`, `year_to`)**: Diterapkan pada parameter OAI `from` serta validasi tahun per rekaman (`_record_matches_filters`).
3. **Filter Kata Kunci (`keyword_filter`)**: Menyaring judul, abstrak/deskripsi, dan subjek (`dc:subject`) sebelum proses unduhan PDF dilakukan.
4. **Filter Jenis Dokumen (`doc_type_filter`)**: Mendukung sinonim Bahasa Indonesia & Inggris untuk *artikel*, *skripsi*, *tesis*, *disertasi*, *prosiding*, dan *buku* terhadap `dc:type` / `setSpec`.
5. **Kontrol Batas Ketat (`max_records`, `max_downloads`, `max_scan_budget`)**:
   - Sistem tidak pernah mengunduh seluruh koleksi tanpa batas.
   - Ketika batas unduhan PDF (`max_downloads`) tercapai dalam satu sesi, rekaman berikutnya tetap disimpan sebatas metadata (`PDF_FOUND` / `METADATA_SAVED`) tanpa memicu unduhan tambahan.
6. **Inkremental, Resume, Retry Failed & Jadwal Opsional**:
   - Kursor `last_datestamp` dan `resumption_token` disimpan per halaman agar aman terhadap *timeout* atau jeda (`Pause`/`Resume`).
   - Rekaman gagal PDF (`PDF_INACCESSIBLE` / `FAILED`) dapat diulang terpisah via `/retry-failed`.
   - Penjadwalan berkala opsional (`PUT /api/oai/repositories/{id}/schedule`) dijalankan oleh worker latar belakang (`run_due_scheduled_harvests` di `worker.py`) dengan batas sopan (`max_records=15`, `max_downloads<=10`).

---

## 2. Integrasi Otomatis ke Korpus Pembanding Lokal & Provenance

- Setiap berkas PDF/teks penuh yang lolos ekstraksi dan deduplikasi (hash konten, DOI, URL kanonik, judul ternormalisasi) langsung diproses melalui `ingest_validated_upload(..., role="CORPUS")` sehingga:
  - Tokenisasi, segmentasi struktur, Winnowing fingerprint, dan MinHash LSH langsung diindeks dan *cache* LSH di-invalidasi otomatis (`invalidate_lsh_cache()`).
  - Dokumen langsung tersedia pada pemeriksaan plagiasi berikutnya dengan `include_local_corpus=True`.
- **Metadata Provenance Tersimpan pada `Document` & Diekspos via `/indexed-documents`:**
  - Universitas / institusi (`extra["university"]`)
  - Nama repositori (`extra["repository_name"]`)
  - Judul karya (`title`)
  - Penulis (`authors`)
  - Tahun publikasi (`year`)
  - DOI (`doi`)
  - URL asli (`url`, `canonical_url`)
  - Lisensi (`license`)
  - Waktu penarikan (`retrieved_at`)
- **Penegakan Strict Full-Text vs Metadata-Only:**
  - Terbukti pada uji mock (`test_advanced_filters_max_downloads_ojs_galley_and_local_corpus_provenance`) dan uji live IPB (`repository.ipb.ac.id`): entri yang hanya memiliki metadata atau gagal mengunduh PDF **tidak pernah** dimasukkan ke tabel `documents` dengan status terindeks dan **tidak pernah** menghasilkan kecocokan semu pada laporan plagiasi.
