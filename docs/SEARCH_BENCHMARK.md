# Benchmark Pencarian & Deteksi Kemiripan (Phase 8)

Skrip benchmark: [run_phase8_search_benchmark.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase8_search_benchmark.py)  
Hasil JSON: [phase8_search_benchmark.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase8_search_benchmark.json)

## 1. Pemisahan Mode Pengujian (Transparansi)

- **Mode yang dieksekusi**: `offline_deterministic_integration` (deterministik lokal, dapat direproduksi tanpa ketergantungan jaringan eksternal).
- **Status Live Internet Providers**: `live_internet_providers_tested: false`. Benchmark ini **tidak** mengklaim hasil live internet; performa live provider (OpenAlex, Europe PMC, arXiv, Crossref, SearXNG) bergantung pada konektivitas jaringan host dan rate limit masing-masing layanan.

## 2. Hasil Pengukuran Aktual

### A. Pembangkitan Kueri Multi-Bab
| Profil | Jumlah Kueri | Bab / Bagian Tercakup | Jenis Kueri | Kebocoran Daftar Pustaka |
| :--- | :---: | :---: | :---: | :---: |
| `QUICK` | 8 | 5 | 5 jenis | Tidak (`false`) |
| `BALANCED` | 24 | 8 | 7 jenis | Tidak (`false`) |
| `DEEP` | 30 (batas teks uji) | 8 | 7 jenis | Tidak (`false`) |

### B. Deduplikasi & Kualitas Peringkat Kandidat
- **Deduplikasi**: 7 kandidat masukan -> 6 kandidat unik (1 duplikat lintas provider dengan DOI sama & parameter `utm_source` dihapus; `canonical_url_check: true`).
- **Precision@5**: `0.80` (seluruh 4 kandidat relevan menempati peringkat 1–4).
- **Recall@5**: `1.00` (100% kandidat relevan ditemukan di top-5).
- **Pemisahan Kandidat Tidak Relevan**: Kedua kandidat tidak relevan (`irr-1`, `irr-2`) memperoleh skor `0.0` dengan label `UNRELATED`.

### C. Deteksi Kemiripan & Latensi
- **Exact spans terdeteksi**: 2 rentang
- **Kata cocok / kata eligible**: `36 / 210` (`17.14%`)
- **Rumus**: `SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%`
- **Total waktu eksekusi benchmark**: `23.64 ms`
