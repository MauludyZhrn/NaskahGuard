# Katalog Komponen Pihak Ketiga & Agent Skills (Phase 9)

Dokumen ini mencatat seluruh komponen UI primitif (`shadcn/ui`), komponen animasi selektif (`Magic UI`), serta *Agent Skills* yang digunakan pada pengembangan NaskahGuard Phase 9.

## 1. Agent Skills di Workspace (`.agents/skills/`)

| Nama Skill | Sumber Resmi | Lisensi | Peran dalam NaskahGuard |
| :--- | :--- | :---: | :--- |
| `ui-ux-pro-max` | Workspace Design Intelligence | MIT | Pedoman utama sistem desain, palet warna akademik, kontras, dan aturan anti-pattern UX. |
| `shadcn` | `https://github.com/shadcn-ui/ui` | MIT | Standar komposisi komponen primitif aksesibel berbasis Radix UI & Tailwind CSS. |
| `magic-ui` | `https://github.com/magicuidesign/magicui` | MIT | Motion mikro selektif (`NumberTicker`, `BlurFade`) dengan dukungan penuh `prefers-reduced-motion`. |
| `scrapling-official` | `https://github.com/D4Vinci/Scrapling` | BSD-3-Clause | Referensi teknik parsing adaptif HTML/Markdown & evaluasi benchmark ekstraksi web. |
| `mineru` | OpenDataLab MinerU | Apache-2.0 | Referensi struktur ekstraksi dokumen akademik kompleks. |
| `scholar-search` | OpenAlex Scholar Skill | MIT | Referensi pencarian literatur ilmiah terbuka. |
| `tufte-data-viz` | Tufte Data Visualization | MIT | Prinsip *data-ink ratio* tinggi pada grafik analitik laporan. |

## 2. Komponen `shadcn/ui` (`frontend/src/components/ui/`)

Seluruh komponen dipasang melalui CLI resmi `npx shadcn@latest add` menggunakan konfigurasi [components.json](file:///d:/Projects/NaskahGuard/frontend/components.json) (lisensi **MIT**, berbasis `@radix-ui/*` berlisensi **MIT**):
- **Layout & Struktur**: `card.tsx`, `separator.tsx`, `collapsible.tsx`, `accordion.tsx`, `tabs.tsx`, `table.tsx`
- **Overlay & Konfirmasi**: `dialog.tsx` (detail atribusi sumber), `alert-dialog.tsx` (konfirmasi hapus dokumen/korpus/repositori), `tooltip.tsx` (ikon sidebar saat diciutkan), `dropdown-menu.tsx`
- **Umpan Balik & Form**: `alert.tsx`, `badge.tsx`, `skeleton.tsx`, `progress.tsx`, `button.tsx`, `input.tsx`, `select.tsx`

## 3. Komponen `Magic UI` Selektif (`frontend/src/components/ui/`)

Dipasang secara selektif (tanpa efek dekoratif berat seperti *globe*, *particles*, *meteors*, atau *rainbow*):
- `number-ticker.tsx` (`@magicui/number-ticker`, MIT + paket `motion` MIT): Digunakan pada angka ringkasan KPI dan Similarity Index dengan format lokal `id-ID` dan fallback instan ketika `prefers-reduced-motion: reduce` aktif.
- `blur-fade.tsx` (`@magicui/blur-fade`, MIT + paket `motion` MIT): Digunakan untuk transisi masuk halaman yang halus (`220ms`) dan dinonaktifkan otomatis pada mode `prefers-reduced-motion` serta tidak diterapkan pada teks *document viewer*.

## 4. Evaluasi Crawler Eksternal (Lingkungan Benchmark Terisolasi)

- **Playwright (`playwright` 1.65.2, Apache-2.0)**: Dipertahankan sebagai engine browser terisolasi produksi (`IsolatedPlaywrightExtractor`).
- **Crawl4AI (`crawl4ai` 0.9.6, Apache-2.0)** & **Scrapling (`scrapling` 0.5.1, BSD-3-Clause)**: Dievaluasi secara menyeluruh pada virtual environment benchmark terisolasi tanpa membebani dependensi utama produksi `backend/requirements.txt`.
