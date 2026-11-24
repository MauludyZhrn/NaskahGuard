# AGENT_REPORT — NaskahGuard

Laporan log pengembangan proyek **NaskahGuard** (Academic Plagiarism & Similarity Detection Intelligence System).

## Ringkasan Pelaksanaan per Fase

### Fase 0 — Riset, Audit Repositori, Skill, dan Dokumentasi (Selesai)
- Inisialisasi repositori Git di `d:\Projects\NaskahGuard`, penambahan `.gitignore` dan `LICENSE` (Apache-2.0).
- Audit 7 repositori referensi di `research/vendor/` (`noplag-engine`, `academicguard`, `awesome-academic-skills`, `mineru-skill`, `ai-skill-scholar`, `tufte-data-viz`, `ui-ux-pro-max-skill`) — terdokumentasi di [docs/research/REPO_AUDIT.md](docs/research/REPO_AUDIT.md).
- Instalasi 4 Agent Skills ke `.agents/skills/`: `mineru`, `scholar-search`, `tufte-data-viz`, `ui-ux-pro-max`.
- Pembuatan [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) serta 11 dokumen arsitektur/spesifikasi di `docs/` lengkap dengan diagram Mermaid (arsitektur, data flow, document processing, similarity detection, source discovery, scoring, dan ERD).

### Fase 1 — Fondasi Backend, DB, dan Ingesti Dokumen (Selesai)
- Konfigurasi Pydantic (`backend/app/config.py`) dengan `APP_NAME` yang dapat diubah melalui `NG_APP_NAME` dan `VITE_APP_NAME`.
- Skema database SQLAlchemy 2 + Alembic (`backend/alembic/versions/0001_initial.py`) mendukung SQLite WAL (default Windows siap pakai) dan PostgreSQL (`pg_trgm` GIN trigram + opsi `pgvector`).
- Pipeline ingesti (`backend/app/ingestion/`): validasi ekstensi/MIME/magic bytes/ukuran streaming, anti path-traversal, ekstraksi PDF (`PyMuPDF` + fallback `pypdf` non-AGPL), fallback OCR lokal opsional (`Tesseract`), `python-docx` (dengan estimasi pemisah halaman), TXT (`utf-8-sig`/`cp1252`), normalisasi Unicode tanpa mengubah teks asli, tokenisasi offset karakter eksak, segmentasi kalimat/paragraf, deteksi bahasa ID/EN/mixed, serta deteksi zona (`BODY`, `BIBLIOGRAPHY`, `TOC`, `COVER`) & bab.
- CLI (`backend/app/cli.py`: `import-corpus`, `purge-retention`), worker antrean latar belakang (`backend/app/worker.py`), retensi data, audit log, rate limiter, dan validasi keamanan startup.

### Fase 2 — Mesin Similarity Multi-Lapis & Scoring (Selesai)
- `backend/app/engine/`: hash 64-bit Blake2b (`hashing.py`), Winnowing `k=5, w=4` + DF stop-gram filtering (`winnowing.py`), MinHash `128` permutasi + LSH (`minhash_lsh.py`), Lapisan 1 Exact Matching (`exact.py`), Lapisan 2 Near-Exact seed-and-extend + `SequenceMatcher` konservatif (`near_exact.py`), Lapisan 3 Lexical TF-IDF `char_wb (3,5)` + BM25 (`lexical.py`), Lapisan 4 Semantic opsional (`semantic.py`), masker pengecualian (`exclusions.py`), atribusi eksklusif anti-hitung-ganda (`attribution.py`), perhitungan `SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%` (`scoring.py`), dan adapter loopback Noplag Engine (`noplag_adapter.py`).

### Fase 3 — Penemuan Sumber Terbuka (Selesai)
- `backend/app/sources/`: antarmuka `SourceProvider` (`base.py`), `LocalCorpusProvider`, `OpenAlexProvider`, `CrossrefProvider` (`METADATA_ONLY`), `ArxivProvider` (jeda >= 3 detik), `PubMedCentralProvider` (metadata E-utilities), serta pemeriksaan `robots.txt` (`robots.py`). Pencarian eksternal nonaktif secara default dan hanya mengirim judul + maksimal 10 frasa kunci TF-IDF.

