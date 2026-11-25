# NaskahGuard — Status & Verifikasi AI Writing Detection (Phase 10.1)

> **Status Keseluruhan**: **PARTIAL** — Pipeline inferensi, persistensi database, antarmuka pengguna, dan ekspor laporan sudah **berjalan nyata end-to-end secara lokal**, namun validasi akurasi masih berbasis dataset kurasi/sintetik internal (belum divalidasi pada korpus akademik Indonesia dunia nyata berskala besar) dan adapter model Transformer opsional belum terpasang.

---

## 1. Checklist Komponen Teknis AI Detection

| Komponen | Status | Bukti Implementasi | Catatan Audit |
|---|---|---|---|
| **Model Classifier** | **TERSEDIA** | `backend/app/ai_detection/detector.py` (`fit_and_save_model`) + `features.py` (`NgramEntropyModel`) | `StandardScaler` + `LogisticRegression(C=0.35)` atas 12 fitur stilometri/burstiness/spesifisitas/4-gram char cross-entropy. |
| **Model File / Konfigurasi Unduhan** | **BAWAAN TERSEDIA / OPSIONAL BELUM** | `backend/app/data/models/ng_id_stylo_lm_v1.json` (`54.908 byte`) & `model_registry.py` | Model CPU bawaan `ng-id-stylo-lm-v1` tersedia luring. Dua adapter opsional (`ng-fast-detect-curv-en`, `ng-mdistilbert-enc-v1`) berstatus `DEPS_MISSING` (`torch=False`, `transformers=False`) dan menolak aktivasi dengan HTTP `400`. |
| **Inference Engine** | **TERSEDIA** | `detector.py`: `analyze_document_ai()`, `classify_paragraph()`, `_score_raw_probability()` | Bukan teks statis atau mockup; menghitung fitur 12 dimensi, logit diskalakan temperatur, dan penalti/kredit fitur secara nyata per dokumen & per paragraf. |
| **API Endpoint** | **TERSEDIA** | `checks.py` (`POST /api/checks` dengan `AI_ONLY`/`COMBINED`), `models_mgmt.py` (`GET /api/models`, `POST /api/models/{id}/verify`, `POST /api/models/{id}/activate`) | Diuji end-to-end lewat `TestClient` pada `test_phase10_ai_detection.py`. |
| **Paragraph Segmentation** | **TERSEDIA** | `features.py`: `split_paragraphs()` (`PARA_SPLIT_RE` + pemecahan kelompok kalimat bila 1 paragraf > 240 kata) | Paragraf `< 25` kata dikembalikan sebagai `INSUFFICIENT_DATA` (`ai_likelihood_pct=None`). |
| **AI Score Generation** | **TERSEDIA** | `detector.py:350-416` | Gabungan terbobot `0.58 * doc_prob + 0.42 * weighted_para_prob`; dokumen `< 80` kata ditolak (`score_available=False`, `INSUFFICIENT_DATA`). |
| **Confidence Calibration** | **TERSEDIA** | `detector.py:89-112, 183-186, 366-381` | Temperature scaling `T = 1.3` dipilih berdasarkan NLL minimum pada validation split (`n=48`, `val_acc=0.9167`, `nll=0.2522`), ditambah `uncertainty_pct` eksplisit (`9%–45%`) dan guardrail dokumen campuran. |
| **Database Persistence** | **TERSEDIA** | `backend/app/models.py` + `alembic/versions/0003_*` | Disimpan pada kolom `checks.mode` dan `checks.ai_report` (JSON). |
| **Report Integration** | **TERSEDIA** | `builder.py:197-286`, `ReportDetailPage.tsx:1357-1536` | Bagian Laporan AI terisolasi ketat dari Indeks Kemiripan Plagiasi, menampilkan skor, ketidakpastian, sinyal penilaian, analisis per paragraf, dan disclaimer wajib. |
| **Export Integration** | **TERSEDIA** | `pdf_report.py:572-621`, `html_report.py` & `report.html`, `json_report.py` | PDF/HTML menuliskan halaman/bagian terpisah *"Laporan Deteksi Tulisan AI"* berisi skor, disclaimer probabilistik, dan tabel per paragraf. |

