from __future__ import annotations

import os
from pathlib import Path


class Settings:
    api_title: str = os.getenv("API_TITLE", "PARDON Anomaly API")
    api_version: str = os.getenv("API_VERSION", "0.1.0")
    api_prefix: str = "/api/v1"
    project_root: Path = Path(__file__).resolve().parents[4]
    data_processed_dir: Path = project_root / "data" / "processed"
    models_dir: Path = project_root / "models" / "base_models"
    database_url: str = os.getenv(
        "PARDON_DATABASE_URL",
        "postgresql+psycopg://pardon:pardon@postgres:5432/pardon",
    )
    default_model_name: str = os.getenv("API_DEFAULT_MODEL", "isolation_forest")
    retrain_lock_timeout_sec: int = int(os.getenv("RETRAIN_LOCK_TIMEOUT_SEC", "5"))
    retrain_auth_enabled: bool = os.getenv(
        "PARDON_RETRAIN_AUTH_ENABLED", "false"
    ).lower() in {"1", "true", "yes", "on"}
    retrain_bearer_token: str = os.getenv("PARDON_RETRAIN_BEARER_TOKEN", "")
    cors_allowed_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("PARDON_CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]


settings = Settings()

