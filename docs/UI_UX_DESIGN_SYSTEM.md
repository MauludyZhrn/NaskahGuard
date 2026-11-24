# Sistem Desain UI/UX NaskahGuard (Phase 8)

Dokumen ini mendefinisikan sistem desain terpusat NaskahGuard yang dihasilkan menggunakan skill `ui-ux-pro-max` dengan arah desain **Professional Academic SaaS / Research Intelligence Platform**.

## 1. Design Tokens (`frontend/src/styles/tokens.css`)

| Token | Light Mode | Dark Mode | Kegunaan |
| :--- | :--- | :--- | :--- |
| `--primary` | `#1E3A5F` | `#60A5FA` | Aksi utama, indikator aktif, fokus navigasi |
| `--secondary` | `#334155` | `#94A3B8` | Teks sekunder & kontrol pendukung |
| `--accent` | `#B45309` | `#F59E0B` | Aksen peringatan terukur & sorotan analitik |
| `--bg` | `#F8FAFC` | `#0F172A` | Latar aplikasi (netral terang / charcoal slate) |
| `--surface` | `#FFFFFF` | `#1E293B` | Kartu, sidebar, panel viewer |
| `--surface-alt` | `#F1F5F9` | `#273549` | Permukaan sekunder, header tabel, dropzone |
| `--border` | `#E2E8F0` | `#334155` | Garis pemisah tipis |

### Warna Kategori Kemiripan (Konsisten di Seluruh Aplikasi)
- **Exact (`EXACT`)**: Merah (`#DC2626` / latar lembut `#FEE2E2`)
- **Near-Exact (`NEAR_EXACT`)**: Oranye (`#EA580C` / latar lembut `#FFEDD5`)
- **Lexical (`LEXICAL`)**: Kuning/Amber (`#CA8A04` / latar lembut `#FEF9C3`)
- **Kandidat Semantik (`SEMANTIC`)**: Biru (`#2563EB` / latar lembut `#DBEAFE`)
- **Dikecualikan (`EXCLUDED`)**: Abu-abu netral (`#64748B` / latar `#F1F5F9`)

## 2. Tipografi & Hierarki

- **Antarmuka (UI Sans)**: `Inter`, `Segoe UI`, `system-ui`, `sans-serif` dengan `tabular-nums` untuk seluruh angka metrik dan tabel.
- **Tampilan Dokumen Akademik & Grafik Analitik**: Serif (`Georgia`, `Cambria`, `Times New Roman`) agar teks naskah mudah dibaca terpisah dari kontrol UI.
- **Kode & Rumus**: Monospace (`JetBrains Mono`, `Consolas`) untuk rumus skor, DOI, dan kueri pencarian.

## 3. Tata Letak & Navigasi

- **Collapsible Sidebar** (`260px` diperluas / `72px` diciutkan):
  - Status tersimpan otomatis di `localStorage` (`ng_sidebar_collapsed`).
  - Saat diciutkan, hanya menampilkan ikon dengan atribut `title` & `aria-label` sebagai tooltip tanpa teks terpotong.
  - Pengelompokan menu yang dapat diciutkan independen: **Utama**, **Sumber**, **Analisis**, **Pengaturan**.
  - Pada layar tablet/mobile (`<= 1024px`), sidebar berubah menjadi *slide-over drawer* dengan *backdrop*.
- **Navigasi Tab Laporan**: 1 baris horizontal dapat digulir pada desktop (`.tabs-bar`) dan otomatis beralih ke `<select>` dropdown (`.tabs-mobile-select`) pada layar sempit.
- **Aksesibilitas**: Mendukung `prefers-reduced-motion`, navigasi keyboard (`tabIndex`, `aria-expanded`, `role="tablist"`), serta kontras WCAG AA pada Light & Dark Mode.
