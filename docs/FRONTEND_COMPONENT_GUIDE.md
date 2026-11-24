# Panduan Komponen Frontend NaskahGuard (Phase 8)

Frontend dibangun dengan React 18, TypeScript, Vite, Lucide Icons, dan Recharts. Seluruh teks antarmuka menggunakan **Bahasa Indonesia**.

## 1. Struktur File Utama

- **Styling & Tokens**:
  - [tokens.css](file:///d:/Projects/NaskahGuard/frontend/src/styles/tokens.css): Variabel warna, radius, bayangan, tipografi, dan tema Light/Dark.
  - [theme.css](file:///d:/Projects/NaskahGuard/frontend/src/styles/theme.css): Layout aplikasi, collapsible sidebar, tab responsif, accordion, skeleton loader, dan viewer dua panel.
- **Utilitas**:
  - [format.ts](file:///d:/Projects/NaskahGuard/frontend/src/utils/format.ts): `formatDuration` (detik -> format manusiawi ID) dan `formatMs` (milidetik -> `ms` / `dtk`).
- **Komponen Bersama**:
  - [Layout.tsx](file:///d:/Projects/NaskahGuard/frontend/src/components/Layout.tsx): Shell aplikasi dengan collapsible sidebar (`260px`/`72px`), persistensi `localStorage`, mobile drawer + backdrop, dan pengalih Light/Dark Mode.
  - [SimilarityGauge.tsx](file:///d:/Projects/NaskahGuard/frontend/src/components/SimilarityGauge.tsx): Gauge SVG skor kemiripan dengan ambang rendah/tinggi.
  - [ProcessFlowchart.tsx](file:///d:/Projects/NaskahGuard/frontend/src/components/ProcessFlowchart.tsx): Diagram alur pemeriksaan berbasis angka aktual tiap tahap.

## 2. Halaman & Rute (`frontend/src/App.tsx`)

| Rute | Komponen | Fungsi Utama |
| :--- | :--- | :--- |
| `/` | `DashboardPage` | Ringkasan KPI, grafik tren skor, laporan terbaru, aktivitas |
| `/new-check` | `NewCheckPage` | 4 bagian terstruktur: Unggah, Pengecualian, Pencarian Eksternal (`QUICK/BALANCED/DEEP` + status provider), Pengaturan Lanjutan (accordion) |
| `/history` | `HistoryPage` | Daftar riwayat pemeriksaan |
| `/documents` | `DocumentsPage` | Pustaka dokumen yang diunggah |
| `/corpus` | `CorpusPage` | Manajemen korpus pembanding lokal |
| `/discovery-monitor` | `DiscoveryMonitorPage` | Dasbor kesehatan provider, akuisisi URL, dan linimasa kueri |
| `/repositories` | `RepositoriesPage` | Registrasi, verifikasi, dan panen OAI-PMH repositori akademik |
| `/reports` | `ReportsListPage` | Indeks seluruh laporan selesai |
| `/reports/:checkId` | `ReportDetailPage` | Detail laporan 8 tab, accordion "Bagaimana skor dihitung?", 9 metrik sumber terpisah, viewer perbandingan |
| `/analytics` | `AnalyticsOverviewPage` | Analitik lintas pemeriksaan, korpus, dan performa provider |
| `/settings` | `SettingsPage` | Konfigurasi pengecualian default, ambang kategori, dan kebijakan retensi |
