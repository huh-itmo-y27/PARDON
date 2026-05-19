from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import (
    AvailableModel,
    DatasetSource,
    PredictRequest,
    PredictRecord,
    PredictResponse,
    PredictionRunDetail,
    PredictionRunSummary,
    RecentPrediction,
)
from ..services import (
    get_dataset_records,
    get_prediction_run_detail,
    list_dataset_sources,
    list_available_models,
    list_prediction_runs,
    list_recent_predictions,
    run_inference,
)

router = APIRouter(prefix="/api/v1", tags=["inference"])


@router.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    try:
        predictions, drift = run_inference(payload, db)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PredictResponse(
        request_id=payload.request_id,
        model_name=payload.model_name,
        predictions=predictions,
        drift=drift,
    )


@router.get("/models/available", response_model=list[AvailableModel])
def available_models() -> list[AvailableModel]:
    return [AvailableModel(model_name=name) for name in list_available_models()]


@router.get("/datasets/sources", response_model=list[DatasetSource])
def dataset_sources(
    split: str = Query(default="val"),
    q: str | None = Query(default=None),
) -> list[DatasetSource]:
    try:
        rows = list_dataset_sources(split=split, query=q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [DatasetSource.model_validate(row) for row in rows]


@router.get("/datasets/records", response_model=list[PredictRecord])
def dataset_records(
    split: str = Query(default="val"),
    source_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> list[PredictRecord]:
    try:
        rows = get_dataset_records(
            split=split, source_id=source_id, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [PredictRecord.model_validate(row) for row in rows]


@router.get("/predictions/runs", response_model=list[PredictionRunSummary])
def prediction_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    model_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[PredictionRunSummary]:
    rows = list_prediction_runs(db, limit=limit, offset=offset, model_name=model_name)
    return [PredictionRunSummary.model_validate(row) for row in rows]


@router.get("/predictions/runs/{request_id}", response_model=PredictionRunDetail)
def prediction_run_detail(
    request_id: str, db: Session = Depends(get_db)
) -> PredictionRunDetail:
    row = get_prediction_run_detail(db, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Prediction run not found")
    return PredictionRunDetail(
        request_id=str(row["request_id"]),
        model_name=str(row["model_name"]),
        created_at=row["created_at"],
        records_count=int(row["records_count"]),
        anomalies_count=int(row["anomalies_count"]),
        anomaly_rate=float(row["anomaly_rate"]),
        avg_score=float(row["avg_score"]),
        max_score=float(row["max_score"]),
        rows=[
            RecentPrediction(
                id=item.id,
                created_at=item.created_at,
                request_id=item.request_id,
                source_id=item.source_id,
                model_name=item.model_name,
                score=item.score,
                threshold=item.threshold,
                anomaly_flag=item.anomaly_flag,
            )
            for item in row["rows"]
        ],
    )


@router.get("/predictions/recent", response_model=list[RecentPrediction])
def recent_predictions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    model_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RecentPrediction]:
    rows = list_recent_predictions(db, limit=limit, offset=offset, model_name=model_name)
    return [
        RecentPrediction(
            id=row.id,
            created_at=row.created_at,
            request_id=row.request_id,
            source_id=row.source_id,
            model_name=row.model_name,
            score=row.score,
            threshold=row.threshold,
            anomaly_flag=row.anomaly_flag,
        )
        for row in rows
    ]

