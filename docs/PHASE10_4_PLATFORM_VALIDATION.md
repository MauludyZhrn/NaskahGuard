# Validasi Platform Live Repositori Akademik — NaskahGuard Phase 10.4

**Tanggal Pengujian Live:** 25 November 2026  
**Skrip Pengujian Live (Terpisah dari Mock Test):** `benchmark/run_phase10_4_live_platform_validation.py`  
**Bukti Output JSON:** `benchmark/results/phase10_4_live_platform_validation.json`

---

## 1. Prinsip Pengujian & Kejujuran

1. Seluruh URL uji berasal dari endpoint publik resmi (`.ac.id` dan referensi resmi DSpace), tanpa mengarang URL kampus.
2. Live test dijalankan pada database SQLite sementara yang terisolasi dengan batas sopan (`max_records=3`, `max_downloads=2`).
3. Hasil **tidak diklaim universal**: tiap repositori di dunia nyata memiliki kebijakan firewall/WAF (`403`), akses PDF terbatas (login mahasiswa), atau *timeout* jaringan.

---

## 2. Matriks Kemampuan Live per Platform

| Platform & Endpoint Uji | Identify | ListMetadataFormats | ListSets | ListRecords | GetRecord | ResumptionToken | PDF Discovery | PDF Download | Ekstraksi Teks | Indeks Lokal | Uji Plagiasi | Status Akhir |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **OJS** — UNY (`https://journal.uny.ac.id/index.php/jpvo/oai`) | LULUS | LULUS (4) | LULUS (2) | LULUS | LULUS | LULUS | LULUS | LULUS (2) | LULUS | LULUS (2) | **LULUS (94.53%)** | **TERVALIDASI FULL-TEXT** |
| **EPrints** — UIN Sunan Kalijaga (`http://digilib.uin-suka.ac.id/cgi/oai2`) | LULUS | LULUS (6) | LULUS (100) | LULUS | LULUS | LULUS | LULUS (3) | LULUS (2) | LULUS | LULUS (2) | **LULUS (94.44%)** | **TERVALIDASI FULL-TEXT** |
| **DSpace Lama** — IPB (`https://repository.ipb.ac.id/oai/request`) | LULUS | LULUS (12) | LULUS (100) | LULUS | LULUS | LULUS | LULUS (2) | GAGAL (akses terbatas) | — | 0 | — | **TERVALIDASI METADATA SAJA** |
| **DSpace 7 (Referensi Resmi)** — DSpace Demo (`https://demo.dspace.org/server/oai/request`) | LULUS | LULUS (14) | LULUS (31) | LULUS | `idDoesNotExist` | LULUS | 0 (sampel demo) | — | — | 0 | — | **TERVALIDASI PROTOKOL/METADATA** |
| **DSpace 7 (Indonesia)** — STIKOM Yos Sudarso (`https://digilib.stikomyos.ac.id/server/oai/request`) | TIMEOUT | — | — | — | — | — | — | — | — | — | — | **BELUM TERVALIDASI LIVE (Timeout)** |

### Observasi Tambahan saat Probe Awal (`task-1998`)
- **EPrints Aktif Lainnya:** `http://repository.its.ac.id/cgi/oai2` (`READY`, 100 koleksi) dan `http://digilib.isi.ac.id/cgi/oai2` (`READY`, 69 koleksi) juga merespons valid.
- **Endpoint Menolak / Timeout:** `https://dspace.uii.ac.id/oai/request` (`HTTP 403`), `https://eprints.umm.ac.id/cgi/oai2` (`HTTP 403`), dan `https://jurnal.uns.ac.id/index.php/joive/oai` (`TIMEOUT`). Hal ini menegaskan pentingnya tombol **Uji Konektivitas** per repositori di Katalog serta pemisahan status `Belum Diuji` vs `Terhubung` vs `Kendala`.

---

## 3. Batasan & Celah yang Didokumentasikan secara Terbuka

- **DSpace 7 Indonesia:** Belum ada endpoint DSpace 7 kampus Indonesia yang merespons tanpa timeout dalam uji jaringan saat ini (`digilib.stikomyos.ac.id` timeout); kemampuan `/server/oai/request` dan `/server/api/core/bitstreams/.../content` tetap teruji melalui simulasi mock lengkap (`test_dspace7_auto_detect_and_bitstream_harvest`) serta verifikasi protokol live terhadap `https://demo.dspace.org/server/oai/request`.
- **DSpace Lama (IPB):** Protokol OAI-PMH lengkap tervalidasi (`12` format metadata, `100` koleksi), tetapi berkas PDF publik gagal diunduh (`2` failed PDF) karena pembatasan akses di server sumber, sehingga sistem dengan benar **tidak mengklaim atau mengindeks metadata sebagai full-text**.
