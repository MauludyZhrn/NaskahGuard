# Desain Mesin Deteksi Kemiripan, Bahasa Indonesia & Audit Skor (Phase 9)

Dokumen ini menjelaskan peningkatan mesin pendeteksian kemiripan pada Phase 9, khususnya pemrosesan morfologi Bahasa Indonesia, deteksi parafrasa terukur, serta audit matematis presisi skor.

## 1. Pemrosesan Morfologi & Parafrasa Bahasa Indonesia (`indonesian_nlp.py`)

Modul [indonesian_nlp.py](file:///d:/Projects/NaskahGuard/backend/app/engine/indonesian_nlp.py) dirancang khusus untuk karakteristik naskah ilmiah Bahasa Indonesia:
1. **Perubahan Imbuhan (*Affixation*)**: Stemmer deterministik menangani prefiks (`meng-`, `meny-`, `mem-`, `men-`, `me-`, `peng-`, `peny-`, `pem-`, `pen-`, `ber-`, `ter-`, `per-`, `di-`, `ke-`, `se-`), sufiks (`-kan`, `-an`, `-i`), dan enklitik (`-lah`, `-kah`, `-nya`) dengan aturan asimilasi bunyi sengau (mis. `menggunakan -> guna`, `memanfaatkan -> manfaat -> guna`, `memperlihatkan -> tunjuk`).
2. **Kanonisasi Sinonim Akademik Non-Teknis**: Mengelompokkan padanan kata kerja/benda umum akademik (mis. `riset/kajian/studi`, `dampak/pengaruh/efek`, `peningkatan/kenaikan`, `penurunan/reduksi`, `kesimpulan/simpulan`) tanpa menyamakan istilah teknis bidang ilmu.
3. **Ketahanan Urutan Klausa & Kata Hubung**: Mengabaikan partikel/konjungsi dan memadukan kemiripan *character n-gram* TF-IDF (`char_wb` 3–5) dengan *Dice overlap* akar kata predikat/konten sehingga pembalikan anak kalimat tetap terdeteksi sebagai `LEXICAL`.
4. **Perlindungan Istilah Teknis / Serapan Arab & Inggris (*Anti-False-Positive Guard*)**: Daftar istilah teknis umum (`regresi`, `validitas`, `algoritma`, `database`, `machine`, `learning`, `syariah`, `mudharabah`, `maqashid`, dll.) dipisahkan dari kata konten non-teknis. Kalimat berbeda yang hanya berbagi jargon teknis **dibatasi di bawah ambang** (`< 0.65`) sehingga tidak menghasilkan *false positive*.
5. **Penjelasan Kandidat (*Explainability*)**: Menghasilkan penjelasan terstruktur (mis. variasi imbuhan/sinonim atau perubahan urutan klausa).

## 2. Pemisahan Ketat 4 Lapisan Kemiripan & Modul Semantik Lokal

- **`EXACT`**: Kecocokan kata berurutan identik (`exact.py`).
- **`NEAR_EXACT`**: Kecocokan berurutan dengan penyisipan/penyuntingan ringan melalui penyelarasan biji 3-gram (`near_exact.py`).
- **`LEXICAL`**: Kemiripan kalimat berbasis fusi TF-IDF `char_wb` + morfologi/sinonim Bahasa Indonesia (`lexical.py`). Hanya masuk ke Similarity Index utama jika pengguna mengaktifkan opsi `include_lexical_in_index`.
- **`SEMANTIC` (Opsional, CPU-First, Lazy Loading)**: Modul [semantic.py](file:///d:/Projects/NaskahGuard/backend/app/engine/semantic.py) tidak pernah mengunduh model secara diam-diam dan **tidak pernah** dimasukkan ke Similarity Index utama secara otomatis (`counted_token_indices = set()`), melainkan hanya disajikan sebagai kandidat peninjauan manusia.

## 3. Audit Matematis Skor & Penjelasan Selisih Pembulatan `0,01%` (`scoring.py`)

Audit terhadap skenario nyata **`408` kata cocok unik dari `5.973` kata eligible**:
- **Exact Match**: `290 / 5.973 = 4,855181...%` → dibulatkan 2 desimal menjadi **`4,86%`**
- **Near-Exact Match**: `118 / 5.973 = 1,975556...%` → dibulatkan 2 desimal menjadi **`1,98%`**
- **Total Kata Cocok Unik**: `290 + 118 = 408` kata (**0 penghitungan ganda** baik lintas lapisan maupun lintas sumber berkat atribusi eksklusif di [attribution.py](file:///d:/Projects/NaskahGuard/backend/app/engine/attribution.py)).
- **Adjusted Similarity Index**: `408 / 5.973 = 6,830738...%` → dibulatkan 2 desimal menjadi **`6,83%`**.
- **Mengapa `4,86% + 1,98% = 6,84%` sedangkan Adjusted SI `6,83%`?** Karena kedua komponen mengalami pembulatan ke atas (`..55% -> ..6%` dan `..75% -> ..8%`), penjumlahan angka tampilan menghasilkan selisih pembulatan `+0,01%`.
- Pada Phase 9, `metrics.score_explanation` menyertakan nilai presisi 4–6 desimal sebelum pembulatan (`unrounded_adjusted_similarity`, `unrounded_exact_pct`, `unrounded_near_exact_pct`) beserta `rounding_note` otomatis yang ditampilkan langsung di accordion **"Penjelasan Perhitungan Similarity"**. Diuji secara permanen pada [test_phase9_upgrade.py](file:///d:/Projects/NaskahGuard/backend/tests/test_phase9_upgrade.py).
