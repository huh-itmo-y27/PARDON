from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PredictRecord(BaseModel):
    source_id: str | None = None
    features: dict[str, float] = Field(default_factory=dict)


class PredictRequest(BaseModel):
    model_name: str = "isolation_forest"
    records: list[PredictRecord] = Field(min_length=1)
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class PredictionItem(BaseModel):
    source_id: str | None
    score: float
    threshold: float
    anomaly_flag: int


class PredictResponse(BaseModel):
    request_id: str
    model_name: str
    predictions: list[PredictionItem]
    drift: dict[str, Any]


class RecentPrediction(BaseModel):
    id: int
    created_at: datetime
    request_id: str
    source_id: str | None
    model_name: str
    score: float
    threshold: float
    anomaly_flag: int


class AvailableModel(BaseModel):
    model_name: str


class PredictionRunSummary(BaseModel):
    request_id: str
    model_name: str
    created_at: datetime
    records_count: int
    anomalies_count: int
    anomaly_rate: float
    avg_score: float
    max_score: float


class PredictionRunDetail(BaseModel):
    request_id: str
    model_name: str
    created_at: datetime
    records_count: int
    anomalies_count: int
    anomaly_rate: float
    avg_score: float
    max_score: float
    rows: list[RecentPrediction]


class DatasetSource(BaseModel):
    split: str
    source_id: str
    rows_count: int


class RetrainRequest(BaseModel):
    model_name: str = "isolation_forest"
    dataset_scenario: str = "all"
    register_model: bool = True


class RetrainJobResponse(BaseModel):
    job_id: str
    status: str
    model_name: str
    dataset_scenario: str
    details: dict[str, Any]


class DriftNotification(BaseModel):
    id: int
    created_at: datetime
    severity: str
    title: str
    message: str
    read: bool


class ExperimentItem(BaseModel):
    run_id: str
    experiment: str
    model_name: str
    status: str
    started_at: datetime | None
    metrics: dict[str, float]
    params: dict[str, str]


class ExperimentDetail(ExperimentItem):
    tags: dict[str, str] = Field(default_factory=dict)

