# Laporan Audit & Diagnosis Implementasi Sebelum Phase 7

Tanggal: 2026-11-25

## 1. Ringkasan Temuan Audit
Audit dilakukan terhadap `backend/app/sources/`, `backend/app/engine/`, `backend/app/ingestion/`, `backend/app/reports/`, `backend/app/config.py`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/tests/`, dan `frontend/src/pages/`.

| Pertanyaan Diagnosis | Kondisi Saat Ini | Akar Masalah & Dampak |
|---|---|---|
| Apakah external search aktif? | Nonaktif secara default (`use_external_sources=False`). | Pemeriksaan hanya membandingkan terhadap korpus lokal kecuali pengguna mencentang opsi sumber eksternal. |
| Apakah provider hanya mencari metadata? | Crossref dan PMC (`pmc.py`) hanya menghasilkan `METADATA_ONLY`; `fetch_content()` mengembalikan `None`. | Sumber yang ditemukan tidak dapat masuk ke mesin pencocokan teks karena tidak memiliki full-text. |
| Apakah full-text benar-benar diunduh? | OpenAlex & arXiv mengunduh PDF hanya dari `best_oa_location.pdf_url` atau `arxiv.org/pdf/...` via `download_oa_pdf`, maksimal 3 hasil dari 2 kueri. Halaman HTML dan XML OA tidak didukung. | Banyak artikel jurnal open-access dan web publik yang berupa halaman HTML/XML atau berada di `locations` alternatif terlewat. |
| Apakah PDF dari URL dapat diekstrak? | Ya, jika URL mengarah langsung ke berkas `%PDF-` dan lolos `robots.txt` serta batas 25 MB. HTML/XML ditolak. | PDF dari arXiv/OpenAlex berhasil diekstrak, tetapi halaman artikel HTML atau JATS/TEI XML gagal diproses. |
| Apakah hasil masuk ke local corpus? | Ya, PDF eksternal yang berhasil diunduh disimpan sebagai `Document(role="EXTERNAL")` beserta segmen, fingerprint Winnowing, dan MinHash. | Berjalan baik untuk PDF, namun belum memiliki pelacakan `indexing_status`, lisensi, atau `alternate_urls`. |
| Apakah candidate retrieval berjalan terhadap hasil web? | Ya, `all_source_ids` mencakup `CORPUS` dan `EXTERNAL` untuk Winnowing, MinHash/LSH, dan BM25. | Karena belum ada General Web Search maupun crawler HTML/Playwright, belum ada sumber web publik yang terindeks. |
| Apakah URL sumber tercatat pada similarity report? | Ya, `CheckSource` mengembalikan `url`, `doi`, dan `provider` dari `Document`. | Namun hanya satu URL tersimpan; tidak ada penggabungan URL alternatif atau halaman *Internet Search Evidence*. |
| Apakah sumber yang sama terhitung berkali-kali? | Berpotensi ya jika artikel yang sama ditemukan di dua URL/repositori berbeda dengan biner PDF sedikit berbeda. | Deduplikasi saat ini hanya mengandalkan `(file_hash, role)`, belum memeriksa DOI, canonical URL, judul ternormalisasi, atau near-duplicate fingerprint. |

## 2. Kesenjangan Tambahan yang Teridentifikasi
1. **Query Generator Terlalu Sederhana**: `extract_query_keywords` hanya mengirim maksimal 2 kueri berbasis judul + TF-IDF global tanpa mempertimbangkan bab, paragraf, frasa eksak khas, atau variasi bahasa ID/EN.
2. **Belum Ada General Web Search & Playwright Crawler**: Tidak ada adapter SearXNG/Web Search, tidak ada SSRF guard IP privat/cloud metadata, dan `playwright` / `beautifulsoup4` belum terpasang.
3. **Belum Ada OAI-PMH Harvester**: Belum ada dukungan panen repositori akademik Indonesia (OJS, DSpace, EPrints) berbasis OAI-PMH.
4. **Cakupan & Pemantauan Terbatas**: Belum ada tabel/status per URL (`acquisition_events`), belum ada halaman `Source Discovery Monitor`, serta tab `Internet Search Evidence` dan `Search Coverage`.

## 3. Strategi Upgrade Phase 7
Upgrade dilakukan secara modular tanpa mengubah SQLite, tanpa menghapus algoritma similarity existing, dan tetap menjaga kompatibilitas seluruh fitur dan 17 tes Phase 1–6.
