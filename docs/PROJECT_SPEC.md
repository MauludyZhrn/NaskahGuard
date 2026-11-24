# Spesifikasi Proyek — NaskahGuard

## 1. Ringkasan Eksekutif
**NaskahGuard** (nama aplikasi dapat diubah melalui konfigurasi `APP_NAME` / `VITE_APP_NAME`) adalah sistem kecerdasan deteksi kemiripan dan audit keaslian dokumen akademik berbahasa Indonesia yang beroperasi secara **local-first** dan **open-source-first**. Aplikasi ini dirancang untuk memeriksa skripsi, tesis, disertasi, artikel jurnal ilmiah, makalah, dan naskah akademik lainnya dengan alur kerja analitik serupa perangkat pemeriksa akademik profesional (seperti konsep pelaporan berlapis dan highlight sumber), namun sepenuhnya transparan, dapat diaudit, dan berjalan pada infrastruktur milik pengguna sendiri.

> **Pernyataan Jujur:** NaskahGuard bukan pengganti Turnitin/iThenticate dan **tidak pernah mengklaim** identik dengan Turnitin maupun memiliki akses ke basis data tertutup institusi/penerbit.

## 2. Prinsip Utama
1. **Local-First & Privasi Ketat**: Dokumen yang diunggah tetap tersimpan secara lokal. Tidak ada dokumen penuh yang dikirim ke layanan eksternal secara default.
2. **Transparansi & Auditabilitas**: Setiap kecocokan menampilkan cuplikan asli, posisi offset karakter/token, nomor halaman (bila tersedia), metode lapisan deteksi, dan identitas sumber yang dapat diverifikasi.
3. **Tanpa Data Fiktif**: Semua metrik, skor persentase, grafik, dan alur proses berasal dari perhitungan nyata. Jika cakupan sumber terbatas atau tidak ada kecocokan, sistem menyatakannya secara eksplisit.
4. **Modular & Dapat Dikembangkan**: Mendukung basis data SQLite (default Windows siap pakai) maupun PostgreSQL (dengan dukungan `pg_trgm` dan opsi `pgvector`), serta adapter sumber terbuka modular (OpenAlex, Crossref, arXiv, PMC).

## 3. Ruang Lingkup Fungsional
- **Ingesti Dokumen**: PDF berbasis teks (PyMuPDF / fallback `pypdf`), PDF hasil pindaian (fallback OCR lokal Tesseract opsional dengan pelaporan tingkat keyakinan), DOCX (`python-docx`), dan TXT (UTF-8 / CP1252).
- **Mesin Deteksi 5 Lapis**:
  1. *Exact Matching*: Frasa kata identik berbasis hash n-gram dan perluasan maksimal.
  2. *Near-Exact Matching*: Winnowing k-gram + MinHash/LSH retrieval + seed-and-extend alignment dengan `SequenceMatcher` konservatif.
  3. *Lexical Similarity*: Kemiripan kalimat berbasis TF-IDF char n-gram + BM25 (terpisah dari skor utama secara default).
  4. *Semantic Similarity*: Modul opsional embedding kalimat multibahasa (nonaktif default, hasil hanya sebagai kandidat tinjauan).
  5. *Source Attribution*: Penautan sumber lokal maupun eksternal beserta status akses (`FULL_TEXT_AVAILABLE`, `METADATA_ONLY`, `INDEXED_LOCALLY`, dll.).
- **Scoring & Pengecualian**: Perhitungan `SI = (Unique Matched Eligible Words / Total Eligible Words) × 100%` dengan union kata terverifikasi (anti-hitung ganda) dan atribusi eksklusif antar sumber. Mendukung pengecualian daftar pustaka, kutipan langsung, sitasi dalam teks, sampul, daftar isi, dan frasa umum.
- **Pelaporan Interaktif & Ekspor**: Antarmuka web React berbahasa Indonesia (tema terang & gelap), penampil perbandingan dua panel dengan highlight sinkron, analitik visual, diagram alur berangka nyata, serta ekspor ke **PDF**, **HTML**, dan **JSON**.

## 4. Kriteria Penerimaan Minimum
- Berjalan native di Windows tanpa ketergantungan wajib layanan berbayar atau cloud.
- Unggah PDF/DOCX/TXT, ekstraksi teks dengan pelestarian teks asli, pembandingan terhadap korpus lokal, deteksi exact & near-exact, perhitungan Similarity Index bebas overlap ganda, pengecualian aktif, ekspor PDF valid, dan cakupan uji otomatis serta benchmark terukur.
