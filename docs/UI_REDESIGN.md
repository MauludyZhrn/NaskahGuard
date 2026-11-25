# Redesign UI/UX NaskahGuard Phase 10

Dokumen ini merangkum pembaruan menyeluruh antarmuka NaskahGuard menggunakan panduan **UI/UX Pro Max** (gaya *Swiss Modernism 2.0*), komponen primitif **shadcn/ui**, **Tailwind CSS**, **Magic UI** selektif, serta **Lucide React** sebagai satu-satunya pustaka ikon.

---

## 1. Masalah Antarmuka Sebelum Redesign (`phase10_before/`)

Dari hasil inspeksi tangkapan layar [docs/screenshots/phase10_before/](screenshots/phase10_before/):
1. Hierarki visual halaman berbeda-beda antara halaman lama (CSS manual `.card`/`.btn` bercampur komponen shadcn parsial).
2. Istilah teknis seperti *Similarity Index*, *Eligible Words*, *Matched Words*, *Fulltext Compared*, *Metadata Only*, dan *Semantic Candidate* menyulitkan pembaca non-teknis.
3. Belum tersedia alur khusus **Deteksi Tulisan AI**, **Laporan Gabungan**, **Analitik AI**, maupun **Manajemen Model**.
4. Pada kondisi tertentu di mode gelap dan tablet, elemen `<button>` dan `<a href>` bawaan terpengaruh `preflight: false` Tailwind sehingga muncul border atau garis bawah tautan yang tidak diinginkan.

---

## 2. Arsitektur UI/UX Baru (`phase10_after/`)

### A. Standar Komponen & Ikon
- **Komponen Utama**: `Card`, `Button`, `Badge`, `Table`, `Tabs`, `Accordion`, `Dialog`, `AlertDialog`, `Alert`, `Progress`, `Tooltip`, `Switch`, `Label`, `Input`, `Skeleton`, dan `Separator`.
- **Ikon**: 100% **`lucide-react`** (`size-4` / `size-3.5` konsisten). Pemeriksaan otomatis terhadap seluruh berkas `frontend/src` memastikan **0 penggunaan emoji sebagai ikon**.
- **Tema Terang & Gelap**: Menggunakan variabel semantik `--tw-*` dan token warna `tokens.css` (`#1E3A5F` Navy Akademik pada terang, kontras teks terkalibrasi pada gelap), serta mematuhi `prefers-reduced-motion: reduce`.
- **Reset Non-Destruktif (`theme.css`)**: Menginisialisasi variabel `--tw-translate-*`, `--tw-ring-*`, `--tw-shadow*`, serta menghapus garis bawah default tautan dan border `<button>` browser agar seluruh komponen shadcn/Radix tampil tajam baik di Light maupun Dark Mode.

### B. Penyederhanaan Navigasi 5 Kelompok
Navigasi ganda pada desktop dihilangkan total; bilah samping responsif (`260px` / ciut `70px`) dan laci mobile (`md:hidden`) hanya menampilkan satu sumber menu:
1. **UTAMA**: Dasbor (`/`), Pemeriksaan Baru (`/new-check`), Riwayat Pemeriksaan (`/history`)
2. **PEMERIKSAAN**: Deteksi Plagiasi (`/plagiarism-checks`), Deteksi Tulisan AI (`/ai-checks`), Laporan Gabungan (`/combined-reports`)
3. **SUMBER**: Pustaka Dokumen (`/documents`), Korpus Sumber (`/corpus`), Monitor Penemuan (`/discovery-monitor`), Repositori Akademik (`/repositories`)
4. **ANALISIS**: Analitik Plagiasi (`/analytics`), Analitik AI (`/analytics/ai`)
5. **PENGATURAN**: Pengaturan (`/settings`), Manajemen Model (`/models`)

### C. Penyederhanaan Istilah Bahasa Indonesia

| Istilah Teknis Lama | Istilah Sederhana Phase 10 | Penjelasan Tambahan (`Tooltip`) |
| :--- | :--- | :--- |
| `Similarity Index` | **Indeks Kemiripan** | Persentase kata pada naskah bersih yang cocok dengan sumber pembanding. |
| `Eligible Words` | **Jumlah Kata yang Diperiksa** | Kata inti di luar daftar pustaka atau bagian yang dikecualikan. |
| `Matched Words` | **Kata yang Cocok** | Jumlah kata unik yang teridentifikasi mirip dengan sumber. |
| `Fulltext Compared` | **Dokumen Sumber yang Dibandingkan** | Sumber pembanding berteks lengkap yang berhasil diunduh dan diperiksa. |
| `Metadata Only` | **Hanya Informasi Referensi** | Sumber hanya mengembalikan judul/abstrak tanpa isi penuh. |
| `Contribution` | **Kontribusi Sumber** | Porsi unik kata cocok yang disumbangkan sumber tersebut. |
| `Semantic Candidate` | **Kandidat Kemiripan Makna** | Segmen dengan potensi kesamaan makna untuk ditinjau manual. |

### D. Perbandingan Tangkapan Layar Sebelum & Sesudah
- **Dasbor Utama**: Sebelum ([01_dashboard.png](screenshots/phase10_before/01_dashboard.png)) vs Sesudah Terang ([01_dashboard.png](screenshots/phase10_after/01_dashboard.png)) & Gelap ([17_dashboard_dark.png](screenshots/phase10_after/17_dashboard_dark.png))
- **Pemeriksaan Baru (3 Mode)**: Sebelum ([02_new_check.png](screenshots/phase10_before/02_new_check.png)) vs Sesudah Desktop ([02_new_check.png](screenshots/phase10_after/02_new_check.png)), Tablet ([18_tablet_new_check.png](screenshots/phase10_after/18_tablet_new_check.png)), Mobile ([19_mobile_new_check.png](screenshots/phase10_after/19_mobile_new_check.png))
- **Laporan Terpisah (Plagiasi vs AI)**: [11_report_detail_plagiarism.png](screenshots/phase10_after/11_report_detail_plagiarism.png) dan [16_report_detail_ai_tab.png](screenshots/phase10_after/16_report_detail_ai_tab.png)
- **Halaman Baru AI**: [13_analytics_ai.png](screenshots/phase10_after/13_analytics_ai.png) dan [15_models.png](screenshots/phase10_after/15_models.png)
