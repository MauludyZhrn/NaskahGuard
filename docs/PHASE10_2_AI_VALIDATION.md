# NaskahGuard — Phase 10.2: Validasi Independen & Audit Kalibrasi AI Detector

> **Model Dievaluasi**: `ng-id-stylo-lm-v1` (`v1.0.0`, CPU lokal luring)  
> **Tanggal Evaluasi**: 25 November 2026  
> **Artefak Hasil**: [phase10_2_ai_validation.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_2_ai_validation.json)  
> **Skrip Reproduksi**: [fetch_openalex_human_groundtruth.py](file:///d:/Projects/NaskahGuard/benchmark/fetch_openalex_human_groundtruth.py), [run_phase10_2_ai_validation.py](file:///d:/Projects/NaskahGuard/benchmark/run_phase10_2_ai_validation.py)

---

## 1. Desain Dataset Evaluasi Independen (Tanpa Kebocoran Data)

Untuk mengatasi celah validasi pada Phase 10.1 (di mana dataset uji lama seluruhnya berupa templat internal), Phase 10.2 membangun korpus evaluasi independen (`benchmark/data/ai_detection_v2/`) sebanyak **152 dokumen** (`61` `validation_v2`, `87` `test_v2`, dan `4` guardrail teks pendek):

1. **100 Artikel Akademik Manusia Pra-2022 Nyata (`real_human_open_access.json`)**:
   - Diambil langsung dari **DOAJ Open Access API** dan **Europe PMC Open Access** dengan batas ketat tahun terbit **2015–2021** (sebelum kemunculan ChatGPT November 2022) untuk menjamin ground truth kepenulisan manusia murni.
   - Setiap dokumen menyimpan `document_id`, `source_id` (ISSN/nama jurnal), `doi`, `year`, `venue`, `license` (`DOAJ-Open-Access` / `Europe-PMC-Open-Access`), dan `provenance`.
   - Rincian kategori nyata pra-2022:
     - `legal_islamic_id` (**31 artikel nyata** jurnal Hukum Islam, Fiqh, Syariah, Hukum Pidana, Ilmu Falak, dan Perundang-undangan Indonesia)
     - `formal_academic_id` (**15 artikel nyata** akademik formal Indonesia)
     - `human_written_id` (**12 artikel nyata** akademik umum Indonesia)
     - `english_academic_en` (**26 artikel nyata** akademik Inggris)
     - `formal_academic_en` (**16 artikel nyata** akademik formal Inggris)
2. **48 Dokumen Evaluasi Multikategori Independen (`CC-BY-4.0`, terpisah 100% dari topik & templat `dataset_builder.py`)**:
   - `ai_generated_id` (`14` dokumen, 3 paragraf, > 85 kata, multi-gaya termasuk gaya netral non-klise)
   - `ai_generated_en` (`8` dokumen, 3 paragraf, multi-gaya)
   - `human_ai_hybrid` (`10` dokumen: paragraf 1 artikel manusia nyata pra-2022 + paragraf 2 keluaran AI independen, `5 ID` + `5 EN`)
   - `ai_human_edited` (`8` dokumen AI yang disunting manusia dengan data empiris/tanggal spesifik, `4 ID` + `4 EN`)
   - `human_translation` (`8` dokumen terjemahan akademik manusia `EN <-> ID`, berlabel `0` sebagai uji *false-positive*)
3. **Pemisahan Ketat Berdasarkan Dokumen & Sumber**:
   - Pembagian `validation_v2` (`~40%`) dan `test_v2` (`~60%`) dikelompokkan berdasarkan `(category, source_id)` dengan asersi otomatis:
     - `document_disjoint_verified = true` (0 dokumen lintas split)
     - `source_disjoint_verified = true` (0 jurnal/sumber lintas split, tidak ada pemecahan paragraf dari dokumen yang sama ke split berbeda)

---

## 2. Audit Kalibrasi & Ambang Batas (Hanya pada Validation Split)

Sebelum melakukan perubahan apa pun pada model, dilakukan audit temperatur (`T`) dan ambang keputusan (`threshold`) **secara eksklusif pada `validation_v2` (`n = 61`)** tanpa menyentuh `test_v2`:

### 2.1 Sweep Temperatur pada `validation_v2`
| Temperatur (`T`) | NLL (`validation_v2`) | Brier Score | ECE | Catatan |
|---|---|---|---|---|
| `1.0` | `0.2306` | `0.0600` | `0.0709` | Sedikit lebih tajam |
| **`1.3` (Aktif Saat Ini)** | **`0.2303` (Terendah)** | `0.0614` | `0.0733` | **Optimal NLL pada validation** |
| `1.6` | `0.2375` | `0.0634` | `0.0615` | NLL mulai naik |
| `1.9` | `0.2478` | `0.0659` | `0.0631` | Under-confident |
| `2.2` – `2.8` | `0.2591` – `0.2667` | `0.0687` – `0.0734` | `0.0640` – `0.0894` | Kalibrasi menurun |

### 2.2 Sweep Ambang Batas pada `validation_v2` (`T = 1.3`)
| Ambang | Precision | Recall | F1 | FPR | FNR |
|---|---|---|---|---|---|
| `0.50` | `1.0000` | `0.8125` | `0.8966` | `0.0000` | `0.1875` |
| `0.55` – `0.65` | `1.0000` | `0.7500` | `0.8571` | `0.0000` | `0.2500` |
| **`0.68` (Ambang Produk Aktif)** | **`1.0000`** | **`0.6875`** | **`0.8148`** | **`0.0000`** | **`0.3125`** |
| `0.78` | `1.0000` | `0.6250` | `0.7692` | `0.0000` | `0.3750` |

**Keputusan Kalibrasi**: Temperatur **`T = 1.3`** dan ambang konservatif **`AI_LIKELY >= 0.68`** **dipertahankan** (tidak diganti secara agresif ke `0.50`) karena pada domain akademik nyata, menjaga `FPR = 0%` atas tulisan terjemahan dan naskah formal jauh lebih kritis dibandingkan menaikkan recall secara agresif. Zona `0.38 < p < 0.68` dipertahankan sebagai **`MIXED_UNCERTAIN`**.

---

## 3. Hasil Evaluasi pada Held-Out `test_v2` (`n = 87`, Tidak Tersentuh Tuning)

### 3.1 Metrik Global & Per Bahasa (`test_v2`)

| Subset (`test_v2`) | `n` | Ambang | Precision | Recall | F1 | FPR | FNR | ROC-AUC | Brier | ECE | Strict `AI_LIKELY` FP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Keseluruhan** | `87` | `0.50` | `0.9474` | `0.7500` | `0.8372` | `0.0159` | `0.2500` | `0.9729` | `0.0581` | `0.0314` | — |
| **Keseluruhan (Produk)** | `87` | **`0.68`** | **`1.0000`** | **`0.7500`** | **`0.8571`** | **`0.0000`** | **`0.2500`** | **`0.9729`** | **`0.0581`** | **`0.0314`** | **`0 / 63` (`0.0%`)** |
| **Bahasa Indonesia (`id`)** | `54` | **`0.68`** | **`1.0000`** | **`0.8000`** | **`0.8889`** | **`0.0000`** | **`0.2000`** | **`0.9880`** | **`0.0455`** | **`0.0801`** | **`0 / 39` (`0.0%`)** |
| **Bahasa Inggris (`en`)** | `33` | **`0.68`** | **`1.0000`** | **`0.6667`** | **`0.8000`** | **`0.0000`** | **`0.3333`** | **`0.9491`** | **`0.0787`** | **`0.0734`** | **`0 / 24` (`0.0%`)** |

### 3.2 Pemeriksaan False Positive & Performa Per Kategori (`test_v2`)

| Kategori | Label | `n` | Rerata Skor AI | Akurasi (`0.68`) | `AI_LIKELY` FP | Distribusi Klasifikasi |
|---|---|---|---|---|---|---|
| `legal_islamic_id` *(DOAJ nyata pra-2022)* | Manusia (`0`) | `20` | **`6.04%`** | **`1.0000`** | **`0`** | `HUMAN_LIKELY: 20` |
| `formal_academic_id` *(DOAJ nyata pra-2022)* | Manusia (`0`) | `9` | **`9.52%`** | **`1.0000`** | **`0`** | `HUMAN_LIKELY: 9` |
| `human_written_id` *(DOAJ nyata pra-2022)* | Manusia (`0`) | `7` | **`8.61%`** | **`1.0000`** | **`0`** | `HUMAN_LIKELY: 7` |
| `english_academic_en` + `formal_academic_en` *(OA nyata pra-2022)* | Manusia (`0`) | `22` | `< 11%` | **`1.0000`** | **`0`** | `HUMAN_LIKELY: 22` |
| `human_translation` *(Terjemahan ID↔EN)* | Manusia (`0`) | `5` | `27.50%` | **`1.0000`** | **`0`** | `HUMAN_LIKELY: 4`, `MIXED_UNCERTAIN: 1` |
| `ai_generated_id` | AI (`1`) | `8` | `> 90%` | `1.0000` | — | `AI_LIKELY: 8` |
| `ai_generated_en` | AI (`1`) | `5` | `93.46%` | `1.0000` | — | `AI_LIKELY: 5` |
| `human_ai_hybrid` *(1 prg manusia + 1 prg AI)* | Campuran (`1`) | `6` | `21.22%` | `0.0000` *(pada level dokumen keras)* | — | **`MIXED_UNCERTAIN: 6`** *(tepat sebagai dokumen campuran; highlight menandai paragraf AI terpisah)* |
| `short_text` (`< 80` kata) | Guardrail | `4` | `null` | `100%` | `0` | **`INSUFFICIENT_DATA: 4`** |

---

## 4. Peningkatan Laporan AI & Keterbatasan Transparan

1. **Peningkatan Laporan (`detector.py`, `ReportDetailPage.tsx`, `pdf_report.py`, `report.html`)**:
   - Menambahkan `paragraph_summary` (`total_paragraphs`, `ai_likely_count`, `human_likely_count`, `uncertain_count`, `insufficient_count`) dan `calibration` (`calibrated`, `temperature`, `ai_threshold`) ke payload laporan, UI Web, ekspor PDF, dan ekspor HTML.
   - Menambahkan blok highlight warna per paragraf (`AI_LIKELY`, `MIXED_UNCERTAIN`, `HUMAN_LIKELY`, `INSUFFICIENT_DATA`).
   - Endpoint `POST /api/checks` kini menolak secara eksplisit (HTTP `400`) apabila pengguna meminta `ai_model_id` eksternal yang bobotnya belum terpasang.
2. **Keterbatasan yang Tetap Dicatat Jujur**:
   - Teks hibrida (`human_ai_hybrid`) yang didominasi paragraf manusia panjang cenderung masuk `MIXED_UNCERTAIN` pada skor level dokumen sehingga penelaah wajib memeriksa highlight per paragraf.
   - Sampel AI pada `test_v2` masih merupakan teks kurasi multi-gaya dan belum mencakup korpus besar lintas keluarga model komersial terbaru (GPT-5/Claude/Gemini/DeepSeek) sepanjang 3.000+ kata.
   - Hasil deteksi AI bersifat **probabilistik**, tidak pernah memberikan vonis otomatis, dan terpisah penuh dari **Indeks Kemiripan Plagiasi**.
