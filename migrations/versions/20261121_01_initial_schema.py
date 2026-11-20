"""Create the initial SignalOps schema with idempotent metric ingestion."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_services_name", "services", ["name"], unique=True)

    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_id", "idempotency_key", name="uq_metrics_service_idempotency_key"
        ),
    )
    op.create_index("ix_metrics_service_id", "metrics", ["service_id"])
    op.create_index("ix_metrics_metric_name", "metrics", ["metric_name"])
    op.create_index("ix_metrics_recorded_at", "metrics", ["recorded_at"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("metric_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=80), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("baseline_mean", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["metric_id"], ["metrics.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_id"),
    )
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_service_id", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_metrics_recorded_at", table_name="metrics")
    op.drop_index("ix_metrics_metric_name", table_name="metrics")
    op.drop_index("ix_metrics_service_id", table_name="metrics")
    op.drop_table("metrics")
    op.drop_index("ix_services_name", table_name="services")
    op.drop_table("services")
