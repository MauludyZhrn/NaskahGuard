# Desain Mesin Pencarian & Diagnostik Sumber Eksternal (Phase 9)

Dokumen ini merinci arsitektur penemuan sumber akademik & web publik pada Phase 9, termasuk pemisahan ketat antara pengujian offline dan konektivitas live internet.

## 1. Diagnostik Konektivitas Nyata (`GET /api/providers` & `POST /api/providers/diagnostics`)

Pada Phase 8, status provider belum melakukan verifikasi live secara eksplisit. Pada Phase 9 ([providers.py](file:///d:/Projects/NaskahGuard/backend/app/api/providers.py)):
- Setiap provider mengekspos atribut: `configured`, `enabled`, `reachable` (`true | false | null`), `last_checked`, `last_successful_request`, `last_error`, `request_count`, `result_count`, dan `timeout_count`.
- **Aturan Kejujuran Status**: Provider eksternal **tidak pernah** ditampilkan sebagai *Terverifikasi Aktif* (`reachable: true`) sebelum benar-benar berhasil merespons kueri pemeriksaan atau diagnostik live.
- Pengguna dapat menekan tombol **"Uji Konektivitas Provider"** pada halaman Monitor Penemuan (`POST /api/providers/diagnostics`) yang mengirim kueri uji publik non-privat (`"winnowing document fingerprinting"`) secara paralel ke provider yang terkonfigurasi.
- Provider yang belum memiliki URL/kredensial (`SearXNG` tanpa `NG_SEARXNG_BASE_URL`, `Official Web API` tanpa kredensial, `OAI-PMH` dengan 0 repositori) ditampilkan secara eksplisit sebagai **`NOT_CONFIGURED`**.

## 2. Cakupan Provider Sumber Akademik & Web

| Provider | Tipe | Kunci API | Full-Text vs Metadata | Catatan Evaluasi Phase 9 |
| :--- | :--- | :---: | :--- | :--- |
| **Korpus Lokal (SQLite)** | Lokal | Tidak | Full-Text | Selalu aktif, tanpa pengiriman keluar jaringan. |
| **OpenAlex** | Akademik | Tidak | Full-Text OA (`best_oa_location`) + Metadata | Sumber utama OA lintas disiplin dengan polite pool `mailto`. |
| **Europe PMC** | Akademik | Tidak | Full-Text JATS XML + OA PDF | Sangat efektif untuk sains hayati, kesehatan, dan multidisiplin OA. |
| **DOAJ** *(Baru Phase 9)* | Akademik | Tidak | Full-Text Link/PDF + Metadata | [doaj.py](file:///d:/Projects/NaskahGuard/backend/app/sources/doaj.py) menjangkau ribuan jurnal Open Access terindeks DOAJ (termasuk OJS Indonesia). |
| **arXiv** | Akademik | Tidak | Full-Text PDF | Pracetak fisika, matematika, ilmu komputer; dibatasi maks. 6 kueri/cek untuk menghormati jeda 3 detik/permintaan. |
| **Crossref** | Akademik | Tidak | **Metadata Saja (`METADATA_ONLY`)** | Penemuan DOI & bibliografi; abstrak/metadata tidak pernah dianggap full-text. |
| **OAI-PMH Harvester** | Repositori | Tidak | Full-Text PDF (jika galley publik) | Mendukung OJS, DSpace, dan EPrints perguruan tinggi Indonesia. |
| **SearXNG Self-Hosted** | Web Umum | Tidak | URL Publik -> `BrowserExtractor` | Opsional via [docker-compose.searxng.yml](file:///d:/Projects/NaskahGuard/docker-compose.searxng.yml); berstatus `NOT_CONFIGURED` bila belum dijalankan. |
| **CORE / OpenAIRE** | Evaluasi | Wajib Key / Rate-Limit | Campuran | CORE v3 mewajibkan `CORE_API_KEY` terdaftar dan OpenAIRE Graph dominan metadata; oleh karena itu DOAJ dipilih sebagai adapter bawaan bebas kunci API yang paling stabil. |

## 3. Pembangkitan Kueri Cerdas Multi-Bab (`query_generator.py`)

- **Distribusi Merata per Bab**: Segmen `BODY` dikelompokkan berdasarkan `section_label` dan diambil secara *round-robin* sehingga setiap bab substantif mendapat peluang pencarian.
- **Peringkat IDF & Terminologi**: Menggabungkan bobot IDF lokal antar segmen, penyaringan *stopword* Bahasa Indonesia & Inggris, deteksi istilah teknis/asing, pencarian frasa persis berpetik, serta pencarian DOI dalam teks.
- **Deduplikasi Lintas Bab & Privasi**: Menggunakan tanda tangan *shingle* agar tidak mengirim kueri berulang lintas bab, menyaring ketat `BIBLIOGRAPHY`/`COVER`/`TOC`, dan menampilkan pemberitahuan privasi jelas kepada pengguna bahwa hanya potongan frasa/kata kunci terpilih yang dikirim keluar.

## 4. Akuisisi Progresif & Peringkat Relevansi

Alur progresif di [registry.py](file:///d:/Projects/NaskahGuard/backend/app/sources/registry.py):
`Dokumen -> Query Generation -> Academic & Public Web Search -> Candidate Ranking (HIGHLY_RELEVANT / RELEVANT / WEAK_CANDIDATE / UNRELATED) -> URL & SSRF Validation -> Isolated Browser/HTTP Extraction (termasuk follow otomatis meta citation_pdf_url pada landing page OA) -> Content-Hash & DOI Deduplication -> Local Indexing -> Similarity Matching -> Exclusive Attribution -> Reporting`.
