# Audit Tiga Repositori AI Writing Detection & Metodologi Kalibrasi

Dokumen pendukung ini mencatat temuan kode aktual dari audit tiga repositori referensi pada Phase 10 NaskahGuard.

## 1. `eric-mitchell/detect-gpt`
- **Lisensi**: MIT (`LICENSE`).
- **Arsitektur Teknis (`run.py`)**:
  - Menghitung `log p(x)` untuk teks asli menggunakan model bahasa kausal (`GPT-2`, `GPT-J`, dll.).
  - Menghasilkan `N` versi terperturbasi via model mask-filling (`t5-large` / `t5-3b`).
  - Membandingkan selisih kurvatur log-probabilitas `(log p(x) - mean(log p(x_tilde))) / std(...)`.
- **Ketergantungan**: `torch`, `transformers`, `datasets`, `openai`, `nltk`, `matplotlib`.
- **Evaluasi Kesiapan NaskahGuard**:
  - **Kelebihan**: Konsep zero-shot berbasis distribusi probabilitas sangat informatif untuk memahami kesenjangan entropi manusia vs LLM.
  - **Hambatan**: Biaya komputasi tinggi (`N=10..100` forward passes + generasi T5), lambat di CPU Windows, dan belum memiliki kalibrasi khusus naskah Indonesia.

## 2. `Croups/is-it-ai`
- **Lisensi**: MIT (`LICENSE`).
- **Arsitektur Teknis (`ai_detector.py`, `calibrate_local.py`, `pyproject.toml`)**:
  - Mengimplementasikan *Fast-DetectGPT*: alih-alih menghasilkan puluhan perturbasi T5, ia menghitung *analytical conditional probability curvature* menggunakan satu forward pass + `num_samples` multinomial sampling distribusi token.
  - Chunking cerdas (`chunk_text`): memecah dokumen menjadi potongan 15–50 kata yang menghormati batas kalimat agar tidak melebihi batas konteks dan memberi analisis granular.
  - Kalibrasi Bayesian dua-Gaussian (`mu0, sigma0` untuk manusia, `mu1, sigma1` untuk AI) untuk memetakan skor `d` ke probabilitas dan label 3-arah (`Human`, `Mixed`, `AI`).
  - Eksplisit memberi peringatan bahwa teks `< 100` kata rentan fluktuasi dan parameter kalibrasi default harus diganti hasil kalibrasi lokal (`calibrate_local.py`).
- **Ketergantungan**: Python `>=3.13`, `transformers>=5.3.0`, `torch`, default model `Qwen/Qwen2.5-3B` (~6+ GB float16 RAM).
- **Adopsi ke NaskahGuard**:
  - Ide **analisis per chunk/paragraf berbasis batas kalimat**, **output 3-kategori + status batas minimum kata**, dan **kalibrasi probabilistik eksplisit di luar skor mentah** diadopsi langsung ke NaskahGuard.

## 3. `ae-saouiqui/ai-text-detection`
- **Lisensi**: Tidak ditemukan file `LICENSE` pada root repositori (hanya `README.md`, `configs/`, `scripts/`, `notebooks/`, `results/`). Kode atau bobot eksternal tidak disalin mentah.
- **Arsitektur Teknis (`scripts/train.py`, `scripts/evaluate_model.py`, `configs/model_map.json`)**:
  - *Fine-tuning* model encoder multibahasa (`AILabTUL/mELECTRA`, `distilbert-base-multilingual-cased`, `microsoft/mdeberta-v3-base`, `FacebookAI/xlm-roberta-base`, serta LoRA).
  - Mengukur metrik per bahasa (`global`, `english`, `french`) menggunakan `accuracy`, `f1`, `precision`, `recall`, dan `roc_auc`, serta memilih ambang batas keputusan optimal berbasis kurva PR.
  - Contoh hasil terpublikasi pada `results/electra/metrics.json`: `global accuracy 0.780`, `f1 0.810`, `roc_auc 0.886`; kinerja berbeda nyata antar bahasa (`english f1 0.782` vs `french f1 0.929`).
- **Pelajaran Penting untuk NaskahGuard**:
  - Performa detektor tidak sama antar bahasa! Evaluasi wajib dipisah per bahasa (`id` vs `en`), per kategori penulisan, dan tidak boleh menyamaratakan klaim metrik bahasa Inggris/Prancis ke Bahasa Indonesia tanpa tolok ukur tersendiri.

## 4. Checklist Kalibrasi & Integritas Data NaskahGuard
1. Split dataset `train` (60%), `validation` (20%), dan `test` (20%) dibuat deterministik sebelum pelatihan fitur statistik maupun regresi kalibrasi.
2. *False-positive benchmark* dipisahkan agar benar-benar mengukur risiko tuduhan keliru pada teks formal Indonesia, abstrak padat, dan teks pendek.
3. Parameter n-gram LM (`token` + `char`) hanya belajar dari split `train`.
4. Skor yang disajikan ke pengguna harus melaporkan **Indeks Indikasi Pola AI (%)**, **Label**, **Tingkat Keyakinan**, **Cakupan Bahasa**, dan **Keterbatasan Analisis**.
