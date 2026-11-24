# Desain Algoritma — NaskahGuard

## 1. Alur Pemrosesan Dokumen (Document Processing Flow)

```mermaid
flowchart TD
    A["Berkas Unggahan"] --> B["Validasi Ekstensi, MIME, Magic Bytes & Batas Ukuran"]
    B --> C["Sanitasi Nama File & Hashing SHA-256"]
    C --> D{"Tipe Berkas"}
    D -->|"PDF"| E["Ekstraksi per Halaman (PyMuPDF / pypdf)"]
    E -->|"Halaman < 20 char & OCR aktif"| F["Render 300 DPI + Tesseract OCR<br/>Catat extraction_confidence"]
    E -->|"PDF Teks"| G["Gabungkan Teks per Halaman"]
    D -->|"DOCX"| H["Ekstrak Paragraf & Tabel (python-docx)<br/>Deteksi Page Break Eksplisit"]
    D -->|"TXT"| I["Decode UTF-8-SIG / CP1252"]
    F --> J["Simpan Teks Asli Utuh (Immutable)"]
    G --> J
    H --> J
    I --> J
    J --> K["Tokenisasi Unicode atas Teks Asli<br/>& Pemetaan Offset Karakter (char_start, char_end)"]
    K --> L["Normalisasi Token (NFKC, Casefold, Hapus Diakritik)<br/>Tanpa Mengubah Teks Asli"]
    L --> M["Segmentasi Paragraf & Kalimat (Daftar Singkatan ID/EN)"]
    M --> N["Deteksi Struktur Zona<br/>(BODY / BIBLIOGRAPHY / TOC / COVER) & Bab"]
```

## 2. Alur Deteksi Kemiripan Multi-Lapis (Similarity Detection Flow)

```mermaid
flowchart TD
    Sub["Dokumen Submission (Tokens + Segments + Winnowing + MinHash)"] --> Cand["Retrieval Kandidat"]
    Cand --> W["Winnowing k=5, w=4 (64-bit Blake2b)<br/>Filter Stop-Gram DF > max(3, 30% korpus)<br/>Minimal 2 irisan hash"]
    Cand --> MH["MinHash (128 perm, 3-gram) + LSH (t=0.2)"]
    W --> Pool["Pool Kandidat Korpus + Eksternal Full-Text"]
    MH --> Pool

    Pool --> L1["Lapisan 1: Exact Matching<br/>Index n-gram kata (n=min_match_words)<br/>Extend maju maksimal selama token identik"]
    Pool --> L2["Lapisan 2: Near-Exact Matching<br/>Seed 3-gram -> Kelompokkan per diagonal (gap <= 4)<br/>SequenceMatcher: hanya blok 'equal' yang dihitung"]
    Pool --> L3["Lapisan 3: Lexical Similarity<br/>Kalimat sisa (<50% tertutup, >=6 kata)<br/>TF-IDF char_wb (3,5) Cosine >= 0.70 (+ Top-5 BM25)"]
    Sub --> L4["Lapisan 4: Semantic Similarity (Opsional)<br/>Multilingual Sentence Embeddings Cosine >= 0.80<br/>Kandidat Tinjauan Saja"]

    L1 --> Mask["Terapkan Masker Pengecualian<br/>(Bibliografi, Sitasi, Kutipan, Daftar Isi, Sampul, Frasa Umum)"]
    L2 --> Mask
    L3 --> Mask
    Mask --> Dedup["Resolusi Overlap & Atribusi Eksklusif<br/>(EXACT > NEAR_EXACT > Panjang > Source ID)"]
    Dedup --> Score["Hitung Adjusted SI, Raw SI, & Kontribusi per Sumber"]
```

## 3. Rincian Teknis Tiap Lapisan

### A. Hashing & Winnowing
- Tokenisasi kata menggunakan ekspresi reguler Unicode `\w+(?:[-'’]\w+)*`.
- Setiap token dinormalisasi (NFKC, casefold, penghapusan tanda diakritik kombinasi, penyatuan ligatur) sementara offset karakter (`char_start`, `char_end`) menunjuk persis ke teks asli.
- Hash 64-bit dihitung menggunakan `blake2b(digest_size=8)` atas gabungan k-gram kata (`k = 5`) dan dikonversi ke bilangan bulat bertanda 64-bit agar kompatibel dengan kolom `BIGINT` SQLite dan PostgreSQL.
- Pemilihan fingerprint menggunakan algoritma **Winnowing** (Schleimer, Wilkerson, Aiken 2003) dengan ukuran jendela `w = 4` dan aturan pemilihan nilai hash terkecil paling kanan (*rightmost minimum*).
- **Alternatif Skala Besar (PostgreSQL + Noplag Pattern)**: Pada korpus jutaan segmen di PostgreSQL, fingerprint dapat disimpan sebagai kolom `bigint[]` terindeks GIN (`array_ops`) sebagaimana diimplementasikan pada Noplag Engine.

### B. Exact Matching (Lapisan 1)
- Membangun indeks posisi n-gram kata sumber berukuran `n = min_match_words` (default 8).
- Untuk setiap posisi kecocokan `(i, j)` yang bukan kelanjutan langsung dari `(i-1, j-1)`, rentang diperluas maju selama token ter-normalisasi identik.
- Rentang dengan panjang `>= min_match_words` disimpan dan dideduplikasi per sumber.

### C. Near-Exact Matching (Lapisan 2)
- Seed dibangun dari 3-gram kata yang sama antara submission dan kandidat.
- Seed dikelompokkan berdasarkan selisih diagonal kasar dan digabungkan apabila jarak antar seed `<= 4` token pada kedua sisi.
- Wilayah kandidat yang panjangnya `>= min_match_words`, memiliki kepadatan seed `>= 0.5`, dan belum tertutup penuh oleh Lapisan 1 diselaraskan dengan `difflib.SequenceMatcher(autojunk=False)`.
- Demi ketepatan audit, **hanya token pada blok `equal`** dihitung sebagai kata cocok (meskipun highlight region dapat menampilkan konteks wilayah modifikasi).

### D. Lexical & Semantic (Lapisan 3 & 4)
- **Lapisan 3 (Lexical)**: Kalimat submission dengan cakupan exact/near `< 50%` dan panjang `>= 6` kata dibandingkan menggunakan `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))` dengan ambang cosine `>= 0.70`. Kandidat diambil dari pool L1/L2 ditambah top-5 dokumen dari ranking BM25 (`rank-bm25`).
- **Lapisan 4 (Semantic)**: Nonaktif secara default. Bila diaktifkan dan pustaka `sentence-transformers` terpasang, menggunakan model multibahasa (`paraphrase-multilingual-MiniLM-L12-v2`) dengan ambang cosine `>= 0.80`. Hasil Lapisan 4 **tidak pernah** masuk ke Similarity Index utama dan dilabeli sebagai kandidat untuk ditinjau.
