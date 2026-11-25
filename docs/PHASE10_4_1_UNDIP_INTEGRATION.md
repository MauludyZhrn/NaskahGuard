# Audit & Perbaikan Integrasi EPrints UNDIP — NaskahGuard Phase 10.4.1

**Tanggal Verifikasi Live:** 26 November 2026  
**Skrip Pengujian Live:** `benchmark/run_phase10_4_1_undip_live.py`  
**Bukti Output JSON Live:** `benchmark/results/phase10_4_1_undip_live.json`  
**Suite Mock & Regresi:** `backend/tests/test_phase10_4_1_undip.py` (`pytest -v` → `62 passed, 1 skipped`)

---

## 1. Profil Endpoint Resmi UNDIP & Kebijakan Data

| Komponen | Nilai Resmi Terverifikasi |
|---|---|
| **Nama Preset** | `UNDIP Institutional Repository` |
| **Platform** | `EPrints` (`eprints`) |
| **Endpoint Baru (Prioritas)** | `https://eprints2.undip.ac.id/cgi/oai2` |
| **Endpoint Lama (Legacy)** | `http://eprints.undip.ac.id/cgi/oai2` |
| **Kebijakan Resmi** | `https://eprints2.undip.ac.id/policies.html` |
| **Mode Panen Bawaan** | **Metadata Saja (`METADATA_ONLY_DEFAULT`, `default_download_pdfs=False`)** |
| **Status Izin Panen** | `METADATA_ALLOWED_FULLTEXT_RESTRICTED` |

### Ringkasan Temuan `policies.html` & `robots.txt` UNDIP
1. **Metadata Policy (`policies.html`, HTTP 200):** Metadata boleh diakses gratis dan digunakan ulang secara non-komersial tanpa izin khusus selama menyertakan *OAI Identifier* atau tautan rekaman asli serta menyebut **UNDIP Repository**.
2. **Data Policy for Full-Text (`policies.html`, HTTP 200):** Akses terhadap sebagian/seluruh berkas penuh dikontrol (*"Full items must not be harvested by robots except transiently for citation analysis"*). Oleh karena itu, NaskahGuard **menonaktifkan bulk robot PDF harvesting untuk UNDIP secara default** dan menerapkan mode *Metadata Saja* sambil menyimpan URL asli repositori & atribusi.
3. **`robots.txt` (`HTTP 200`):** Mencantumkan `Content-Signal: search=yes,ai-train=no,use=reference` serta `Disallow: /cgi/`.

---

## 2. Diagnosis Kegagalan Sebelumnya & Kategorisasi Error

Audit langsung terhadap alur EPrints/UNDIP pada kode sebelumnya dan uji jaringan nyata mengidentifikasi hal berikut:

| Area Audit | Temuan & Perbaikan |
|---|---|
| **HTTP Redirect & Endpoint Lama** | `http://eprints.undip.ac.id/cgi/oai2` mengembalikan **HTTP `301`** ke `https://eprints.undip.ac.id:443/cgi/oai2?verb=Identify`. Diperbaiki dengan redirect aman *hop-by-hop* (validasi SSRF tiap lompatan) dan normalisasi port `:443`/`:80` pada `clean_oai_base_url()` tanpa mengubah URL pengguna sebelum diuji. |
| **HTTPS / TLS Handling** | Menambahkan penangkapan error sertifikat/TLS (`TLS_ERROR`) di `_safe_http_get` agar pesan asli TLS tampil eksplisit, bukan error koneksi generik. |
| **Timeout EPrints XML Besar** | Respons `ListRecords` EPrints UNDIP (~`141 KB` per halaman 99–100 rekaman) membutuhkan waktu respons lebih lama pada jaringan sibuk. Preset EPrints/UNDIP kini memakai timeout bawaan `45 detik` (katalog uji `35 detik`). |
| **EPrints Identifier & Ekstraksi URL** | EPrints menyertakan `<dc:relation>https://eprints2.undip.ac.id/id/eprint/4/</dc:relation>` dan URL PDF pada `<dc:identifier>` (termasuk ekstensi ganda seperti `.pdf.pdf`). Keduanya diekstrak bersih ke `landing_urls` dan `pdf_urls`. |
| **Klasifikasi 4 Kategori Kegagalan** | Setiap error di `OAIPMHProtocolError` & `OAIWizardView` kini dibedakan secara tegas ke:<br>1. `HTTP_CONNECTION_FAILURE` (*Kegagalan Koneksi HTTP / Jaringan*)<br>2. `OAI_PROTOCOL_FAILURE` (*Kegagalan Protokol OAI-PMH*)<br>3. `METADATA_PARSING_FAILURE` (*Kegagalan Parsing Metadata / XML*)<br>4. `FULLTEXT_ACCESS_RESTRICTION` (*Pembatasan Akses / Kebijakan Full-Text*) |

