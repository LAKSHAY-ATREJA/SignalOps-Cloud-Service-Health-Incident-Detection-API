"""Persist an operator reason for incident resolution.

Revision ID: 20261122_03
Revises: 20261122_02
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_03"
down_revision = "20261122_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("resolution_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "resolution_reason")
