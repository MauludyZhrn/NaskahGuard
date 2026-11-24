# Lisensi Pihak Ketiga — NaskahGuard

NaskahGuard sendiri dilisensikan di bawah **Apache License 2.0** (lihat berkas `LICENSE`).

## 1. Perhatian Khusus: PyMuPDF (AGPL-3.0)
- **PyMuPDF (`pymupdf`)** berlisensi **GNU Affero General Public License v3.0 (AGPL-3.0)** untuk penggunaan open-source.
- **Implikasi Hukum**: Apabila NaskahGuard dimodifikasi dan dijalankan sebagai layanan jaringan publik atau didistribusikan dengan `pymupdf` aktif tanpa lisensi komersial Artifex, ketentuan copyleft AGPL-3.0 mewajibkan penyediaan kode sumber lengkap aplikasi kepada pengguna jaringan.
- **Mitigasi Arsitektural**: NaskahGuard menyediakan opsi konfigurasi `PDF_BACKEND=pypdf` (menggunakan `pypdf` berlisensi **BSD-3-Clause**) agar pengguna yang menginginkan distribusi non-AGPL dapat menonaktifkan `pymupdf` sepenuhnya tanpa mengubah kode aplikasi.

## 2. Daftar Dependensi Python Backend

| Paket | Lisensi | Peran |
|---|---|---|
| `fastapi` | MIT | Kerangka kerja REST API |
| `uvicorn` | BSD-3-Clause | Server ASGI |
| `sqlalchemy` | MIT | ORM & koneksi SQLite/PostgreSQL |
| `alembic` | MIT | Migrasi skema basis data |
| `pydantic`, `pydantic-settings` | MIT | Validasi data & konfigurasi env |
| `python-multipart` | Apache-2.0 | Parsing unggahan multipart |
| `pymupdf` | **AGPL-3.0** | Ekstraktor PDF utama (opsional via `PDF_BACKEND`) |
| `pypdf` | BSD-3-Clause | Ekstraktor PDF alternatif non-AGPL |
| `python-docx` | MIT | Ekstraktor dokumen DOCX |
| `numpy` | BSD-3-Clause | Komputasi array numerik |
| `scikit-learn` | BSD-3-Clause | TF-IDF & cosine similarity |
| `datasketch` | MIT | MinHash & LSH |
| `rank-bm25` | Apache-2.0 | Ranking kandidat BM25 |
| `httpx` | BSD-3-Clause | Klien HTTP untuk adapter sumber resmi |
| `jinja2` | BSD-3-Clause | Template laporan HTML mandiri |
| `reportlab` | BSD-3-Clause | Pembuatan laporan PDF |
| `beautifulsoup4` | MIT | Pembersihan boilerplate HTML & ekstraksi artikel web |
| `defusedxml` | PSF-2.0 | Parsing aman XML JATS/TEI/OAI-PMH (anti-XXE) |
| `playwright` | Apache-2.0 | Browser crawler terisolasi (Chromium) untuk halaman web JS |
| `pytest` (dev) | MIT | Kerangka uji otomatis |
| `pytesseract` (opsional) | Apache-2.0 | Pembungkus Tesseract OCR (biner Tesseract berlisensi Apache-2.0) |
| `sentence-transformers` (opsional) | Apache-2.0 | Embedding semantik multibahasa |
| `psycopg` (opsional) | LGPL-3.0 | Driver PostgreSQL 3 |

## 3. Daftar Dependensi Frontend

| Paket | Lisensi | Peran |
|---|---|---|
| `react`, `react-dom` | MIT | Pustaka antarmuka pengguna |
| `react-router-dom` | MIT | Navigasi halaman SPA |
| `recharts` | MIT | Visualisasi grafik analitik |
| `lucide-react` | ISC | Ikon vektor UI |
| `vite`, `@vitejs/plugin-react`, `typescript` | MIT / Apache-2.0 | Bundler & compiler TypeScript |


---

## Tambahan Dependensi & Komponen Phase 9

### Frontend (`frontend/package.json` & `src/components/ui/`)
- `tailwindcss` (`^3.4.17`), `postcss`, `autoprefixer` — **MIT License**
- `@radix-ui/react-*` (`accordion`, `alert-dialog`, `collapsible`, `dialog`, `dropdown-menu`, `progress`, `select`, `separator`, `slot`, `tabs`, `tooltip`) — **MIT License**
- `class-variance-authority` — **Apache-2.0 License**
- `clsx`, `tailwind-merge` — **MIT License**
- `motion` (`^12.0.0`, untuk komponen Magic UI `NumberTicker` & `BlurFade`) — **MIT License**
- Komponen kode sumber `shadcn/ui` & `Magic UI` (`number-ticker.tsx`, `blur-fade.tsx`) — **MIT License**

### Agent Skills & Evaluasi Benchmark (Non-Produksi)
- `shadcn` skill (`shadcn-ui/ui`) — **MIT License**
- `magic-ui` skill (`magicuidesign/magicui`) — **MIT License**
- `scrapling-official` skill & paket evaluasi `scrapling` (`D4Vinci/Scrapling`) — **BSD-3-Clause License**
- Paket evaluasi benchmark terisolasi `crawl4ai` (`unclecode/crawl4ai`) — **Apache-2.0 License**
