# Katalog Penemuan Repositori Akademik Indonesia — Phase 10.4

**Implementasi Backend:** `backend/app/sources/oai_catalog.py`, `backend/app/models.py` (`RepositoryCatalogEntry` / tabel `oai_catalog`), `backend/app/api/oai.py`  
**Implementasi Frontend:** Tab **Katalog Repositori** pada `frontend/src/pages/RepositoriesPage.tsx`

---

## 1. Fitur Katalog yang Tersedia

1. **Pencarian Nama Universitas / Repositori / Domain**: `GET /api/oai/catalog?q=...&platform=...&status=...`
2. **Input Base URL Manual**: Modal **Daftarkan URL ke Katalog** (`POST /api/oai/catalog`) dengan input nama universitas, nama repositori, URL OAI-PMH, dan pilihan platform.
3. **Pilihan Platform**: `OJS`, `DSpace 7`, `DSpace Lama`, `EPrints`, `arXiv OAI-PMH`, atau `OAI-PMH Umum`.
4. **Status OAI-PMH Jujur**:
   - Semua entri awal pada katalog dimulai dengan status **`UNVERIFIED` (Belum Diuji)**.
   - Tidak ada repositori yang disebut "Aktif" atau "Terhubung" sebelum pengguna atau proses uji menjalankan verifikasi OAI-PMH nyata.
5. **Jumlah Koleksi & Format Metadata**: Diperbarui otomatis dari hasil live `ListSets` dan `ListMetadataFormats` saat tombol **Uji** (`POST /api/oai/catalog/{id}/test`) dijalankan, disertai tampilan dialog diagnostik 8 tahap (`OAIWizardView`).
6. **Tambahkan ke Daftar Pribadi**: Tombol **Tambahkan** (`POST /api/oai/catalog/{id}/add`) mempromosikan entri katalog ke daftar pribadi pengguna (`oai_repositories`) lengkap dengan daftar format dan koleksi yang terdeteksi.

---

## 2. Daftar Awal Katalog (Berbasis Endpoint Nyata)

Seluruh entri di bawah ini bersumber dari endpoint publik resmi (`.ac.id` & arsip terbuka) dan disemai dengan status awal `UNVERIFIED` (*Belum Diuji*):

| Universitas / Institusi | Repositori | Platform | URL Endpoint |
|---|---|---|---|
| Universitas Negeri Yogyakarta (UNY) | Jurnal Pendidikan Vokasi Otomotif (OJS UNY) | `ojs` | `https://journal.uny.ac.id/index.php/jpvo/oai` |
| IPB University | IPB Scientific Repository | `dspace_legacy` | `https://repository.ipb.ac.id/oai/request` |
| UIN Sunan Kalijaga Yogyakarta | Institutional Repository UIN Sunan Kalijaga | `eprints` | `http://digilib.uin-suka.ac.id/cgi/oai2` |
| Institut Teknologi Sepuluh Nopember (ITS) | ITS Repository | `eprints` | `http://repository.its.ac.id/cgi/oai2` |
| Institut Seni Indonesia (ISI) Yogyakarta | Digilib ISI Yogyakarta | `eprints` | `http://digilib.isi.ac.id/cgi/oai2` |
| Universitas Sebelas Maret (UNS) | JOIVE OJS UNS | `ojs` | `https://jurnal.uns.ac.id/index.php/joive/oai` |
| Universitas Islam Indonesia (UII) | DSpace UII Repository | `dspace_legacy` | `https://dspace.uii.ac.id/oai/request` |
| Universitas Muhammadiyah Malang (UMM) | EPrints UMM Repository | `eprints` | `https://eprints.umm.ac.id/cgi/oai2` |
| STIKOM Yos Sudarso Purwokerto | SYS Digital Repository (DSpace 7) | `dspace7` | `https://digilib.stikomyos.ac.id/server/oai/request` |
| Cornell University (Open Archive) | arXiv Public OAI-PMH | `arxiv` | `https://oaipmh.arxiv.org/oai` |
