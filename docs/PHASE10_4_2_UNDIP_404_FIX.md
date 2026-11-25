# Audit & Perbaikan Error HTTP 404 UNDIP Modal — NaskahGuard Phase 10.4.2

**Tanggal Audit & Perbaikan:** 26 November 2026  
**Target Endpoint UNDIP:** `https://eprints2.undip.ac.id/cgi/oai2` (prioritas) · `http://eprints.undip.ac.id/cgi/oai2` (legacy `301` redirect)  
**Pesan Error Awal di UI:** `"Gagal memproses — Not Found"` pada modal **Tambah Repositori Akademik**

---

## 1. Penelusuran Error (Trace & Reproduksi Nyata)

Pengujian langsung pada proses server lokal yang sedang aktif serta inspeksi *contract* API membuktikan **endpoint UNDIP tidak rusak**. Kegagalan HTTP 404 terjadi di sisi server API lokal yang belum ter-reload.

### Bukti Reproduksi Sebelum Perbaikan

| Pengujian | Target URL / Route | Method | Payload | Status & Body Aktual | Backend Route Seharusnya | Penyebab Sebenarnya |
|---|---|---|---|---|---|---|
| **Server aktif lama** (`127.0.0.1:8000`, PID `30456`, aktif sejak `22:26`) | `http://127.0.0.1:8000/openapi.json` | `GET` | — | HTTP `200` — hanya memuat **4 route OAI** (`/repositories`, `/verify`, `/harvest`, `/repositories/{id}`) | 19 route OAI di `backend/app/api/oai.py` | Proses `uvicorn` lama berjalan **tanpa `--reload`** sehingga route Phase 10.3–10.4.1 tidak ter-load |
| **Deteksi Otomatis via UI/Vite Proxy** | `http://127.0.0.1:5173/api/oai/auto-detect` → `127.0.0.1:8000` | `POST` | `{"base_url": "https://eprints2.undip.ac.id/cgi/oai2"}` | **HTTP `404`** `{"detail": "Not Found"}` | `@router.post("/auto-detect")` (`backend/app/api/oai.py`) | Route belum ada di proses uvicorn lama → FastAPI membalas `{"detail": "Not Found"}` → UI menampilkan *"Gagal memproses — Not Found"* |
| **Uji Koneksi via UI/Vite Proxy** | `http://127.0.0.1:5173/api/oai/test-connection` → `127.0.0.1:8000` | `POST` | `{"base_url": "https://eprints2.undip.ac.id/cgi/oai2", ...}` | **HTTP `404`** `{"detail": "Not Found"}` | `@router.post("/test-connection")` (`backend/app/api/oai.py`) | Sama: proxy Vite (`vite.config.ts`) meneruskan `/api` ke server `8000` yang usang |
| **Backend Terkini (`TestClient app.main:app`)** | `/api/oai/auto-detect` & `/api/oai/test-connection` | `POST` | Endpoint UNDIP HTTPS | **HTTP `200`** (`Undip Repository`, `READY`, 8/8 lulus, 6 format, 100 koleksi, 99 est. rekaman) | Route aktif `19` endpoint OAI | Kode backend pada disk sudah valid; masalah pemicu utama adalah *stale server* tanpa `--reload` |

### Celah Sekunder yang Ditemukan Saat Audit

1. **`scripts/dev.ps1`** tidak memakai `--reload` maupun pembersihan proses lama pada port `8000`/`5173`, sehingga pembaruan backend berisiko memunculkan 404 pada route baru.
2. **`frontend/src/api/client.ts` & `RepositoriesPage.tsx`** meneruskan `data.detail = "Not Found"` mentah ke `<AlertDescription>` tanpa membedakan *API route tidak ditemukan* vs *Endpoint OAI-PMH tidak ditemukan* vs kondisi OAI lain, serta tanpa menampilkan 5 elemen diagnostik.
3. **`backend/app/api/oai.py` (`OAITestConnectionRequest` & `add_oai_repository`)**:
   - `test-connection` belum menerima `timeout_sec` kustom (sebelumnya fixed `20s`, terlalu sempit untuk EPrints `ListRecords`).
   - Penambahan UNDIP lewat modal manual (`POST /api/oai/repositories`) belum otomatis menerapkan profil kebijakan UNDIP (`METADATA_ONLY_DEFAULT`, `METADATA_ALLOWED_FULLTEXT_RESTRICTED`, `default_download_pdfs=False`, `policies.html`).
4. **`RepositoriesPage.tsx` (`handleHarvest`)**: masih mengirim `download_pdfs: true` secara statis, bukan menghormati `repo.default_download_pdfs`.

---

## 2. Perbaikan yang Diterapkan

