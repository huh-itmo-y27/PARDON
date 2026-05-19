"""use jsonb and enums

Revision ID: 20260421_000002
Revises: 20260421_000001
Create Date: 2026-04-21 00:00:02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260421_000002"
down_revision = "20260421_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    retrain_status = postgresql.ENUM(
        "queued",
        "running",
        "succeeded",
        "failed",
        name="retrain_job_status",
    )
    drift_severity = postgresql.ENUM(
        "info",
        "medium",
        "high",
        name="drift_notification_severity",
    )
    retrain_status.create(op.get_bind(), checkfirst=True)
    drift_severity.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        "retrain_jobs",
        "status",
        existing_type=sa.String(length=32),
        type_=retrain_status,
        postgresql_using="status::retrain_job_status",
    )
    op.alter_column(
        "drift_notifications",
        "severity",
        existing_type=sa.String(length=16),
        type_=drift_severity,
        postgresql_using="severity::drift_notification_severity",
    )
    op.alter_column(
        "retrain_jobs",
        "details",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="details::jsonb",
    )


def downgrade() -> None:
    op.alter_column(
        "retrain_jobs",
        "details",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        postgresql_using="details::text",
    )
    op.alter_column(
        "drift_notifications",
        "severity",
        existing_type=postgresql.ENUM(
            "info",
            "medium",
            "high",
            name="drift_notification_severity",
        ),
        type_=sa.String(length=16),
        postgresql_using="severity::text",
    )
    op.alter_column(
        "retrain_jobs",
        "status",
        existing_type=postgresql.ENUM(
            "queued",
            "running",
            "succeeded",
            "failed",
            name="retrain_job_status",
        ),
        type_=sa.String(length=32),
        postgresql_using="status::text",
    )
    op.execute("DROP TYPE IF EXISTS drift_notification_severity")
    op.execute("DROP TYPE IF EXISTS retrain_job_status")

