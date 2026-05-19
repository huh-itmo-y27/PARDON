from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from services.api.app import db as db_module
from services.api.app import main as api_main
from services.api.app.core.settings import settings
from services.api.app.models import DriftNotification
from services.api.app.routers import predict as predict_router
from services.api.app.routers import retrain as retrain_router
from services.api.app.schemas import PredictionItem
from services.api.app.services import _store_drift_notification


def test_predict_flow_returns_predictions_and_drift(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "init_db", lambda: None)

    def override_get_db():
        yield object()

    api_main.app.dependency_overrides[db_module.get_db] = override_get_db

    def fake_run_inference(payload, _db):  # type: ignore[no-untyped-def]
        return (
            [
                PredictionItem(
                    source_id=payload.records[0].source_id,
                    score=0.42,
                    threshold=0.3,
                    anomaly_flag=1,
                )
            ],
            {"data_drift": {"data_drift_score": 0.2}},
        )

    monkeypatch.setattr(predict_router, "run_inference", fake_run_inference)

    with TestClient(api_main.app) as client:
        response = client.post(
            "/api/v1/predict",
            json={
                "model_name": "isolation_forest",
                "records": [{"source_id": "series-1", "features": {"x": 1.0}}],
            },
        )
    api_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["model_name"] == "isolation_forest"
    assert len(body["predictions"]) == 1
    assert body["predictions"][0]["anomaly_flag"] == 1
    assert "data_drift" in body["drift"]


def test_retrain_lifecycle_enforces_auth_and_returns_status(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(settings, "retrain_auth_enabled", True)
    monkeypatch.setattr(settings, "retrain_bearer_token", "secret-token")

    def override_get_db():
        yield object()

    api_main.app.dependency_overrides[db_module.get_db] = override_get_db

    job_state = {
        "id": "job-1",
        "status": "queued",
        "model_name": "isolation_forest",
        "dataset_scenario": "all",
        "details": {"message": "Queued"},
    }

    def fake_row() -> SimpleNamespace:
        return SimpleNamespace(**job_state)

    monkeypatch.setattr(retrain_router, "create_retrain_job", lambda _db, _req: "job-1")
    monkeypatch.setattr(
        retrain_router,
        "get_retrain_job",
        lambda _db, job_id: fake_row() if job_id == "job-1" else None,
    )
    monkeypatch.setattr(retrain_router, "get_active_retrain_job", lambda _db: fake_row())

    payload = {
        "model_name": "isolation_forest",
        "dataset_scenario": "all",
        "register_model": True,
    }

    with TestClient(api_main.app) as client:
        unauthorized = client.post("/api/v1/retrain", json=payload)
        assert unauthorized.status_code == 401

        wrong = client.post(
            "/api/v1/retrain",
            json=payload,
            headers={"Authorization": "Bearer wrong"},
        )
        assert wrong.status_code == 401

        ok = client.post(
            "/api/v1/retrain",
            json=payload,
            headers={"Authorization": "Bearer secret-token"},
        )
        assert ok.status_code == 200
        assert ok.json()["job_id"] == "job-1"

        active = client.get("/api/v1/retrain/active")
        assert active.status_code == 200
        assert active.json()["job_id"] == "job-1"

        job_state["status"] = "succeeded"
        job_state["details"] = {"message": "Done"}
        status = client.get("/api/v1/retrain/job-1")
        assert status.status_code == 200
        assert status.json()["status"] == "succeeded"

    api_main.app.dependency_overrides.clear()


def test_notification_dedup_enforces_unique_notification() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    DriftNotification.__table__.create(bind=engine)

    drift_payload = {
        "data_drift": {"data_drift_score": 0.2},
        "concept_drift_proxy": {"concept_drift_proxy_score": 0.0},
    }

    with SessionLocal() as db:
        _store_drift_notification(db, drift_payload)
        _store_drift_notification(db, drift_payload)
        rows = list(db.scalars(select(DriftNotification)))

    assert len(rows) == 1
