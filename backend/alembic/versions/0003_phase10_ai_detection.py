"""Phase 10 AI writing detection schema update.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25 19:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("checks") as batch_op:
        batch_op.add_column(
            sa.Column("mode", sa.String(length=24), nullable=False, server_default="PLAGIARISM_ONLY")
        )
        batch_op.add_column(sa.Column("ai_report", sa.JSON(), nullable=True))
    op.create_index("ix_checks_mode", "checks", ["mode"])


def downgrade() -> None:
    op.drop_index("ix_checks_mode", table_name="checks")
    with op.batch_alter_table("checks") as batch_op:
        batch_op.drop_column("ai_report")
        batch_op.drop_column("mode")
