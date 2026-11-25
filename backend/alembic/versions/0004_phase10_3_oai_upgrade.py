"""Phase 10.3 academic repository & OAI-PMH reliability upgrade.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25 23:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.add_column(sa.Column("platform_detected", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("selected_set", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("supported_formats", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("available_sets", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("resumption_token", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("harvest_state", sa.String(length=24), nullable=False, server_default="IDLE")
        )
        batch_op.add_column(sa.Column("last_test_report", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("metadata_saved_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("pdf_urls_found_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("pdf_accessible_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("fulltext_extracted_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("failed_records_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("rate_limit_delay_sec", sa.Float(), nullable=False, server_default="0.8")
        )
        batch_op.add_column(
            sa.Column("request_timeout_sec", sa.Integer(), nullable=False, server_default="20")
        )
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "oai_harvest_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("oai_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oai_identifier", sa.String(length=512), nullable=False),
        sa.Column("datestamp", sa.String(length=64), nullable=True),
        sa.Column("set_spec", sa.String(length=255), nullable=True),
        sa.Column("metadata_prefix", sa.String(length=64), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("authors", sa.JSON(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("rights", sa.String(length=255), nullable=True),
        sa.Column("landing_urls", sa.JSON(), nullable=True),
        sa.Column("pdf_urls", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="METADATA_SAVED"),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("repository_id", "oai_identifier", name="uq_oai_repo_identifier"),
    )
    op.create_index("ix_oai_harvest_records_repository_id", "oai_harvest_records", ["repository_id"])
    op.create_index("ix_oai_harvest_records_doi", "oai_harvest_records", ["doi"])
    op.create_index("ix_oai_harvest_records_status", "oai_harvest_records", ["status"])

    op.create_table(
        "oai_harvest_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("oai_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("stage", sa.String(length=48), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oai_harvest_logs_repository_id", "oai_harvest_logs", ["repository_id"])
    op.create_index("ix_oai_harvest_logs_created_at", "oai_harvest_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_oai_harvest_logs_created_at", table_name="oai_harvest_logs")
    op.drop_index("ix_oai_harvest_logs_repository_id", table_name="oai_harvest_logs")
    op.drop_table("oai_harvest_logs")

    op.drop_index("ix_oai_harvest_records_status", table_name="oai_harvest_records")
    op.drop_index("ix_oai_harvest_records_doi", table_name="oai_harvest_records")
    op.drop_index("ix_oai_harvest_records_repository_id", table_name="oai_harvest_records")
    op.drop_table("oai_harvest_records")

    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("request_timeout_sec")
        batch_op.drop_column("rate_limit_delay_sec")
        batch_op.drop_column("failed_records_count")
        batch_op.drop_column("fulltext_extracted_count")
        batch_op.drop_column("pdf_accessible_count")
        batch_op.drop_column("pdf_urls_found_count")
        batch_op.drop_column("metadata_saved_count")
        batch_op.drop_column("last_test_report")
        batch_op.drop_column("harvest_state")
        batch_op.drop_column("resumption_token")
        batch_op.drop_column("available_sets")
        batch_op.drop_column("supported_formats")
        batch_op.drop_column("selected_set")
        batch_op.drop_column("platform_detected")
