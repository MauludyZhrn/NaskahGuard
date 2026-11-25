"""Phase 10.4.1 UNDIP EPrints integration, policy metadata, and catalog presets.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26 01:02:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.add_column(sa.Column("legacy_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("policy_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(
            sa.Column("fulltext_policy", sa.String(length=64), nullable=False, server_default="OPEN_PUBLIC_PDF")
        )
        batch_op.add_column(
            sa.Column(
                "harvesting_permission_status",
                sa.String(length=64),
                nullable=False,
                server_default="OPEN_UNRESTRICTED",
            )
        )
        batch_op.add_column(
            sa.Column("default_download_pdfs", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("record_count_estimate", sa.Integer(), nullable=True))

    with op.batch_alter_table("oai_catalog") as batch_op:
        batch_op.add_column(sa.Column("legacy_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("policy_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(
            sa.Column("fulltext_policy", sa.String(length=64), nullable=False, server_default="OPEN_PUBLIC_PDF")
        )
        batch_op.add_column(
            sa.Column(
                "harvesting_permission_status",
                sa.String(length=64),
                nullable=False,
                server_default="OPEN_UNRESTRICTED",
            )
        )
        batch_op.add_column(
            sa.Column("default_download_pdfs", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "requires_verification_before_save",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("record_count_estimate", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("oai_catalog") as batch_op:
        batch_op.drop_column("record_count_estimate")
        batch_op.drop_column("requires_verification_before_save")
        batch_op.drop_column("default_download_pdfs")
        batch_op.drop_column("harvesting_permission_status")
        batch_op.drop_column("fulltext_policy")
        batch_op.drop_column("policy_url")
        batch_op.drop_column("legacy_url")

    with op.batch_alter_table("oai_repositories") as batch_op:
        batch_op.drop_column("record_count_estimate")
        batch_op.drop_column("default_download_pdfs")
        batch_op.drop_column("harvesting_permission_status")
        batch_op.drop_column("fulltext_policy")
        batch_op.drop_column("policy_url")
        batch_op.drop_column("legacy_url")
