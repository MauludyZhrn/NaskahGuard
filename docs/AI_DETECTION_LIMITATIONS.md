# Keterbatasan & Panduan Interpretasi Deteksi Tulisan AI

Dokumen ini menjelaskan batasan ilmiah dan operasional fitur Deteksi Tulisan AI di NaskahGuard agar tidak disalahgunakan dalam keputusan akademik.

---

## 1. Sifat Probabilistik (Bukan Alat Vonis)
- Deteksi tulisan AI hanya mengukur **pola kesamaan statistik kebahasaan** (keseragaman ritme kalimat, prediktabilitas karakter, serta kepadatan frasa generik).
- Nilai indikasi tinggi **tidak membuktikan** adanya penggunaan LLM secara mutlak, dan nilai rendah tidak menjamin dokumen 100% bebas AI.
- Keputusan sanksi akademik **wajib** didasarkan pada telaah substansi dosen/reviewer, wawancara klarifikasi penulis, dan riwayat draf dokumen — bukan satu angka detektor otomatis.

## 2. Keterbatasan Teknis & Kebahasaan
1. **Teks Akademik Sangat Formal (`academic_formal_human`)**:
   Penulisan regulasi hukum, pasal perundang-undangan, atau bagian metode baku BAB III secara alami memiliki ritme kalimat seragam sehingga dapat masuk kategori `MIXED_UNCERTAIN` (`38%–67%`). Oleh karena itu NaskahGuard menggunakan ambang tinggi (`>= 68%`) sebelum memberi label `AI_LIKELY`.
2. **Teks AI yang Disunting Berat (`ai_human_edited`)**:
   Apabila teks keluaran AI disunting ekstensif oleh manusia dan diberi rincian observasi lapangan nyata, skor turun ke wilayah ragu-ragu (`MIXED_UNCERTAIN`, rata-rata uji `53,7%`).
3. **Teks Pendek (`< 80` kata)**:
   Secara statistik tidak stabil; NaskahGuard menghentikan penilaian numerik dan mengembalikan **`Tidak Cukup Bukti`** (`INSUFFICIENT_DATA`).
4. **Cakupan Bahasa**:
   Model bawaan (`ng-id-stylo-lm-v1`) dikalibrasi untuk **Bahasa Indonesia** dan **Bahasa Inggris**. Untuk dokumen berbahasa lain, sistem otomatis mencatat peringatan cakupan bahasa pada laporan.
5. **Model Opsional HuggingFace**:
   Adapter seperti `ng-fast-detect-curv-en` dan `ng-mdistilbert-enc-v1` tidak diaktifkan secara bawaan karena memerlukan PyTorch (`1,1–3,2+ GB` RAM) serta belum memiliki kalibrasi Bahasa Indonesia bawaan.

## 3. Pemisahan Mutlak dari Plagiasi
- **Kemiripan Plagiasi** berarti ada kecocokan teks nyata terhadap sumber pembanding berteks lengkap.
- **Indikasi Pola AI** berarti gaya penulisan menyerupai distribusi teks LLM, meskipun tidak ada satu kalimat pun yang menjiplak sumber tertentu.
- Kedua metrik tersebut tidak pernah digabungkan pada rumus perhitungan NaskahGuard.
