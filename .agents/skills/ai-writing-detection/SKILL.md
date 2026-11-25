---
name: ai-writing-detection
description: >-
  Guidelines and architecture patterns for local-first AI writing detection
  inside NaskahGuard (Bahasa Indonesia and English academic prose). Covers
  benchmark-driven calibration, Windows CPU/RAM deployment constraints,
  stylometric + n-gram entropy + optional local transformer inference,
  uncertainty bounds, false-positive guardrails, and strict separation from
  plagiarism similarity scores.
allowed-tools: Read, Glob, Grep
---

# AI Writing Detection Skill (NaskahGuard)

Gunakan skill ini saat merancang, mengkalibrasi, mengaudit, atau menampilkan **Deteksi Tulisan AI** di NaskahGuard.

> **Prinsip Etika & Akurasi Utama:**
> 1. Deteksi tulisan AI bersifat **probabilistik / indikatif**, BUKAN bukti hukum atau vonis pelanggaran akademik.
> 2. Skor AI **TIDAK BOLEH PERNAH** dicampur atau dijumlahkan ke **Indeks Kemiripan Plagiasi**. Keduanya harus berdiri sebagai laporan terpisah.
> 3. Jika teks terlalu pendek (`< 80` kata bermakna) atau sinyal saling bertentangan dengan kepercayaan rendah, sistem **WAJIB** mengembalikan status `INSUFFICIENT_DATA` (**TIDAK CUKUP BUKTI**) — jangan pernah memaksakan klaim pasti "100% AI" pada naskah pendek.

---

## 1. Perbandingan Hasil Audit Tiga Pendekatan Utama

Sebelum membangun engine, seluruh referensi open-source diaudit untuk kompatibilitas CPU Windows, Bahasa Indonesia, dan kalibrasi:

| Pendekatan / Repo | Metode Inti | Kebutuhan Resource (Windows) | Bahasa & Lisensi | Kelemahan Kritis untuk NaskahGuard |
| :--- | :--- | :--- | :--- | :--- |
| **`eric-mitchell/detect-gpt`** | Kurvatur log-probabilitas dengan 10–100 perturbasi `T5` mask-filling + base causal LM (`GPT-2`/dll.) | Sangat berat untuk CPU (~10–100 inferensi per teks; disarankan GPU) | Inggris (`WritingPrompts`, `XSum`, `SQuAD`); **MIT License** | Terlalu lambat di CPU standar; bias pada teks Inggris; tidak terkalibrasi untuk teks akademik Indonesia |
| **`Croups/is-it-ai`** | *Fast-DetectGPT* (single forward pass + multinomial token sampling) + kalibrasi 2-Gaussian (`mu0, sigma0, mu1, sigma1`), chunk 15–50 kata, output 3-kelas (`AI`/`Mixed`/`Human`) | Sedang–Berat (`requires-python >= 3.13`, `transformers>=5.3`, default `Qwen/Qwen2.5-3B` float16 ~6+ GB RAM) | Terutama Inggris; **MIT License** | Butuh kalibrasi ulang lokal (`calibrate_local.py`) agar skor bermakna; teks `<100` kata eksplisit rentan error |
| **`ae-saouiqui/ai-text-detection`** | Klasifikator *fine-tuned* encoder (`mELECTRA`, `mDistilBERT`, `mDeBERTa`, `XLM-R`, LoRA) + tuning threshold PR | Berat (`torch==2.6+cu124`, `peft`, `bitsandbytes`), GPU CUDA | Inggris & Prancis (tanpa Bahasa Indonesia); **Tanpa file LICENSE di repo** | Model terlatih tidak tersedia di repo; tidak dilatih pada teks Indonesia; ketergantungan CUDA tinggi |

Untuk detail metrik, struktur kode, dan file hasil audit lengkap, baca [references/repo_audit_and_calibration.md](references/repo_audit_and_calibration.md).

---

## 2. Arsitektur Deteksi AI NaskahGuard (CPU-First & Modular)

NaskahGuard menerapkan desain **dual-tier modular**:

