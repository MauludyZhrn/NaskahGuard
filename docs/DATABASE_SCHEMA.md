# Skema Basis Data — NaskahGuard

## 1. Diagram ERD (Entity-Relationship Diagram)

```mermaid
erDiagram
    DOCUMENTS ||--o{ SEGMENTS : "has"
    DOCUMENTS ||--o{ FINGERPRINTS : "has"
    DOCUMENTS ||--o{ CHECKS : "checked_as_submission"
    CHECKS ||--o{ MATCHES : "produces"
    DOCUMENTS ||--o{ MATCHES : "matched_as_source"
    CHECKS ||--o{ CHECK_SOURCES : "attributes"
    DOCUMENTS ||--o{ CHECK_SOURCES : "referenced_in"
    CHECKS ||--o{ PROVIDER_QUERIES : "logs"

    DOCUMENTS {
        string id PK
        string role "SUBMISSION|CORPUS|EXTERNAL"
        string filename
        string stored_name
        string file_hash
        string file_type
        string mime
        int size_bytes
        string language
        int page_count
        int word_count
        string title
        json authors
        int year
        string doi
        string url
        string source_type
        string access_status
        string extraction_method
        float extraction_confidence
        json ocr_pages
        blob minhash
        string provider
        string external_id
        datetime retrieved_at
        datetime created_at
        json extra
    }

    SEGMENTS {
        int id PK
        string document_id FK
        int page_number
        int paragraph_number
        int sentence_number
        int char_start
        int char_end
        int token_start
        int token_end
        text original_text
        text normalized_text
        string section_label
        string zone "BODY|BIBLIOGRAPHY|TOC|COVER"
    }

    FINGERPRINTS {
        int id PK
        string document_id FK
        bigint hash
        int token_pos
    }

    CHECKS {
        string id PK
        string report_number UK
        string document_id FK
        string status "QUEUED|PROCESSING|COMPLETED|FAILED"
        string stage
        int progress
        json settings
        json stage_counts
        json metrics
        json coverage
        text error
        datetime created_at
        datetime started_at
        datetime finished_at
    }

    MATCHES {
        int id PK
        string check_id FK
        string source_document_id FK
        string layer "EXACT|NEAR_EXACT|LEXICAL|SEMANTIC"
        int sub_token_start
        int sub_token_end
        int sub_char_start
        int sub_char_end
        int src_token_start
        int src_token_end
        int src_char_start
        int src_char_end
        int src_page
        int matched_words
        float score
        text sub_excerpt
        text src_excerpt
        string excluded_reason
        bool counted
    }

    CHECK_SOURCES {
        int id PK
        string check_id FK
        string source_document_id FK
        int rank
        int matched_words_exclusive
        int matched_words_total
        float contribution_pct
        json layers
    }

    PROVIDER_QUERIES {
        int id PK
        string check_id FK
        string provider
        string query
        string status
        int result_count
        int http_status
        text error
        datetime started_at
        int duration_ms
    }

    AUDIT_LOGS {
        int id PK
        datetime ts
        string actor
        string action
        string target_type
        string target_id
        json details
    }

    APP_SETTINGS {
        string key PK
        json value
        datetime updated_at
    }
```

## 2. Dukungan Dialek SQLite & PostgreSQL
- **SQLite (Default)**: Mode WAL (`PRAGMA journal_mode=WAL`) dan `busy_timeout=5000` agar akses baca API dan penulisan worker latar belakang berjalan aman bersamaan. Indeks B-tree pada `fingerprints(hash)` mempercepat lookup kandidat.
- **PostgreSQL (Opsional Produksi)**: Migrasi Alembic mendeteksi dialek `postgresql` secara otomatis untuk membuat ekstensi `pg_trgm` dan indeks GIN trigram (`gin_trgm_ops`) pada `segments.normalized_text`, serta opsional ekstensi `pgvector` apabila `ENABLE_PGVECTOR=true`.
