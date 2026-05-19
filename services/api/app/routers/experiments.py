from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas import ExperimentDetail, ExperimentItem
from ..services import get_experiment_by_run_id, list_experiments

router = APIRouter(prefix="/api/v1", tags=["experiments"])


@router.get("/experiments", response_model=list[ExperimentItem])
def experiments(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    model_name: str | None = Query(default=None),
) -> list[ExperimentItem]:
    return [
        ExperimentItem.model_validate(item)
        for item in list_experiments(limit, model_name, offset)
    ]


@router.get("/experiments/{run_id}", response_model=ExperimentDetail)
def experiment_detail(run_id: str) -> ExperimentDetail:
    row = get_experiment_by_run_id(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Experiment run not found")
    return ExperimentDetail.model_validate(row)

