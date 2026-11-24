# THIRD_PARTY_NOTICES — NaskahGuard

Proyek **NaskahGuard** menggunakan dan merujuk pada komponen pihak ketiga open-source berikut. Seluruh lisensi asli dan atribusi dipertahankan.

## 1. Agent Skills Terpasang (`.agents/skills/`)

| Skill | Sumber Repositori | Lisensi | Catatan Penggunaan |
|---|---|---|---|
| `mineru` | https://github.com/nebutra/mineru-skill | MIT License (Copyright 2026 Nebutra) | Dipasang sebagai referensi parsing dokumen; **mode cloud tidak pernah dipanggil otomatis** oleh NaskahGuard tanpa persetujuan eksplisit pengguna. |
| `scholar-search` | https://github.com/dsebastien/ai-skill-scholar | MIT License (Copyright 2026 Sebastien Dubois) | Referensi pencarian sumber terbuka OpenAlex (tanpa API key, polite pool via email). |
| `tufte-data-viz` | https://github.com/caylent/tufte-data-viz | MIT License (Copyright 2026 Caylent) | Prinsip visualisasi data (rasio data-ink tinggi, label langsung, palet terang/gelap) diterapkan pada Recharts dan SVG. |
| `ui-ux-pro-max` | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | MIT License (Copyright 2024 Next Level Builder) | Panduan desain UI/UX, aksesibilitas (kontras WCAG), tipografi, dan tata letak responsif. |

## 2. Repositori Referensi Audit (`research/vendor/`, tidak didistribusikan)

- **Noplag Engine** (`NoplagLabs/noplag-engine`) — Apache License 2.0. Dijadikan acuan arsitektur Winnowing fingerprint, sentence-window chunking, retrieval kandidat, seed-and-extend alignment, interval merging, dan struktur adapter opsional.
- **AcademicGuard** (`sunilgentyala/academicguard`) — MIT License (Copyright 2026 AcademicGuard Contributors). Dijadikan referensi komplementer konsep Winnowing, MinHash/LSH, TF-IDF sentence similarity, dan Crossref title lookup.
- **Awesome Academic Skills** (`O0000-code/awesome-academic-skills`) — CC0 1.0 Universal. Digunakan sebagai direktori kurasi skill akademik.

## 3. Dependensi Runtime & Pengembangan Utama

Lihat rincian lengkap dan catatan kepatuhan lisensi (termasuk catatan khusus AGPL-3.0 untuk PyMuPDF) pada [docs/THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md).
