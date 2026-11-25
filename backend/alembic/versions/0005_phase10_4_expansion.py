"""Phase 10.4 Indonesian academic repository expansion (catalog, filters, history, scheduling).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-26 00:18:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.add_column(sa.Column("year_from", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("year_to", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("keyword_filter", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("doc_type_filter", sa.String(length=128), nullable=True))
        batch_op.add_column(
            sa.Column("max_downloads", sa.Integer(), nullable=False, server_default="10")
        )
        batch_op.add_column(
            sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("schedule_interval_hours", sa.Integer(), nullable=False, server_default="24")
        )
        batch_op.add_column(sa.Column("next_scheduled_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("oai_harvest_records") as batch_op:
        batch_op.add_column(sa.Column("doc_type", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("subjects", sa.JSON(), nullable=True))

    op.create_table(
        "oai_harvest_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("oai_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger_mode", sa.String(length=24), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="RUNNING"),
        sa.Column("set_spec", sa.String(length=255), nullable=True),
        sa.Column("metadata_prefix", sa.String(length=64), nullable=True),
        sa.Column("filters_snapshot", sa.JSON(), nullable=True),
        sa.Column("records_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_matched_filter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_harvested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fulltext_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_only", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_oai_harvest_runs_repository_id", "oai_harvest_runs", ["repository_id"])

    op.create_table(
        "oai_catalog",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("university", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False, unique=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("platform_label", sa.String(length=64), nullable=False, server_default="OAI-PMH Umum"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("oai_status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("identified_name", sa.String(length=512), nullable=True),
        sa.Column("collections_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("supported_formats", sa.JSON(), nullable=True),
        sa.Column("available_sets", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oai_catalog_university", "oai_catalog", ["university"])
    op.create_index("ix_oai_catalog_name", "oai_catalog", ["name"])
    op.create_index("ix_oai_catalog_platform", "oai_catalog", ["platform"])
    op.create_index("ix_oai_catalog_oai_status", "oai_catalog", ["oai_status"])


def downgrade() -> None:
    op.drop_index("ix_oai_catalog_oai_status", table_name="oai_catalog")
    op.drop_index("ix_oai_catalog_platform", table_name="oai_catalog")
    op.drop_index("ix_oai_catalog_name", table_name="oai_catalog")
    op.drop_index("ix_oai_catalog_university", table_name="oai_catalog")
    op.drop_table("oai_catalog")

    op.drop_index("ix_oai_harvest_runs_repository_id", table_name="oai_harvest_runs")
    op.drop_table("oai_harvest_runs")

    with op.batch_alter_table("oai_harvest_records") as batch_op:
        batch_op.drop_column("subjects")
        batch_op.drop_column("doc_type")

    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.drop_column("next_scheduled_at")
        batch_op.drop_column("schedule_interval_hours")
        batch_op.drop_column("schedule_enabled")
        batch_op.drop_column("max_downloads")
        batch_op.drop_column("doc_type_filter")
        batch_op.drop_column("keyword_filter")
        batch_op.drop_column("year_to")
        batch_op.drop_column("year_from")
