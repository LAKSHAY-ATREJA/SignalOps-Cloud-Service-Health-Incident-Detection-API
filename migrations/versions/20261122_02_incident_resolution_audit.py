"""Add an auditable timestamp for incident resolution.

Revision ID: 20261122_02
Revises: 20261121_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_02"
down_revision = "20261121_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "resolved_at")