---

## 2. Verifikasi Alur End-to-End

Alur berikut telah ditelusuri langsung pada kode dan diverifikasi melalui `test_e2e_ai_only_and_combined_modes_and_model_registry` (`PASSED`):

1. `POST /api/documents` → ekstraksi teks PDF/DOCX/TXT (`extraction.py` / `pdf.py`) & simpan artefak terstruktur.
2. `POST /api/checks` (`check_mode="AI_ONLY"` atau `"COMBINED"`) → worker memanggil `run_check_pipeline()`.
3. `load_extracted_payload(doc.id)` → mengambil teks naskah penuh.
4. `analyze_document_ai(sub_text, model_id=chosen_model)` → menjalankan `detect_text_language()`, `split_paragraphs()`, `classify_paragraph()`, agregasi berbobot dokumen+paragraf, serta guardrail `< 80` kata dan prose campuran.
5. `check.ai_report = ai_result` → tersimpan ke SQLite dan tersedia di `GET /api/checks/{id}/report`, `export.pdf`, `export.html`, dan `export.json`.

**Kesimpulan Status Alur**: **Bukan `UI ONLY`**. Seluruh rantai inferensi berjalan nyata di backend lokal.

---

## 3. Hasil Benchmark Aktual (`run_phase10_ai_benchmark.py`)

Dieksekusi langsung pada **25 November 2026** terhadap artefak model `ng-id-stylo-lm-v1` (`v1.0.0`) menggunakan dataset uji terpisah (`benchmark/data/ai_detection/`):
- **Train split**: `120` dokumen (`10` topik unik)
- **Validation split**: `48` dokumen (`4` topik unik, terpisah dari train & test)
- **Test split**: `72` dokumen (`6` topik unik & pola kalimat tak terlihat oleh train/val)
- **False-Positive Stress suite**: `5` kasus khusus

### 3.1 Metrik Keseluruhan Test Split (`n = 72`)

| Ambang Evaluasi | Precision | Recall | F1 | FPR | FNR | ROC-AUC | Brier Score | ECE |
|---|---|---|---|---|---|---|---|---|
| Ambang statistik `>= 0.50` | `0.7692` | `0.8333` | `0.8000` | `0.2500` | `0.1667` | `0.9537` | `0.1023` | `0.1465` |
| Ambang produk `AI_LIKELY >= 0.68` | `0.9062` | `0.8056` | `0.8529` | `0.0833` | `0.1944` | `0.9537` | `0.1023` | `0.1465` |
| Keputusan keras produk (`classification == "AI_LIKELY"`) | — | — | — | **`0.0000` (0/36)** | — | — | — | — |

### 3.2 Performa Per Bahasa (`test_by_language`, ambang `0.50`)

| Bahasa | Jumlah (`n`) | TP / FP / TN / FN | Precision | Recall | F1 | FPR | FNR | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bahasa Indonesia (`id`)** | `39` | `15 / 3 / 15 / 6` | `0.8333` | `0.7143` | `0.7692` | `0.1667` | `0.2857` | `0.9524` | `0.1032` | `0.1401` |
| **Bahasa Inggris (`en`)** | `33` | `15 / 6 / 12 / 0` | `0.7143` | `1.0000` | `0.8333` | `0.3333` | `0.0000` | `1.0000` | `0.1012` | `0.1834` |

### 3.3 Performa Per Kategori Penulisan (`n = 72`)

| Kategori | Label Asli | `n` | Akurasi (`>= 0.50`) | Rerata Skor AI (%) | Distribusi Keputusan Produk |
|---|---|---|---|---|---|
| `human_original_id` | Manusia (`0`) | `6` | `1.0000` | `3.72%` | `HUMAN_LIKELY: 6` |
| `human_original_en` | Manusia (`0`) | `6` | `1.0000` | `4.45%` | `HUMAN_LIKELY: 6` |
| `academic_nonformal_human` | Manusia (`0`) | `12` | `1.0000` | `12.49%` | `HUMAN_LIKELY: 12` |
| `academic_formal_human` | Manusia (`0`) | `12` | **`0.2500`** | **`53.84%`** | `HUMAN_LIKELY: 3`, `MIXED_UNCERTAIN: 9` *(0 AI_LIKELY)* |
| `human_ai_assisted` (hybrid) | AI (`1`) | `6` | `0.5000` | `56.22%` | `MIXED_UNCERTAIN: 4`, `AI_LIKELY: 2` |
| `ai_human_edited` | AI (`1`) | `6` | `0.5000` | `53.73%` | `MIXED_UNCERTAIN: 6` |
| `ai_paraphrased` | AI (`1`) | `12` | `1.0000` | `90.61%` | `AI_LIKELY: 12` |
| `ai_pure_multi_style` | AI (`1`) | `12` | `1.0000` | `95.00%` | `AI_LIKELY: 12` |

