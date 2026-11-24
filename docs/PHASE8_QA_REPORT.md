# Laporan QA Phase 8 — UI/UX, Backend & Benchmark

Tanggal verifikasi: Phase 8 Final Verification  
Skrip QA otomatis: [qa_ui_playwright.py](file:///d:/Projects/NaskahGuard/scripts/qa_ui_playwright.py)  
Hasil JSON QA UI: [phase8_ui_qa.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase8_ui_qa.json)

## 1. Ringkasan Hasil Pengujian

| Kategori Pengujian | Perintah / Skrip | Hasil |
| :--- | :--- | :--- |
| Unit & Integration Test Backend | `backend\.venv\Scripts\python.exe -m pytest -v` | **27 / 27 PASSED** (`5.64s`) |
| TypeScript Check & Vite Production Build | `tsc --noEmit` & `npm run build` | **EXIT 0** (tanpa error) |
| Phase 8 Search Benchmark | `benchmark\run_phase8_search_benchmark.py` | **EXIT 0** (`P@5=0.80`, `R@5=1.00`, `0` bib leak) |
| Automated Playwright UI/UX QA | `scripts\qa_ui_playwright.py` | **EXIT 0** (semua asersi lolos) |

## 2. Detail Verifikasi Playwright Headless Chromium

Pengujian dijalankan terhadap backend FastAPI sementara (SQLite terisolasi) dan bundel produksi `frontend/dist`:

1. **Zero Horizontal Overflow**:
   - Desktop (`1280×800`): `/`, `/new-check`, `/discovery-monitor`, `/repositories`, `/analytics`, `/reports/<id>` — semuanya `horizontal_overflow: false`.
   - Tablet (`768×1024`): `/`, `/new-check`, `/reports/<id>` — semuanya `horizontal_overflow: false`.
2. **Collapsible Sidebar & Persistensi**:
   - Lebar diperluas: `260px`
   - Lebar diciutkan: `72px`
   - Tetap tersimpan setelah muat ulang halaman (`persisted_after_reload: true`).
3. **Transparansi Skor Laporan**:
   - Accordion `"Bagaimana skor dihitung?"` pada `/reports/<id>` berhasil dibuka dan menampilkan rumus nyata backend (`formula_accordion_visible: true`).
4. **Tema Gelap (Dark Mode)**:
   - Pengalih mode gelap menerapkan `data-theme="dark"` secara konsisten (`dark_mode_applied: true`).
5. **Kebersihan Runtime**:
   - `console_errors: []` (0 error)
   - `page_errors: []` (0 uncaught exception)

## 3. Catatan Keterbatasan Lingkungan Uji

- Docker, PostgreSQL, dan Tesseract OCR tidak terpasang pada host Windows ini; seluruh pengujian berjalan pada arsitektur standar Local-First SQLite + PyMuPDF + Playwright Chromium terisolasi.
- Pengujian provider eksternal dilakukan secara deterministik offline (mock transport); konektivitas internet live provider bergantung pada jaringan pengguna saat aplikasi dijalankan.