### Backend & Dev Script
- [dev.ps1](file:///d:/Projects/NaskahGuard/scripts/dev.ps1): otomatis menghentikan proses usang di port `8000` dan `5173` sebelum start serta menjalankan `uvicorn app.main:app --reload --reload-dir app`.
- [oai_catalog.py](file:///d:/Projects/NaskahGuard/backend/app/sources/oai_catalog.py): menambah helper `resolve_known_policy_profile()` agar UNDIP (`eprints2.undip.ac.id` & `eprints.undip.ac.id`) otomatis dikenali kebijakannya baik dari Katalog maupun Modal Manual.
- [oai.py](file:///d:/Projects/NaskahGuard/backend/app/api/oai.py):
  - `OAITestConnectionRequest` kini menerima `timeout_sec` dan otomatis menaikkan batas minimum timeout menjadi `35–40s` untuk EPrints/UNDIP.
  - `add_oai_repository` otomatis menautkan `legacy_url`, `policy_url`, `fulltext_policy="METADATA_ONLY_DEFAULT"`, `harvesting_permission_status="METADATA_ALLOWED_FULLTEXT_RESTRICTED"`, `default_download_pdfs=False`, dan menyimpan `record_count_estimate`.
- [oai_pmh.py](file:///d:/Projects/NaskahGuard/backend/app/sources/oai_pmh.py): menambah `classify_ui_failure_kind()` serta field `failure_kind`, `failure_kind_label`, `failure_stage`, `failure_http_status`, `failure_suggestion` pada laporan wizard.

### Frontend & Penanganan Error Terstruktur (Anti `"Not Found"` Generik)
- [client.ts](file:///d:/Projects/NaskahGuard/frontend/src/api/client.ts):
  - Mengganti lemparan string mentah `"Not Found"` dengan `ApiRequestError` + helper `toStructuredUiError()`.
  - Membedakan 5 kondisi secara tegas:
    1. **API route tidak ditemukan** (`API_ROUTE_NOT_FOUND`, HTTP 404 route `/api/...`)
    2. **Endpoint OAI-PMH tidak ditemukan** (`OAI_ENDPOINT_NOT_FOUND`, `HTTP_404` / `HTML_RESPONSE`)
    3. **Repository tidak memiliki record** (`EMPTY_RECORDS`, `noRecordsMatch`)
    4. **Metadata format tidak tersedia** (`UNAVAILABLE_METADATA_FORMAT`, `cannotDisseminateFormat` / `noMetadataFormats`)
    5. **Full-text dibatasi kebijakan** (`FULLTEXT_POLICY_RESTRICTED`, `POLICY_RESTRICTED` / `HTTP_403`)
- [StructuredErrorAlert.tsx](file:///d:/Projects/NaskahGuard/frontend/src/components/StructuredErrorAlert.tsx): komponen UI terpadu menampilkan **Tahap yang gagal**, **URL yang sedang diuji**, **Status HTTP**, **Penyebab**, dan **Saran perbaikan**.
- [OAIWizardView.tsx](file:///d:/Projects/NaskahGuard/frontend/src/components/OAIWizardView.tsx), [RepositoriesPage.tsx](file:///d:/Projects/NaskahGuard/frontend/src/pages/RepositoriesPage.tsx), dan [RepositoryDetailPage.tsx](file:///d:/Projects/NaskahGuard/frontend/src/pages/RepositoryDetailPage.tsx): seluruh alur Deteksi, Uji Koneksi, Tambah/Simpan, Katalog, dan Panen menggunakan `StructuredErrorAlert`, menampilkan notice kebijakan UNDIP, dan mematuhi `default_download_pdfs=False`.

---

## 3. Hasil Verifikasi Setelah Perbaikan

1. **Pytest Regresi Penuh (`backend`):**
   - `pytest -v` (mencakup [test_phase10_4_2_undip_404.py](file:///d:/Projects/NaskahGuard/backend/tests/test_phase10_4_2_undip_404.py)): **`65 passed, 1 skipped, 0 failed`** (`18.32s`).
2. **Frontend Build:**
   - `npm run build` (`tsc -b && vite build`): **exit `0`** (`7.45s`).
3. **Playwright Full UI QA (`benchmark/run_phase10_ui_qa.py`):**
   - **`18/18` pengecekan viewport & rute lulus**, `console_errors: []`, `page_errors: []`, `bad_http: []`, `dark_mode_verified: true`.
4. **Live UI E2E Melalui Browser (`http://127.0.0.1:5173/repositories` → proxy Vite → `127.0.0.1:8000`):**
   - Bukti JSON: [phase10_4_2_undip_ui_e2e.json](file:///d:/Projects/NaskahGuard/benchmark/results/phase10_4_2_undip_ui_e2e.json)
   - Uji kasus gagal `HTTP 404` non-OAI (`https://example.org/cgi/oai2`): menampilkan **Endpoint OAI-PMH tidak ditemukan** beserta 5 field diagnostik (tidak ada pesan `"Gagal memproses — Not Found"`). Screenshot: [26_oai_structured_error_alert.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase10_after/26_oai_structured_error_alert.png)
   - Uji UNDIP nyata (`https://eprints2.undip.ac.id/cgi/oai2`):
     - Klik **Deteksi** (`POST /api/oai/auto-detect`): **HTTP `200`** (`Undip Repository`, platform `EPrints`).
     - Klik **Uji Koneksi (8 Tahap)** (`POST /api/oai/test-connection`): **HTTP `200`**, `Siap Dipanen`, `8 lulus`, 6 format (`didl`, `mets`, `oai_bibl`, `oai_dc`, `rdf`, `uketd_dc`), notice kebijakan *Mode Metadata Saja (Default)* tampil. Screenshot: [25_undip_modal_wizard_pass.png](file:///d:/Projects/NaskahGuard/docs/screenshots/phase10_after/25_undip_modal_wizard_pass.png)
     - Klik **Simpan Repositori** (`POST /api/oai/repositories`): **HTTP `201`**, tersimpan dengan `status="VERIFIED"`, `fulltext_policy="METADATA_ONLY_DEFAULT"`, `harvesting_permission_status="METADATA_ALLOWED_FULLTEXT_RESTRICTED"`, `default_download_pdfs=False`.
