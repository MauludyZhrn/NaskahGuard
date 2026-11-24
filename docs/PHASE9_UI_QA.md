# Laporan QA UI/UX & Responsivitas 5 Viewport (Phase 9)

Skrip pengujian otomatis: [qa_ui_playwright.py](file:///d:/Projects/NaskahGuard/scripts/qa_ui_playwright.py)  
Hasil JSON terukur: [phase9_ui_qa.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase9_ui_qa.json)  
Direktori tangkapan layar: `docs/screenshots/phase9/`

## 1. Matriks Pengujian 5 Resolusi Layar

Seluruh pengujian dijalankan menggunakan Playwright Headless Chromium terhadap server backend FastAPI + bundel produksi `frontend/dist`:

| Resolusi Viewport | Kategori Perangkat | Rute Diuji | Horizontal Overflow | Navigasi Ganda Laporan |
| :--- | :--- | :--- | :---: | :---: |
| **`1600 × 900`** | Desktop Lebar | `/`, `/new-check`, `/reports/:id` | `false` (0px) | **0 Pelanggaran** (Hanya Tab Desktop) |
| **`1440 × 900`** | Desktop Standar | `/`, `/new-check`, `/discovery-monitor`, `/repositories`, `/analytics`, `/reports/:id` | `false` (0px) | **0 Pelanggaran** (Hanya Tab Desktop) |
| **`1280 × 800`** | Laptop | `/`, `/new-check`, `/reports/:id` | `false` (0px) | **0 Pelanggaran** (Hanya Tab Desktop) |
| **`768 × 1024`** | Tablet | `/`, `/new-check`, `/reports/:id` | `false` (0px) | **0 Pelanggaran** (Tab Scrollable) |
| **`390 × 844`** | Mobile | `/`, `/new-check`, `/discovery-monitor`, `/repositories`, `/analytics`, `/reports/:id` | `false` (0px) | **0 Pelanggaran** (Hanya Mobile Select) |

## 2. Verifikasi Interaksi & Perbaikan Utama Phase 9

1. **Fix 1 — Penghapusan Navigasi Ganda**: `duplicate_nav_violations: []`. Pada layar `> 640px` hanya `.tabs-bar` yang tampil; pada `<= 640px` hanya `.mobile-tab-select` yang tampil.
2. **Fix 2 — Ringkasan Skor Proporsional**: Gauge diperkecil secara proporsional (`128×74`) di dalam kartu skor kiri (berdampingan dengan Similarity Index, badge Kategori Operasional, Adjusted & Raw Similarity), sedangkan area kanan menampilkan grid 2×2 (`Eligible Words`, `Kata Cocok Unik`, `Sumber Berkontribusi`, `Full-Text Dibandingkan`).
3. **Fix 3 & 5 — Accordion Skor & Expand/Collapse**:
   - `formula_accordion_visible: true` ("Penjelasan Perhitungan Similarity" menampilkan rumus, nilai presisi sebelum pembulatan, resolusi overlap, dan tabel kontribusi sumber).
   - `expand_all_works: true` & `collapse_all_works: true`, dengan persistensi `localStorage` (`ng_report_open_accordions`) sementara ringkasan skor utama tetap terlihat di bagian atas.
4. **Fix 4 — 9 Kategori Transparansi Sumber**: Ditampilkan terpisah secara eksplisit tanpa mencampur metadata-only dengan full-text.
5. **Fix 6 — Sticky Viewer Toolbar, Paginasi & Dialog Detail Sumber**:
   - `viewer_sticky_toolbar_visible: true`
   - `source_detail_dialog_visible: true` (komponen `Dialog` dari `shadcn/ui` lengkap dengan `DialogTitle` & `DialogDescription`).
6. **Collapsible Sidebar & Tema**:
   - Lebar diperluas `260px` → diciutkan `72px` → diperluas kembali `260px`, dengan `persisted_after_reload: true` serta `Tooltip` Radix saat diciutkan.
   - `dark_mode_applied: true`, `console_errors: []`, `page_errors: []`.

## 3. Daftar Tangkapan Layar (`docs/screenshots/phase9/`)

- [01_dashboard_light.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/01_dashboard_light.png) — Dasbor utama (Light Mode, `1440×900`)
- [02_new_check_light.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/02_new_check_light.png) — Pemeriksaan Baru 4 bagian terstruktur (`1440×900`)
- [03_discovery_monitor_light.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/03_discovery_monitor_light.png) — Monitor Penemuan & tombol Uji Konektivitas Provider (`1440×900`)
- [04_report_overview_light.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/04_report_overview_light.png) — Laporan Kemiripan dengan layout proporsional & tanpa navigasi ganda (`1440×900`)
- [05_report_compare_viewer.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/05_report_compare_viewer.png) — Perbandingan Dokumen dua panel dengan sticky toolbar (`1440×900`)
- [06_report_overview_dark.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/06_report_overview_dark.png) — Laporan Kemiripan dalam Dark Mode (`1440×900`)
- [07_report_mobile_390.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase9/07_report_mobile_390.png) — Laporan Kemiripan responsif pada layar Mobile (`390×844`)
