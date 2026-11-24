"""Phase 7 schema upgrade: source acquisition tracking, deduplication fields, and OAI-PMH repository registry.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    with op.batch_alter_table("documents", recreate="auto" if is_sqlite else "never") as batch_op:
        batch_op.add_column(sa.Column("canonical_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("normalized_title", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("license", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("indexing_status", sa.String(length=32), nullable=False, server_default="FULLTEXT_INDEXED")
        )
        batch_op.add_column(sa.Column("alternate_urls", sa.JSON(), nullable=True))
        batch_op.create_index("ix_documents_canonical_url", ["canonical_url"])
        batch_op.create_index("ix_documents_normalized_title", ["normalized_title"])

    op.create_table(
        "source_acquisitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=36), sa.ForeignKey("checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("canonical_url", sa.String(length=1024), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("used_playwright", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_acquisitions_check_id", "source_acquisitions", ["check_id"])
    op.create_index("ix_source_acquisitions_status", "source_acquisitions", ["status"])

    op.create_table(
        "oai_repositories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False, unique=True),
        sa.Column("repo_type", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("identified_name", sa.String(length=512), nullable=True),
        sa.Column("metadata_prefix", sa.String(length=64), nullable=False),
        sa.Column("last_harvested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_datestamp", sa.String(length=32), nullable=True),
        sa.Column("records_harvested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fulltext_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oai_repositories")
    op.drop_table("source_acquisitions")
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    with op.batch_alter_table("documents", recreate="auto" if is_sqlite else "never") as batch_op:
        batch_op.drop_index("ix_documents_normalized_title")
        batch_op.drop_index("ix_documents_canonical_url")
        batch_op.drop_column("alternate_urls")
        batch_op.drop_column("indexing_status")
        batch_op.drop_column("license")
        batch_op.drop_column("normalized_title")
        batch_op.drop_column("canonical_url")
