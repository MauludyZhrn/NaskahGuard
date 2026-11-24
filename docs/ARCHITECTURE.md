# Arsitektur Sistem — NaskahGuard

## 1. Gambaran Umum
NaskahGuard menggunakan arsitektur monolit modular yang memisahkan lapisan antarmuka (React + Vite), API & antrean latar belakang (FastAPI + Worker), modul ingesti dokumen, mesin similarity multi-lapis, adapter penemuan sumber, penyimpanan data relasional + berkas lokal, serta generator laporan.

## 2. Diagram Arsitektur Sistem

```mermaid
flowchart TB
    User["Pengguna / Peneliti / Reviewer"] --> UI["Frontend React + TypeScript + Vite<br/>(Bahasa Indonesia, Tema Terang/Gelap)"]
    UI -->|"REST API /api/* (Proxy Vite)"| API["Backend FastAPI + Pydantic<br/>(Auth Token & Rate Limiter)"]

    subgraph BackendCore["Backend Python (Modular)"]
        API --> Ingestion["Document Ingestion Engine<br/>(PyMuPDF/pypdf, python-docx, OCR Opsional)"]
        API --> Worker["Background Queue Worker<br/>(ThreadPoolExecutor + DB Job State)"]
        API --> Reports["Report Builder & Exporters<br/>(ReportLab PDF, Jinja2 HTML, JSON)"]

        Worker --> Pipeline["Multi-Layer Similarity Pipeline"]
        Pipeline --> L1["L1: Exact Match (N-Gram Hash)"]
        Pipeline --> L2["L2: Near-Exact (Winnowing, MinHash, Seed-Extend)"]
        Pipeline --> L3["L3: Lexical (TF-IDF Char N-Gram + BM25)"]
        Pipeline --> L4["L4: Semantic Opsional (Sentence Embeddings)"]
        Pipeline --> NoplagOpt["Adapter Opsional Noplag Engine<br/>(Loopback HTTP Only)"]
        Pipeline --> Scoring["Scoring, Exclusion Mask & Exclusive Attribution"]
        Pipeline --> Discovery["Source Discovery Engine"]
    end

    Discovery --> LocalCorpus["Korpus Lokal Terindeks"]
    Discovery --> ExtAdapters["Adapter Resmi (Off by Default):<br/>OpenAlex, Crossref, arXiv, PMC"]

    Ingestion --> Storage[("Local Storage<br/>uploads/, extracted/, reports/")]
    API --> DB[("Database SQLAlchemy + Alembic<br/>SQLite (Default) / PostgreSQL (GIN/pg_trgm)")]
    Worker --> DB
    Reports --> DB
```

## 3. Diagram Aliran Data (Data Flow)

```mermaid
flowchart LR
    File["Berkas Unggahan<br/>(PDF / DOCX / TXT)"] --> Validate["Validasi Ekstensi,<br/>Magic Bytes & Ukuran"]
    Validate --> SaveRaw["Simpan Berkas Aman<br/>(UUID filename)"]
    SaveRaw --> Extract["Ekstraksi Teks Asli +<br/>Metadata + Posisi Halaman"]
    Extract --> SaveExtracted["Simpan JSON Terstruktur<br/>(Teks Asli + Token + Offset)"]
    SaveExtracted --> IndexCorpus{"Peran Dokumen?"}
    IndexCorpus -->|"CORPUS / EXTERNAL"| PersistIndex["Simpan Segmen, Winnowing<br/>Fingerprints & MinHash"]
    IndexCorpus -->|"SUBMISSION"| CreateCheck["Buat Job Check (QUEUED)"]
    CreateCheck --> MatchEngine["Jalankan Pipeline Similarity<br/>(L1-L4 + Exclusions)"]
    PersistIndex --> MatchEngine
    MatchEngine --> PersistResults["Simpan Matches, CheckSources,<br/>Metrics & Stage Counts"]
    PersistResults --> Render["Viewer Interaktif & Ekspor<br/>(PDF / HTML / JSON)"]
```

## 4. Keputusan Desain & Keterbatasan Lingkungan
1. **Basis Data Portabel (SQLite Default, PostgreSQL Siap Pakai)**: SQLite dipilih sebagai default agar NaskahGuard langsung berjalan di Windows tanpa instalasi server DB terpisah. Skema SQLAlchemy dan migrasi Alembic mendukung PostgreSQL beserta ekstensi `pg_trgm` dan indeks GIN secara otomatis saat `DATABASE_URL` mengarah ke PostgreSQL.
2. **Worker Antrean Latar Belakang**: Pemrosesan pemeriksaan berjalan asinkron melalui `ThreadPoolExecutor` dan status persisten di tabel `checks` (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`). Saat aplikasi dimulai ulang, tugas yang tertunda dipulihkan kembali.
3. **Pemisahan Service Noplag Engine**: Jika pengguna menjalankan Noplag Engine secara lokal pada PostgreSQL, `NoplagAdapter` dapat diaktifkan melalui `NOPLAG_ENGINE_URL` yang dibatasi ketat pada host loopback (`127.0.0.1`/`localhost`).
