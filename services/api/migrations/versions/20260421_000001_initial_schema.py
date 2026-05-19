"""initial schema

Revision ID: 20260421_000001
Revises:
Create Date: 2026-04-21 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drift_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dedup_key", name="uq_drift_notifications_dedup_key"
        ),
    )
    op.create_index(
        op.f("ix_drift_notifications_severity"),
        "drift_notifications",
        ["severity"],
        unique=False,
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("anomaly_flag", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_predictions_model_name"),
        "predictions",
        ["model_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predictions_request_id"),
        "predictions",
        ["request_id"],
        unique=False,
    )

    op.create_table(
        "retrain_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("dataset_scenario", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retrain_jobs_status"),
        "retrain_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_retrain_jobs_status"), table_name="retrain_jobs")
    op.drop_table("retrain_jobs")
    op.drop_index(op.f("ix_predictions_request_id"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_model_name"), table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(
        op.f("ix_drift_notifications_severity"),
        table_name="drift_notifications",
    )
    op.drop_table("drift_notifications")

