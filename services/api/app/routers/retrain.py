from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..core.settings import settings
from ..db import get_db
from ..schemas import RetrainJobResponse, RetrainRequest
from ..services import create_retrain_job, get_active_retrain_job, get_retrain_job

router = APIRouter(prefix="/api/v1", tags=["retrain"])


def _status_to_str(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _details_to_dict(details: object) -> dict:
    if isinstance(details, dict):
        return details
    if isinstance(details, str):
        try:
            parsed = json.loads(details)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {"raw": str(details)}


def _require_retrain_auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.retrain_auth_enabled:
        return
    if not settings.retrain_bearer_token:
        raise HTTPException(status_code=503, detail="Retrain auth is misconfigured")
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len(prefix) :].strip()
    if not secrets.compare_digest(token, settings.retrain_bearer_token):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@router.post("/retrain", response_model=RetrainJobResponse)
def retrain(
    payload: RetrainRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_retrain_auth),
) -> RetrainJobResponse:
    try:
        job_id = create_retrain_job(db, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = get_retrain_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Retrain job was not persisted")
    return RetrainJobResponse(
        job_id=row.id,
        status=_status_to_str(row.status),
        model_name=row.model_name,
        dataset_scenario=row.dataset_scenario,
        details=_details_to_dict(row.details),
    )


@router.get("/retrain/active", response_model=RetrainJobResponse | None)
def retrain_active(db: Session = Depends(get_db)) -> RetrainJobResponse | None:
    row = get_active_retrain_job(db)
    if row is None:
        return None
    return RetrainJobResponse(
        job_id=row.id,
        status=_status_to_str(row.status),
        model_name=row.model_name,
        dataset_scenario=row.dataset_scenario,
        details=_details_to_dict(row.details),
    )


@router.get("/retrain/{job_id}", response_model=RetrainJobResponse)
def retrain_status(
    job_id: str, db: Session = Depends(get_db)
) -> RetrainJobResponse:
    row = get_retrain_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return RetrainJobResponse(
        job_id=row.id,
        status=_status_to_str(row.status),
        model_name=row.model_name,
        dataset_scenario=row.dataset_scenario,
        details=_details_to_dict(row.details),
    )

