# Hasil Benchmark & Kalibrasi Deteksi Tulisan AI (Phase 10)

Evaluasi dijalankan menggunakan `backend/.venv/Scripts/python.exe benchmark/run_phase10_ai_benchmark.py` dengan keluaran tersimpan di `benchmark/results/phase10_ai_benchmark.json`.

---

## 1. Desain Dataset Bebas Kebocoran (*Zero-Leakage Splits*)

Untuk memastikan skor mencerminkan kemampuan generalisasi sebenarnya, pemisahan dilakukan secara ketat baik pada **topik** maupun **pola kalimat/templat**:
- **`train`** (`120` dokumen): 10 topik unik (mis. irigasi subak, retribusi sampah, fermentasi tempe) untuk fitting model bahasa karakter 4-gram, scaler standar, dan bobot regresi logistik terregularisasi (`C = 0.35`).
- **`validation`** (`48` dokumen): 4 topik terpisah (mis. rehabilitasi mangrove, kopi arabika, ergonomi konveksi) khusus untuk *temperature scaling* (`T = 1.3`, akurasi validasi `0.9167`, NLL `0.2522`).
- **`test`** (`72` dokumen): 6 topik dan gaya retorika yang **belum pernah dilihat saat pelatihan/validasi** (mis. kepatuhan pajak UMKM, stabilitas lereng, stok reagen RSUD), mencakup seluruh 8 kategori penulisan.
- **`false_positive_stress`** (`5` skenario khusus): teks hukum formal Indonesia, abstrak IMRAD medis padat, metodologi formal Inggris, tulisan Indonesia rapi tersunting, serta teks pendek `< 80` kata.

---

## 2. Metrik Evaluasi pada Split Uji Tersembunyi (`test`, n = 72)

| Pengaturan Ambang | Precision | Recall | F1-Score | FPR | FNR | ROC-AUC | Brier | ECE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Ambang Biner Standar (`p >= 0.50`) | `0.7692` | `0.8333` | `0.8000` | `0.2500` | `0.1667` | `0.9537` | `0.1023` | `0.1465` |
| Ambang Keputusan Produk (`AI_LIKELY`, `p >= 0.68`) | `0.9062` | `0.8056` | `0.8529` | `0.0833` | `0.1944` | `0.9537` | `0.1023` | `0.1465` |

> **Temuan Kunci Ambang Konservatif**: Pada ambang produk resmi (`AI_LIKELY >= 68%`), **`strict_ai_likely_false_positives = 0`** dari seluruh 36 dokumen manusia pada split uji (`strict_ai_likely_fpr = 0.0`). Dokumen manusia formal berada di rentang `HUMAN_LIKELY` atau `MIXED_UNCERTAIN` sehingga tidak pernah divonis keliru sebagai "Terindikasi Pola AI".

### Performa per Bahasa (`p >= 0.50`)
- **Bahasa Indonesia (`n = 39`)**: Precision `0.8333`, Recall `0.7143`, F1 `0.7692`, FPR `0.1667`, ROC-AUC `0.9524`, ECE `0.1401`.
- **Bahasa Inggris (`n = 33`)**: Precision `0.7143`, Recall `1.0000`, F1 `0.8333`, FPR `0.3333`, ROC-AUC `1.0000`, ECE `0.1834`.

### Performa per Kategori Penulisan (8 Kategori)

| Kategori | Label Asli | Rata-rata Skor AI (%) | Distribusi Klasifikasi Aktual |
| :--- | :---: | :---: | :--- |
| `human_original_id` | Manusia (0) | `3.72%` | `6/6 HUMAN_LIKELY` |
| `human_original_en` | Manusia (0) | `4.45%` | `6/6 HUMAN_LIKELY` |
| `academic_nonformal_human` | Manusia (0) | `12.49%` | `12/12 HUMAN_LIKELY` |
| `academic_formal_human` | Manusia (0) | `53.84%` | `3 HUMAN_LIKELY`, `9 MIXED_UNCERTAIN`, **0 `AI_LIKELY`** |
| `human_ai_assisted` (campuran) | Campuran (1) | `56.22%` | `4 MIXED_UNCERTAIN`, `2 AI_LIKELY` |
| `ai_human_edited` (AI disunting) | AI (1) | `53.73%` | `6/6 MIXED_UNCERTAIN` |
| `ai_paraphrased` | AI (1) | `90.61%` | `12/12 AI_LIKELY` |
| `ai_pure_multi_style` | AI (1) | `95.00%` | `12/12 AI_LIKELY` |

---

## 3. Hasil Uji Ketahanan *False Positive* (`false_positive_stress`)

| ID Kasus | Skenario Risiko | Skor AI | Keputusan NaskahGuard | Status Guardrail |
| :--- | :--- | :---: | :--- | :---: |
| `fp_01_id_formal_law` | Penulisan hukum & regulasi formal | `45.3%` | `MIXED_UNCERTAIN` | Lulus (tidak dituduh AI) |
| `fp_02_id_dense_abstract` | Abstrak IMRAD medis padat Bahasa Indonesia | `3.0%` | `HUMAN_LIKELY` | Lulus |
| `fp_03_en_formal_methods` | Bab metodologi Inggris sangat rapi | `3.0%` | `HUMAN_LIKELY` | Lulus |
| `fp_04_id_grammar_polished` | Tulisan asli manusia tersunting tata bahasa | `33.3%` | `HUMAN_LIKELY` | Lulus |
| `fp_05_short_text_guard` | Teks terlalu singkat (`< 80` kata) | `null` | `INSUFFICIENT_DATA` | Lulus |

**Rata-rata waktu analisis per dokumen**: `1,17 ms` di CPU lokal (`84,38 ms` untuk seluruh 72 dokumen uji).
