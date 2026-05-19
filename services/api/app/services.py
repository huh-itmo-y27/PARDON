from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

import joblib
import pandas as pd
from sqlalchemy import case, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anomaly_detection.config import CHANGEPOINT_COL, LABEL_COL, TIMESTAMP_COL
from anomaly_detection.config import MLFLOW_TRACKING_URI
from anomaly_detection.modeling.models import load_model
from anomaly_detection.monitoring.drift import compute_concept_proxy, compute_data_drift

from .core.settings import settings
from .db import SessionLocal
from .models import (
    DriftNotification,
    DriftSeverity,
    Prediction,
    RetrainJob,
    RetrainStatus,
)
from .schemas import PredictRequest, PredictionItem, RetrainRequest

_retrain_guard = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_model_metadata(model_name: str) -> tuple[Any, dict[str, Any], list[str], Any]:
    model_dir = settings.models_dir / model_name
    metadata = json.loads(
        (model_dir / "train_metadata.json").read_text("utf-8")
    )
    feature_columns = metadata.get("feature_columns", [])
    scaler = joblib.load(settings.data_processed_dir / "scaler.pkl")
    model = load_model(model_name, model_dir)
    return model, metadata, feature_columns, scaler


def run_inference(
    payload: PredictRequest, db: Session
) -> tuple[list[PredictionItem], dict[str, Any]]:
    model, metadata, feature_columns, scaler = _load_model_metadata(payload.model_name)
    if not feature_columns:
        raise ValueError("Feature columns are not available in model metadata.")
    rows = []
    for rec in payload.records:
        missing = [col for col in feature_columns if col not in rec.features]
        if missing:
            raise ValueError(f"Missing feature values: {missing}")
        rows.append({col: float(rec.features[col]) for col in feature_columns})
    frame = pd.DataFrame(rows, columns=feature_columns)
    scaled = scaler.transform(frame)
    scores = model.score_points(scaled)
    threshold = float(metadata["threshold"])
    flags = (scores > threshold).astype(int)

    result = []
    for idx, rec in enumerate(payload.records):
        row = PredictionItem(
            source_id=rec.source_id,
            score=float(scores[idx]),
            threshold=threshold,
            anomaly_flag=int(flags[idx]),
        )
        result.append(row)
        db.add(
            Prediction(
                created_at=_utc_now(),
                request_id=payload.request_id,
                source_id=rec.source_id,
                model_name=payload.model_name,
                score=row.score,
                threshold=row.threshold,
                anomaly_flag=row.anomaly_flag,
            )
        )
    db.commit()

    drift_reference = metadata.get("drift_reference", {})
    data_drift = compute_data_drift(frame, drift_reference) if drift_reference else {}
    baseline = {
        "anomaly_rate": float(
            drift_reference.get("label_rates", {}).get("anomaly", 0.0)
        )
    }
    concept = compute_concept_proxy(
        current_metrics={"anomaly_rate": float(flags.mean())},
        baseline_metrics=baseline,
    )
    drift_payload = {"data_drift": data_drift, "concept_drift_proxy": concept}
    _store_drift_notification(db, drift_payload)
    return result, drift_payload


