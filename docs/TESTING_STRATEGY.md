# Strategi Pengujian & Evaluasi Benchmark — NaskahGuard

## 1. Pengujian Unit & Integrasi (`pytest`)
Seluruh pengujian dijalankan secara offline (tanpa akses jaringan) menggunakan `backend/.venv/Scripts/python -m pytest -q`:
- **Validasi & Keamanan**: Penolakan ekstensi tidak valid, magic bytes palsu, berkas biner disamarkan sebagai TXT, batas ukuran unggahan, sanitasi nama file & pencegahan path traversal, autentikasi token, dan penolakan startup non-loopback tanpa `API_TOKEN`.
- **Ingesti & Offset**: Ekstraksi PDF (fixture dibuat programatik via PyMuPDF), DOCX (`python-docx`), dan TXT; verifikasi invarian `original_text[char_start:char_end]` cocok persis dengan token aslinya; pelestarian teks asli; deteksi zona (`BIBLIOGRAPHY`, `TOC`, `COVER`, `BODY`).
- **Mesin Similarity**: Determinisme Winnowing, pencocokan Exact 100% pada dokumen identik, akurasi Exact pada potongan kalimat, deteksi Near-Exact pada substitusi/penghapusan ringan, deduplikasi overlap dua sumber (invarian: jumlah kontribusi == Adjusted SI), efek pengecualian pada Adjusted SI vs Raw SI, filter frasa umum, dan status keterbatasan cakupan saat korpus kosong.
- **Adapter Sumber Eksternal (Mock)**: Pengujian `OpenAlex`, `Crossref`, `arXiv`, dan `PMC` melalui `httpx.MockTransport` termasuk pelaporan `METADATA_ONLY`, penolakan `ACCESS_DENIED`, dan pencatatan `provider_queries`.
- **End-to-End API**: Siklus lengkap via FastAPI `TestClient` (unggah korpus -> unggah submission -> jalankan pemeriksaan -> tunggu `COMPLETED` -> cek laporan & viewer -> ekspor PDF berheader `%PDF-`, HTML, JSON -> `DELETE` menghapus seluruh turunan).

## 2. Benchmark Evaluasi 12 Kasus Sintetis (`benchmark/run_benchmark.py`)
Benchmark menghasilkan 12 skenario ber-ground-truth tingkat token dalam Bahasa Indonesia dan Inggris:
1. Dua dokumen identik (*Exact*).
2. Dokumen dengan beberapa kalimat salinan persis (*Exact*).
3. Dokumen dengan susunan kata sedikit berubah / substitusi ringan (*Near-Exact*).
4. Paragraf dengan penggantian sinonim (*Lexical / Near-Exact*).
5. Paragraf dengan kesamaan makna / parafrase (*Semantic / Lexical*).
6. Kutipan langsung dengan sitasi benar (*Exclusion verification*).
7. Daftar pustaka yang sama (*Bibliography exclusion*).
8. Frasa akademik umum di banyak dokumen (*Stop-gram & common phrase filter*).
9. Dua sumber dengan rentang kecocokan saling tumpang tindih (*Overlap attribution*).
10. Dokumen dengan simulasi hasil OCR buruk / noise karakter (*Degraded OCR resilience*).
11. Dokumen tanpa sumber pembanding (*Coverage honesty*).
12. Dokumen multibahasa ID-EN (*Multilingual handling*).

Metrik yang diukur secara nyata: **Precision**, **Recall**, **F1-Score**, **False Positive Rate (FPR)**, **False Negative Rate (FNR)** per lapisan (`EXACT`, `NEAR_EXACT`, `LEXICAL`), waktu pemrosesan (ms), dan memori puncak (`tracemalloc`).

> **Catatan Kejujuran:** Tabel hasil benchmark aktual akan ditulis ke bagian ini setelah `benchmark/run_benchmark.py` dijalankan pada Fase 6. Tidak ada klaim akurasi sebelum pengukuran dijalankan.
