# Peta Jalan Pengembangan (Roadmap) — NaskahGuard

## Status Rilis Saat Ini (MVP Lokal End-to-End)
- Ingesti PDF (PyMuPDF & `pypdf`), DOCX (`python-docx`), dan TXT dengan pelestarian teks asli & pemetaan offset karakter.
- Mesin similarity 5 lapis (Exact, Near-Exact Winnowing + MinHash/LSH + Seed-Extend, Lexical TF-IDF + BM25, Semantic opsional, Source Attribution).
- Perhitungan Similarity Index transparan bebas hitung ganda dengan atribusi eksklusif & pengecualian fleksibel.
- Adapter korpus lokal serta adapter resmi OpenAlex, Crossref, arXiv, dan PubMed Central (nonaktif default).
- Antarmuka web React berbahasa Indonesia (tema terang/gelap), penampil perbandingan dua panel, analitik visual, diagram alur berangka nyata, serta ekspor PDF/HTML/JSON.

## Pengembangan Tahap Lanjut
1. **Skala Korpus Besar dengan PostgreSQL GIN + `bigint[]`**: Mengaktifkan penyimpanan array fingerprint `bigint[]` terindeks GIN serta tabel `fingerprint_df` ala Noplag Engine untuk jutaan segmen dokumen.
2. **Worker Terdistribusi (Redis / RQ / Celery)**: Memisahkan proses antrean ke worker terpisah di luar proses HTTP FastAPI untuk konkurensi tinggi multi-pengguna.
3. **Ekstraksi PDF Lanjutan (MinerU Lokal / OCR Batch)**: Integrasi pipeline OCR lokal otomatis untuk dokumen pindaian multi-kolom dan rumus matematika LaTeX, serta opsi MinerU Cloud *opt-in* eksplisit.
4. **Indeks Semantik Vektor (`pgvector` / FAISS)**: Menyimpan embedding kalimat korpus secara persisten untuk pencarian Lapisan 4 berkecepatan tinggi pada korpus besar.
5. **Evaluasi Korpus Standar Eksternal**: Pengujian menggunakan subset PAN-PC-11 dan korpus karya ilmiah Indonesia beranotasi terbuka.
6. **Manajemen Multi-Tenant & SSO Institusi**: Dukungan otentikasi OIDC/OAuth2 dan pemisahan ruang kerja per fakultas atau jurnal.