def _store_drift_notification(db: Session, drift: dict[str, Any]) -> None:
    score = float(drift.get("data_drift", {}).get("data_drift_score", 0.0))
    concept_score = float(
        drift.get("concept_drift_proxy", {}).get(
            "concept_drift_proxy_score", 0.0
        )
    )
    severity = DriftSeverity.INFO
    if score >= 0.2 or concept_score >= 0.1:
        severity = DriftSeverity.HIGH
    elif score >= 0.1 or concept_score >= 0.07:
        severity = DriftSeverity.MEDIUM
    if severity is DriftSeverity.INFO:
        return
    dedup_key = f"{severity.value}:{round(score,3)}:{round(concept_score,3)}"
    db.add(
        DriftNotification(
            created_at=_utc_now(),
            severity=severity,
            title="Drift threshold exceeded",
            message=(
                f"Data drift score={score:.3f}, "
                f"concept drift proxy={concept_score:.3f}"
            ),
            dedup_key=dedup_key,
            read=False,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def list_recent_predictions(
    db: Session, limit: int, offset: int, model_name: str | None
) -> list[Prediction]:
    stmt = (
        select(Prediction)
        .order_by(desc(Prediction.id))
        .limit(limit)
        .offset(offset)
    )
    if model_name:
        stmt = stmt.where(Prediction.model_name == model_name)
    return list(db.scalars(stmt))


def list_available_models() -> list[str]:
    if not settings.models_dir.exists():
        return []
    result: list[str] = []
    for item in sorted(settings.models_dir.iterdir()):
        if not item.is_dir():
            continue
        if (item / "train_metadata.json").exists():
            result.append(item.name)
    return result


def _split_path(split: str) -> str:
    if split not in {"train", "val", "test"}:
        raise ValueError("split must be one of: train, val, test")
    return str(settings.data_processed_dir / f"{split}.csv")


def list_dataset_sources(split: str, query: str | None = None) -> list[dict[str, Any]]:
    frame = pd.read_csv(_split_path(split))
    if "source_id" not in frame.columns:
        return []
    counts = frame["source_id"].astype(str).value_counts().to_dict()
    items = []
    for source_id, rows_count in counts.items():
        if query and query.lower() not in source_id.lower():
            continue
        items.append(
            {"split": split, "source_id": source_id, "rows_count": int(rows_count)}
        )
    items.sort(key=lambda item: item["source_id"])
    return items


def get_dataset_records(
    split: str, source_id: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    frame = pd.read_csv(_split_path(split))
    if "source_id" not in frame.columns:
        return []
    filtered = frame[frame["source_id"].astype(str) == source_id]
    if filtered.empty:
        return []
    exclude = {TIMESTAMP_COL, "source_id", LABEL_COL, CHANGEPOINT_COL}
    feature_cols = [col for col in filtered.columns if col not in exclude]
    page = filtered.iloc[offset : offset + limit]
    records = []
    for idx, row in page.iterrows():
        features = {col: float(row[col]) for col in feature_cols}
        records.append({"source_id": f"{source_id}:{idx}", "features": features})
    return records


def list_prediction_runs(
    db: Session, limit: int, offset: int, model_name: str | None
) -> list[dict[str, Any]]:
    anomaly_case = case((Prediction.anomaly_flag == 1, 1), else_=0)
    stmt = (
        select(
            Prediction.request_id.label("request_id"),
            Prediction.model_name.label("model_name"),
            func.max(Prediction.created_at).label("created_at"),
            func.count(Prediction.id).label("records_count"),
            func.sum(anomaly_case).label("anomalies_count"),
            func.avg(Prediction.score).label("avg_score"),
            func.max(Prediction.score).label("max_score"),
        )
        .group_by(Prediction.request_id, Prediction.model_name)
        .order_by(desc(func.max(Prediction.created_at)))
        .limit(limit)
        .offset(offset)
    )
    if model_name:
        stmt = stmt.where(Prediction.model_name == model_name)
    rows = db.execute(stmt).all()
    payload: list[dict[str, Any]] = []
    for row in rows:
        records_count = int(row.records_count or 0)
        anomalies_count = int(row.anomalies_count or 0)
        payload.append(
            {
                "request_id": str(row.request_id),
                "model_name": str(row.model_name),
                "created_at": row.created_at,
                "records_count": records_count,
                "anomalies_count": anomalies_count,
                "anomaly_rate": (anomalies_count / records_count) if records_count else 0.0,
                "avg_score": float(row.avg_score or 0.0),
                "max_score": float(row.max_score or 0.0),
            }
        )
    return payload


def get_prediction_run_detail(db: Session, request_id: str) -> dict[str, Any] | None:
    rows_stmt = (
        select(Prediction)
        .where(Prediction.request_id == request_id)
        .order_by(desc(Prediction.id))
    )
    rows = list(db.scalars(rows_stmt))
    if not rows:
        return None
    records_count = len(rows)
    anomalies_count = sum(1 for row in rows if int(row.anomaly_flag) == 1)
    avg_score = sum(float(row.score) for row in rows) / records_count
    max_score = max(float(row.score) for row in rows)
    latest = rows[0]
    return {
        "request_id": request_id,
        "model_name": latest.model_name,
        "created_at": latest.created_at,
        "records_count": records_count,
        "anomalies_count": anomalies_count,
        "anomaly_rate": anomalies_count / records_count,
        "avg_score": avg_score,
        "max_score": max_score,
        "rows": rows,
    }


def get_notifications(
    db: Session, limit: int, offset: int, only_unread: bool
) -> list[DriftNotification]:
    stmt = (
        select(DriftNotification)
        .order_by(desc(DriftNotification.id))
        .limit(limit)
        .offset(offset)
    )
    if only_unread:
        stmt = stmt.where(DriftNotification.read.is_(False))
    return list(db.scalars(stmt))


def mark_notification_as_read(db: Session, notification_id: int) -> None:
    item = db.get(DriftNotification, notification_id)
    if item is None:
        return
    item.read = True
    db.commit()


def create_retrain_job(db: Session, request: RetrainRequest) -> str:
    active_job = get_active_retrain_job(db)
    if active_job is not None:
        return active_job.id

    if not _retrain_guard.acquire(blocking=False):
        active_job = get_active_retrain_job(db)
        if active_job is not None:
            return active_job.id
        raise RuntimeError("A retrain job is already running.")
    job_id = str(uuid4())
    now = _utc_now()
    db.add(
        RetrainJob(
            id=job_id,
            created_at=now,
            updated_at=now,
            model_name=request.model_name,
            dataset_scenario=request.dataset_scenario,
            status=RetrainStatus.QUEUED.value,
            details={"message": "Queued for execution"},
        )
    )
    db.commit()
    thread = threading.Thread(
        target=_run_retrain_subprocess,
        args=(job_id, request),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_retrain_subprocess(job_id: str, request: RetrainRequest) -> None:
    try:
        _update_retrain_job(
            job_id,
            RetrainStatus.RUNNING,
            {"message": "Training started"},
        )
        cmd = [
            "python",
            "-m",
            "anomaly_detection.modeling.train",
            "--model-name",
            request.model_name,
            "--dataset-scenario",
            request.dataset_scenario,
        ]
        cmd.append(
            "--register-model" if request.register_model else "--no-register-model"
        )
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=settings.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdout_buffer: deque[str] = deque(maxlen=1500)
        stderr_buffer: deque[str] = deque(maxlen=1500)
        stream_lock = threading.Lock()

        def _read_stream(stream: Any, sink: deque[str]) -> None:
            for line in iter(stream.readline, ""):
                with stream_lock:
                    sink.append(line)
            stream.close()

        assert proc.stdout is not None
        assert proc.stderr is not None
        stdout_thread = threading.Thread(
            target=_read_stream, args=(proc.stdout, stdout_buffer), daemon=True
        )
        stderr_thread = threading.Thread(
            target=_read_stream, args=(proc.stderr, stderr_buffer), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()

        while proc.poll() is None:
            with stream_lock:
                _update_retrain_job(
                    job_id,
                    RetrainStatus.RUNNING,
                    {
                        "message": "Training in progress",
                        "stdout": "".join(stdout_buffer)[-4000:],
                        "stderr": "".join(stderr_buffer)[-4000:],
                    },
                )
            time.sleep(1.2)

        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)

        with stream_lock:
            stdout_tail = "".join(stdout_buffer)[-4000:]
            stderr_tail = "".join(stderr_buffer)[-4000:]

        if proc.returncode != 0:
            _update_retrain_job(
                job_id,
                RetrainStatus.FAILED,
                {
                    "message": "Training failed",
                    "stdout": stdout_tail,
                    "stderr": stderr_tail,
                },
            )
            return
        _update_retrain_job(
            job_id,
            RetrainStatus.SUCCEEDED,
            {
                "message": "Training completed successfully",
                "stdout": stdout_tail,
                "stderr": stderr_tail,
            },
        )
    finally:
        _retrain_guard.release()


def _update_retrain_job(
    job_id: str, status: RetrainStatus, details: dict[str, Any]
) -> None:
    with SessionLocal() as db:
        row = db.get(RetrainJob, job_id)
        if row is None:
            return
        row.updated_at = _utc_now()
        row.status = status.value
        row.details = details
        db.commit()


def get_retrain_job(db: Session, job_id: str) -> RetrainJob | None:
    return db.get(RetrainJob, job_id)


def get_active_retrain_job(db: Session) -> RetrainJob | None:
    stmt = (
        select(RetrainJob)
        .where(
            RetrainJob.status.in_(
                [RetrainStatus.QUEUED.value, RetrainStatus.RUNNING.value]
            )
        )
        .order_by(desc(RetrainJob.updated_at))
        .limit(1)
    )
    return db.scalar(stmt)


def list_experiments(
    limit: int, model_name: str | None = None, offset: int = 0
) -> list[dict[str, Any]]:
    try:
        import mlflow
    except ModuleNotFoundError:
        return []
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()
    experiments = client.search_experiments()
    runs_payload: list[dict[str, Any]] = []
    for exp in experiments:
        runs = client.search_runs([exp.experiment_id], max_results=2000)
        for run in runs:
            run_model = str(run.data.params.get("model_name", ""))
            if model_name and run_model != model_name:
                continue
            start_ms = int(run.info.start_time or 0)
            started_at = (
                datetime.fromtimestamp(
                    start_ms / 1000, tz=timezone.utc
                ).isoformat()
                if start_ms
                else None
            )
            runs_payload.append(
                {
                    "_start_ms": start_ms,
                    "run_id": run.info.run_id,
                    "experiment": exp.name,
                    "model_name": run_model,
                    "status": run.info.status,
                    "started_at": started_at,
                    "metrics": {
                        k: float(v) for k, v in run.data.metrics.items()
                    },
                    "params": {k: str(v) for k, v in run.data.params.items()},
                }
            )
    runs_payload.sort(key=lambda item: int(item.get("_start_ms", 0)), reverse=True)
    page = runs_payload[offset : offset + limit]
    for row in page:
        row.pop("_start_ms", None)
    return page


def get_experiment_by_run_id(run_id: str) -> dict[str, Any] | None:
    try:
        import mlflow
    except ModuleNotFoundError:
        return None
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()
    try:
        run = client.get_run(run_id)
    except Exception:
        return None
    exp = client.get_experiment(run.info.experiment_id)
    started_at = (
        datetime.fromtimestamp(run.info.start_time / 1000, tz=timezone.utc).isoformat()
        if run.info.start_time
        else None
    )
    return {
        "run_id": run.info.run_id,
        "experiment": exp.name if exp else run.info.experiment_id,
        "model_name": str(run.data.params.get("model_name", "")),
        "status": run.info.status,
        "started_at": started_at,
        "metrics": {k: float(v) for k, v in run.data.metrics.items()},
        "params": {k: str(v) for k, v in run.data.params.items()},
        "tags": {k: str(v) for k, v in run.data.tags.items()},
    }