### Tier 1 — Engine Lokal Bawaan (`ng-id-stylo-lm-v1`, Selalu Tersedia Offline)
- Berjalan di CPU Windows tanpa GPU/CUDA dan tanpa panggilan API berbayar.
- Fitur yang diekstrak per dokumen dan per paragraf:
  1. **Prediktabilitas / Cross-Entropy N-gram Lokal** — Model bahasa n-gram karakter (4-gram) dan kata (bigram/trigram) terpisah untuk pola manusia vs LLM yang dilatih **hanya dari split `train`**, menghasilkan skor *log-likelihood ratio* dan entropi teks.
  2. **Burstiness & Variansi Struktur Kalimat** — Simpangan baku & koefisien variasi (*CV*) panjang kalimat, entropi pembuka kalimat (*sentence starter diversity*), rasio kalimat seragam, dan variansi panjang paragraf.
  3. **Stilometri Akademik (ID & EN)** — *Type-Token Ratio (TTR)* yang ternormalisasi panjang (*MATTR*), *hapax legomena ratio*, distribusi kata fungsi (*stopwords* akademik ID/EN), panjang rata-rata kata, serta rasio klausul/tanda baca (`:`, `;`, em-dash, daftar berpoin simetris).
  4. **Penanda Retorika & Penulisan** — Deteksi konstruksi transisi generik LLM (*"Di era digital...", "Secara keseluruhan...", "Penting untuk dicatat...", "Furthermore, it is worth noting..."*) dibanding variasi penulisan manusia (sitasi tahun/halaman spesifik, gaya personal/informal non-templat, kalimat asimetris).
- **Kalibrasi Ketat**:
  - Seluruh bobot klasifikator (`LogisticRegression` standar + Platt/temperature scaling) **WAJIB** di-fit HANYA pada `train` + `validation`, tidak pernah menyentuh `test` atau *false-positive stress benchmark*.
  - Skor probabilitas (`0.0 - 1.0`) dikonversi ke tingkat keyakinan konservatif.

### Tier 2 — Adapter Transformer Opsional (Manajemen Model)
- Dapat diaktifkan pengguna secara opsional di halaman **Manajemen Model** (`/models`), misalnya model kecil multibahasa yang kompatibel CPU jika `transformers`/`torch` terpasang.
- Harus melaporkan secara eksplisit: ukuran unduhan, estimasi RAM/CPU, dukungan Bahasa Indonesia vs keterbatasan model Inggris-saja, dan status offline.

---

## 3. Empat Label Klasifikasi Resmi & Ambang Konservatif

| Kode Label | Label Bahasa Indonesia | Aturan Keputusan |
| :--- | :--- | :--- |
| `INSUFFICIENT_DATA` | **Tidak Cukup Bukti** | Jumlah kata bersih `< 80` kata (dokumen) atau `< 25` kata (paragraf pendek), atau rasio tanda baca/kode tidak layak dianalisis. Skor ditandai tidak reliabel. |
| `HUMAN_LIKELY` | **Cenderung Tulisan Manusia** | Probabilitas terkalibrasi AI rendah (`<= 0.35`) dengan sinyal variansi manusia yang kuat. |
| `MIXED_UNCERTAIN` | **Campuran / Tidak Pasti** | Probabilitas menengah (`0.35 < p < 0.68`) atau ketidakpastian tinggi antar-paragraf / antar-fitur. |
| `AI_LIKELY` | **Terindikasi Pola Tulisan AI** | Probabilitas terkalibrasi tinggi (`>= 0.68`) yang konsisten di beberapa sinyal independen dan cukup kata (`>= 80`). |

---

## 4. Pencegahan False Positive (Teks Manusia yang Terlihat "Rapi")

Kalibrasi wajib diuji secara eksplisit terhadap kasus manusia berikut agar tidak salah menuduh:
1. **Penulisan Akademik Formal Indonesia** (skripsi/tesis hukum, administrasi, metodologi BAB III yang memang baku).
2. **Abstrak Jurnal Padat** yang ringkas dan mengikuti struktur IMRAD.
3. **Teks Terjemahan atau Suntingan Tata Bahasa** (manusia yang merapikan kalimat dengan EYD/Grammarly ringan).
4. **Dokumen Sangat Pendek** (< 80 kata).

Setiap laporan AI di UI dan PDF/HTML **wajib menampilkan**:
- Disclaimer bahwa hasil adalah **indikasi statistik pola bahasa**, bukan vonis pasti.
- Tingkat ketidakpastian / interval kepercayaan serta status dukungan bahasa (`id`, `en`, atau `mixed`).
- Penjelasan sinyal per paragraf (*mengapa paragraf ini ditandai*), bukan hanya angka persentase tunggal.