---

## 3. Hasil Pengujian Live Nyata (`https://eprints2.undip.ac.id/cgi/oai2`)

Seluruh 6 operasi OAI-PMH wajib berhasil dijalankan secara **live** tanpa memalsukan data:

1. **Identify:**
   - Status: **PASS (`HTTP 200`)**
   - `repositoryName`: `Undip Repository`
   - `baseURL`: `https://eprints2.undip.ac.id/cgi/oai2`
   - `protocolVersion`: `2.0`
   - `adminEmail`: `lisensi@live.undip.ac.id`
   - `earliestDatestamp`: `2019-12-30T01:04:29Z`
   - `deletedRecord`: `persistent`
   - `granularity`: `YYYY-MM-DDThh:mm:ssZ`
   - Catatan XML `Identify`: bagian deskripsi EPrints XML masih berisi teks placeholder *("No metadata policy defined..."*) disertai tautan ke `https://eprints2.undip.ac.id/policies.html` yang memuat kebijakan resmi sebenarnya.
2. **ListMetadataFormats:**
   - Status: **PASS (`HTTP 200`)**
   - Format tersedia (**6 format**): `didl`, `mets`, `oai_bibl`, `oai_dc`, `rdf`, `uketd_dc`.
3. **ListSets:**
   - Status: **PASS (`HTTP 200`)**
   - Jumlah koleksi terdeteksi & diindeks di katalog: **`100` set terambil** (paginasi awal).
4. **ListRecords (Halaman 1):**
   - Status: **PASS (`HTTP 200`)**
   - Jumlah rekaman diuji pada halaman 1: **`99` rekaman aktif** (`1` rekaman berstatus `deleted`), seluruhnya memiliki judul & penulis; **`99/99` memuat URL PDF pada `<dc:identifier>`** serta URL halaman repositori asli pada `<dc:relation>`.
5. **GetRecord:**
   - Status: **PASS (`HTTP 200`)**
   - Identifier uji: `oai:eprints2.undip.ac.id:4` → judul `"Lembar hasil Penilaian Sejawat Jurnal Ilmiah : Penyuluhan metode Pembuatan kapal nelayan berbahan kayu"`, URL asli `https://eprints2.undip.ac.id/id/eprint/4/`.
6. **ResumptionToken (Halaman 2):**
   - Token halaman 1: `metadataPrefix%3Doai_dc%26offset%3D108`
   - Status halaman 2: **PASS (`HTTP 200`)** — berhasil mengambil **`100` rekaman** dan menerima token lanjutan `metadataPrefix%3Doai_dc%26offset%3D215`.
7. **Status Akses Full-Text & Kepatuhan Kebijakan:**
   - Pengecekan header tunggal pada sampel (`HEAD .../Peer_Review_C-1_AKY.pdf.pdf`) merespons `HTTP 200` (`application/pdf`), namun sesuai kebijakan `policies.html` UNDIP yang melarang *robot bulk harvesting*, NaskahGuard menjalankan preset UNDIP dengan **`default_download_pdfs=False`**.
   - Pada uji panen API E2E (`max_records=5`): `5` rekaman metadata + URL PDF (`status="PDF_FOUND"`) + URL halaman asli `https://eprints2.undip.ac.id/id/eprint/...` tersimpan dengan **`fulltext_indexed=0`** (**0** pengunduhan massal PDF oleh robot).

---

## 4. Verifikasi Antarmuka & Regresi

- **Preset Katalog & Kebijakan UI:** Preset `UNDIP Institutional Repository` dimulai dengan status `UNVERIFIED` (*Belum Diuji*), mewajibkan uji konektivitas sebelum disimpan (`requires_verification_before_save=True`), dan menampilkan status koneksi, 6 format metadata, jumlah koleksi, estimasi record, label kebijakan full-text, serta status izin panen dalam Bahasa Indonesia.
- **Regresi Penuh:** `pytest -v` lulus **`62 passed, 1 skipped, 0 failed`**; `npm run build` lulus 0 error; `benchmark/run_phase10_ui_qa.py` lulus tanpa error.
