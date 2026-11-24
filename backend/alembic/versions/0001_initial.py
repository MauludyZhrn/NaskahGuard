"""Initial schema for NaskahGuard (SQLite + PostgreSQL dialect-aware).

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    settings = get_settings()

    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        if settings.ENABLE_PGVECTOR:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=24), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("authors", sa.JSON(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("access_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_method", sa.String(length=24), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=False),
        sa.Column("ocr_pages", sa.JSON(), nullable=True),
        sa.Column("minhash", sa.LargeBinary(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.UniqueConstraint("file_hash", "role", name="uq_documents_hash_role"),
    )
    op.create_index("ix_documents_role", "documents", ["role"])
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])

    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_number", sa.Integer(), nullable=False),
        sa.Column("sentence_number", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_start", sa.Integer(), nullable=False),
        sa.Column("token_end", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("section_label", sa.String(length=128), nullable=True),
        sa.Column("zone", sa.String(length=24), nullable=False),
    )
    op.create_index("ix_segments_document_id", "segments", ["document_id"])
    op.create_index("ix_segments_doc_seq", "segments", ["document_id", "sentence_number"])
    if dialect == "postgresql":
        op.execute(
            "CREATE INDEX ix_segments_norm_trgm ON segments USING gin (normalized_text gin_trgm_ops)"
        )

    op.create_table(
        "fingerprints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hash", sa.BigInteger(), nullable=False),
        sa.Column("token_pos", sa.Integer(), nullable=False),
    )
    op.create_index("ix_fingerprints_document_id", "fingerprints", ["document_id"])
    op.create_index("ix_fingerprints_hash", "fingerprints", ["hash"])
    op.create_index("ix_fingerprints_hash_doc", "fingerprints", ["hash", "document_id"])

    op.create_table(
        "checks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("report_number", sa.String(length=48), nullable=False, unique=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("stage_counts", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_checks_report_number", "checks", ["report_number"], unique=True)
    op.create_index("ix_checks_document_id", "checks", ["document_id"])
    op.create_index("ix_checks_status", "checks", ["status"])

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=36), sa.ForeignKey("checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer", sa.String(length=24), nullable=False),
        sa.Column("sub_token_start", sa.Integer(), nullable=False),
        sa.Column("sub_token_end", sa.Integer(), nullable=False),
        sa.Column("sub_char_start", sa.Integer(), nullable=False),
        sa.Column("sub_char_end", sa.Integer(), nullable=False),
        sa.Column("src_token_start", sa.Integer(), nullable=False),
        sa.Column("src_token_end", sa.Integer(), nullable=False),
        sa.Column("src_char_start", sa.Integer(), nullable=False),
        sa.Column("src_char_end", sa.Integer(), nullable=False),
        sa.Column("src_page", sa.Integer(), nullable=True),
        sa.Column("matched_words", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sub_excerpt", sa.Text(), nullable=False),
        sa.Column("src_excerpt", sa.Text(), nullable=False),
        sa.Column("excluded_reason", sa.String(length=32), nullable=True),
        sa.Column("counted", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_matches_check_id", "matches", ["check_id"])
    op.create_index("ix_matches_source_document_id", "matches", ["source_document_id"])

    op.create_table(
        "check_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=36), sa.ForeignKey("checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("matched_words_exclusive", sa.Integer(), nullable=False),
        sa.Column("matched_words_total", sa.Integer(), nullable=False),
        sa.Column("contribution_pct", sa.Float(), nullable=False),
        sa.Column("layers", sa.JSON(), nullable=False),
    )
    op.create_index("ix_check_sources_check_id", "check_sources", ["check_id"])
    op.create_index("ix_check_sources_source_document_id", "check_sources", ["source_document_id"])

    op.create_table(
        "provider_queries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=36), sa.ForeignKey("checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
    )
    op.create_index("ix_provider_queries_check_id", "provider_queries", ["check_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_logs_ts", "audit_logs", ["ts"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("audit_logs")
    op.drop_table("provider_queries")
    op.drop_table("check_sources")
    op.drop_table("matches")
    op.drop_table("checks")
    op.drop_table("fingerprints")
    op.drop_table("segments")
    op.drop_table("documents")
