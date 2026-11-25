# Laporan Quality Assurance Phase 10 (NaskahGuard)

Laporan ini mencatat seluruh hasil verifikasi aktual setelah implementasi Phase 10 (Redesign UI/UX Lengkap + Deteksi Tulisan AI Lokal).

---

## 1. Pengujian Backend & Regresi Plagiasi

| Pengujian | Perintah / Sumber | Hasil Teramati |
| :--- | :--- | :--- |
| **Suite Pytest Lengkap** | `backend/.venv/Scripts/python.exe -m pytest -v` (di `backend/`) | **36 passed, 1 skipped** (`test_live_internet_providers_explicit` hanya berjalan jika flag live diaktifkan). Termasuk seluruh 31 tes regresi Phase 1–9 dan 5 tes E2E/unit Phase 10 (`test_phase10_ai_detection.py`) termasuk migrasi SQLite Alembic `0003`. |
| **Benchmark Deteksi Plagiasi** | `backend/.venv/Scripts/python.exe benchmark/run_phase9_detection_benchmark.py` | **Precision 1.0000**, **Recall 1.0000**, **F1 1.0000**, **FPR 0.0000**, **FNR 0.0000** lintas 12 skenario ground-truth (`zero double counting: true`, `24,17 ms`). |

---

## 2. Pengujian & Kalibrasi Deteksi Tulisan AI

- **Runner**: `backend/.venv/Scripts/python.exe benchmark/run_phase10_ai_benchmark.py` (`benchmark/results/phase10_ai_benchmark.json`).
- **Split Ketat Bebas Kebocoran**: `train` (120 dokumen), `validation` (48 dokumen), `test` (72 dokumen topik & templat tak terlihat), dan `false_positive_stress` (5 kasus).
- **Performa Split `test` (n = 72)**:
  - Ambang keputusan produk (`AI_LIKELY >= 0,68`): **Precision `0,9062`**, **Recall `0,8056`**, **F1 `0,8529`**, **`strict_ai_likely_fpr = 0,0`** (`0` dokumen manusia dituduh `AI_LIKELY`).
  - Ambang biner `0,50`: **Precision `0,7692`**, **Recall `0,8333`**, **F1 `0,8000`**, **ROC-AUC `0,9537`**, **Brier `0,1023`**.
  - **Kecepatan rata-rata CPU**: `1,17 ms` per dokumen.
- **Kasus Ketahanan False Positive (`false_positive_stress`)**:
  - Hukum & regulasi formal ID (`fp_01`), abstrak IMRAD medis padat ID (`fp_02`), metode formal EN (`fp_03`), tulisan rapi tersunting ejaan ID (`fp_04`): seluruhnya lulus guardrail (0 false positive `AI_LIKELY`).
  - Teks terlalu singkat (`fp_05`, `< 80` kata): akurat menghasilkan **`INSUFFICIENT_DATA`** (*Tidak Cukup Bukti*).

---

## 3. Verifikasi Build Frontend, Emoji & Playwright E2E UI QA

| Pemeriksaan | Hasil Teramati |
| :--- | :--- |
| **Pemeriksaan Emoji (`frontend/src`)** | `EMOJI_HITS: 0` (seluruh ikon menggunakan `lucide-react`). |
| **TypeScript & Vite Build (`npm run build`)** | `tsc -b && vite build` **exit code 0** (`11,11s`, tanpa error tipe maupun build). |
| **Playwright UI QA (`benchmark/run_phase10_ui_qa.py`)** | **17/17 pengecekan rute/viewport LULUS** (`passed: true`, `console_errors: []`, `page_errors: []`, `bad_http: []`). |
| **Responsive Layout Checks** | `0` *horizontal overflow* di Desktop `1440×900` (15 rute), Tablet `768×1024`, dan Mobile `390×844`. |
| **Dark Mode Parity** | Terverifikasi `data-theme="dark"` aktif penuh dengan tombol & teks terbaca jelas ([17_dashboard_dark.png](screenshots/phase10_after/17_dashboard_dark.png)). |
| **Bukti Visual Sebelum & Sesudah** | 10 screenshot *before* di [docs/screenshots/phase10_before/](screenshots/phase10_before/) dan 19 screenshot *after* di [docs/screenshots/phase10_after/](screenshots/phase10_after/). |

### Temuan Visual yang Berhasil Diperbaiki Selama QA
1. Mengatasi bug *tablet overflow* (`768px`) pada kartu pilihan mode dan bar tombol unggah `NewCheckPage` dengan memindahkan breakpoint 3-kolom ke `lg:grid-cols-3`.
2. Mengatasi bug CSS Tailwind v3 tanpa `@tailwind base` (`--tw-translate-*` / `--tw-ring-*` belum terinisialisasi) yang menyebabkan laci navigasi mobile muncul di viewport `390px` dan border bawaan `<button>` muncul pada tab serta grup sidebar. Setelah perbaikan dan build ulang, verifikasi ulang Playwright menampilkan laci mobile tertutup rapi (`19_mobile_new_check.png`) dan komponen `Switch` berfungsi normal (`14_settings.png`).