### 3.4 Uji Stress False-Positive, Teks Pendek, & Teks Panjang

- **False-Positive Stress Suite (`n = 5`)**: `false_positive_rate_strict_ai = 0.0` (0 vonis keliru `AI_LIKELY`).
  - `fp_01_id_formal_law` (teks hukum formal Indonesia) -> `MIXED_UNCERTAIN` (`45.3%`).
  - `fp_02_id_dense_abstract` (abstrak IMRAD medis) -> `HUMAN_LIKELY` (`3.0%`).
  - `fp_03_en_formal_methods` (metode akademik Inggris) -> `HUMAN_LIKELY` (`3.0%`).
  - `fp_04_id_grammar_polished` (prose Indonesia tersunting) -> `HUMAN_LIKELY` (`33.3%`).
  - `fp_05_short_text_guard` (< 80 kata) -> `INSUFFICIENT_DATA` (`ai_likelihood_pct=null`).
- **Uji Ad-Hoc Teks Panjang (gabungan korpus uji Bahasa Indonesia)**:
  - Teks manusia panjang (`464` kata) -> `HUMAN_LIKELY` (`9.0%`).
  - Teks AI + suntingan campuran panjang (`427` kata) -> `MIXED_UNCERTAIN` (`72.8%`; ditahan oleh guardrail campuran karena salah satu segmen terukur rendah).
- **Latensi Inferensi**: Total `83.78 ms` untuk `72` dokumen (`1.16 ms/dokumen` rata-rata di CPU).

---

## 4. Keterbatasan Jujur & Celah Validasi

1. **Sumber Ground-Truth Masih Kurasi Internal (Belum Validasi Eksternal Independen)**:
   - Seluruh `245` sampel pada `backend/app/ai_detection/dataset_builder.py` disintesis secara programatik melalui templat dan topik yang dipisah ketat (`TRAIN_TOPICS`, `VAL_TOPICS`, `TEST_TOPICS`) — **bukan** korpus eksternal terpublikasi independen (seperti skripsi mahasiswa pra-2022 vs keluaran nyata GPT-4/Claude/Gemini/DeepSeek).
   - Oleh karena itu, angka `ROC-AUC = 0.9537` mencerminkan performa pada benchmark internal terkontrol, dan **Bahasa Indonesia dunia nyata belum tervalidasi secara eksternal**.
2. **Teks Akademik Sangat Formal (`academic_formal_human`)**:
   - Pada benchmark uji, `9 dari 12` sampel prose akademik sangat formal mendapat skor `>= 50%` (`MIXED_UNCERTAIN`, rerata `53.84%`). Walaupun tidak ada yang melampaui ambang vonis `AI_LIKELY` (`>= 68%`), angka `~54%` tetap berpotensi menimbulkan kecurigaan reviewer awam tanpa penjelasan konteks.
3. **Teks Terjemahan & Teks AI yang Disunting Berat**:
   - Skenario **terjemahan manusia (`ID <-> EN`)** belum memiliki kategori uji terpisah di `run_phase10_ai_benchmark.py`.
   - Skenario **`ai_human_edited`** umumnya jatuh ke `MIXED_UNCERTAIN` (`53.73%`), sehingga sistem tidak agresif menuduh naskah yang telah banyak disunting manusia.
4. **Model Transformer Opsional Belum Terpasang**:
   - `ng-fast-detect-curv-en` dan `ng-mdistilbert-enc-v1` tidak disertai bobot lokal maupun paket `torch`/`transformers` di environment Windows default.
