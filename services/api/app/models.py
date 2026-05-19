from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .db import Base


class RetrainStatus(str, PyEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DriftSeverity(str, PyEnum):
    INFO = "info"
    MEDIUM = "medium"
    HIGH = "high"


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_flag: Mapped[int] = mapped_column(Integer, nullable=False)


class RetrainJob(Base):
    __tablename__ = "retrain_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RetrainStatus] = mapped_column(
        SAEnum(
            RetrainStatus,
            name="retrain_job_status",
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        index=True,
        nullable=False,
    )
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)


class DriftNotification(Base):
    __tablename__ = "drift_notifications"
    __table_args__ = (UniqueConstraint("dedup_key", name="uq_drift_notifications_dedup_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    severity: Mapped[DriftSeverity] = mapped_column(
        SAEnum(
            DriftSeverity,
            name="drift_notification_severity",
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