### Fase 5 — Pelaporan Interaktif & Antarmuka Frontend (Selesai)
- Pelaporan backend (`backend/app/reports/`): JSON, HTML mandiri dengan grafik SVG, dan PDF menggunakan ReportLab (`pdf_report.py`) lengkap dengan identitas pemeriksaan, metodologi, grafik, daftar sumber, cuplikan, alur data aktual, dan pernyataan keterbatasan.
- Frontend React + TypeScript + Vite (`frontend/`) berbahasa Indonesia penuh (mode terang & gelap, responsif, prinsip Tufte & aksesibilitas): Dasbor, Pemeriksaan Baru, Riwayat Pemeriksaan, Pustaka Dokumen, Korpus Sumber, Laporan Kemiripan, Detail Laporan 6 tab (Ringkasan, Perbandingan Dokumen dua panel sinkron, Sumber, Analitik Recharts, Alur Pemeriksaan 12 tahap data aktual, Ekspor), dan Pengaturan.

### Fase 6 — Pengujian, Benchmark, & Verifikasi (Selesai)
- **Pytest (`backend/.venv/Scripts/python.exe -m pytest -q`)**: **16 passed** (validasi keamanan/magic-bytes/traversal, ingesti PDF/DOCX/TXT + invarian offset, Winnowing, Exact, Near-Exact, overlap attribution, exclusions, mock provider adapters, end-to-end API termasuk ekspor PDF & penghapusan menyeluruh, serta penegakan `API_TOKEN`).
- **Benchmark 12 Kasus Sintetis (`backend/.venv/Scripts/python.exe benchmark/run_benchmark.py`)**:
  - `EXACT`: Precision = **1.0000**, Recall = **1.0000**, F1 = **1.0000**, FPR = **0.0000**, FNR = **0.0000**.
  - `NEAR_EXACT` (gabungan): Precision = **0.9805**, Recall = **0.9934**, F1 = **0.9869**, FPR = **0.0333**, FNR = **0.0066**.
  - `LEXICAL`: Precision = **1.0000**, Recall = **1.0000**, F1 = **1.0000**, FPR = **0.0000**, FNR = **0.0000**.
  - Rincian tersimpan di `benchmark/results/latest.json` dan [docs/TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md).
- **Smoke Test (`backend/.venv/Scripts/python.exe scripts/smoke_test.py`)**: Lulus (`Report=NG-20261124-0001 SI=31.31% MatchedWords=31/99 PDFBytes=6362`).
- **Live Server Probe**: `uvicorn app.main:app --host 127.0.0.1 --port 8019` mengembalikan HTTP 200 JSON valid pada `/api/health`.
- **Frontend Build (`tsc --noEmit` & `npm run build`)**: Lulus tanpa error.

## Keterbatasan Lingkungan & Implementasi Saat Ini
1. **PostgreSQL, Tesseract, dan Docker tidak terpasang** di mesin host; seluruh eksekusi dan verifikasi berjalan di atas SQLite (mode WAL). Skema PostgreSQL (`pg_trgm` GIN) telah disiapkan pada migrasi Alembic tetapi belum diuji terhadap server PostgreSQL hidup.
2. **Noplag Engine** diaudit sebagai referensi arsitektur dan disediakan adapter HTTP khusus loopback (`app/engine/noplag_adapter.py`), namun tidak dijalankan secara langsung karena membutuhkan PostgreSQL + Python 3.12+.
3. **OCR & Modul Semantik** tidak diaktifkan secara default karena membutuhkan biner Tesseract dan paket berat `sentence-transformers` (`backend/requirements-optional.txt`); sistem melaporkan status ketersediaan secara jujur di API, UI, dan PDF.
4. **Adapter PubMed Central (PMC)** saat ini menyediakan pencarian metadata E-utilities (`METADATA_ONLY`); pengambilan arsip penuh XML/PDF OA subset PMC belum diimplementasikan.
5. **Nomor Halaman DOCX** diestimasi berdasarkan pemisah halaman eksplisit OOXML karena DOCX tidak menyimpan tata letak halaman tetap.
6. **Lisensi PyMuPDF (AGPL-3.0)** didokumentasikan pada [docs/THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md) dan dapat dialihkan ke `NG_PDF_BACKEND=pypdf` (BSD-3-Clause).

## Langkah Selanjutnya yang Disarankan
1. Uji migrasi dan performa indeks GIN `pg_trgm` serta `bigint[]` pada instance PostgreSQL 15+.
2. Pasang Tesseract OCR (`ind+eng`) dan `sentence-transformers` bila membutuhkan pemindaian PDF gambar dan pencarian kandidat semantik Lapisan 4.
3. Lakukan evaluasi lanjutan pada korpus publik beranotasi besar seperti PAN-PC-11 atau repositori ilmiah lokal kampus.
