# Keamanan dan Privasi — NaskahGuard

## 1. Privasi Dokumen (Local-First)
- **Tidak Ada Pengiriman Otomatis ke Cloud**: Seluruh ekstraksi teks (PyMuPDF/pypdf, python-docx, Tesseract lokal opsional) dan pencocokan terhadap korpus lokal berjalan 100% di mesin lokal.
- **Sumber Eksternal Off by Default**: Pencarian sumber eksternal (`OpenAlex`, `Crossref`, `arXiv`, `PMC`) hanya berjalan apabila diaktifkan secara eksplisit per pemeriksaan. Kueri yang dikirim hanya berisi judul dan hingga 10 frasa kunci TF-IDF—**tidak pernah teks penuh dokumen**.
- **Tidak Ada Pelatihan Model**: Dokumen pengguna tidak pernah digunakan untuk melatih model AI atau dibagikan ke pihak ketiga.

## 2. Keamanan Aplikasi & Berkas
- **Validasi Tipe & Magic Bytes**: Ekstensi file diverifikasi terhadap magic bytes aktual (`%PDF-` untuk PDF, ZIP `PK\x03\x04` dengan `word/document.xml` tanpa makro `.docm` untuk DOCX, serta pemeriksaan biner NUL/encoding untuk TXT).
- **Pembatasan Ukuran Streaming**: Unggahan dibaca bertahap (*chunked*) dan langsung ditolak (`413 Payload Too Large`) jika melebihi `MAX_UPLOAD_MB` (default 50 MB).
- **Pencegahan Path Traversal**: Nama file asli disanitasi (`[\w\-. ]`, maksimal 150 karakter) hanya untuk tampilan. Penyimpanan fisik menggunakan UUID, dan setiap pembacaan/penghapusan berkas memverifikasi bahwa path teresolusi berada di dalam `STORAGE_DIR`.
- **Proteksi Jaringan & Autentikasi**:
  - `HOST` default adalah `127.0.0.1` (loopback).
  - Backend **menolak startup** jika `HOST` bukan alamat loopback sementara `API_TOKEN` kosong.
  - CORS hanya mengizinkan origin lokal antarmuka frontend.
  - Rate limiting *sliding-window* berbasis IP diterapkan pada endpoint `POST` sensitif.
- **Keamanan Crawler & Pencegahan SSRF (Phase 7)**:
  - `app/sources/ssrf.py` membatasi skema hanya `http`/`https`, menolak `localhost`, host `.local`/`.internal`, alamat metadata cloud (`169.254.169.254`, `metadata.google.internal`), serta memvalidasi hasil resolusi DNS agar bukan IP privat, loopback, atau link-local.
  - Setiap lompatan *HTTP redirect* divalidasi ulang terhadap SSRF (maksimal 5 redirect), mematuhi `robots.txt`, menerapkan jeda per domain (`CRAWL_DOMAIN_DELAY_SEC`), batas ukuran unduhan (`MAX_EXTERNAL_DOWNLOAD_MB`), dan *exponential backoff*.
  - **Isolasi Playwright Chromium**: Browser crawler dijalankan pada konteks ephemeral terisolasi tanpa profil pengguna, tanpa cookies pribadi, tanpa password/sesi login, dan menyaring sub-request melalui route SSRF guard.
- **Keamanan Internal Adapter Noplag**: `NOPLAG_ENGINE_URL` divalidasi agar hanya mengarah ke host loopback (`127.0.0.1`, `localhost`, `::1`).
- **Retensi & Penghapusan Menyeluruh**: `DELETE /api/documents/{id}` menghapus berkas fisik, JSON ekstraksi, segmen, fingerprint, pemeriksaan, dan hasil match secara permanen. `RETENTION_DAYS > 0` memicu pembersihan otomatis dokumen submission kedaluwarsa saat startup dan berkala setiap 24 jam.
- **Audit Logging**: Setiap unggahan, pemeriksaan, penghapusan, perubahan pengaturan, dan kegagalan otentikasi dicatat ke `audit_logs`.
