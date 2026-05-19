from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from starlette.responses import Response

from .core.settings import settings
from .db import init_db
from .routers.experiments import router as experiments_router
from .routers.health import router as health_router
from .routers.notifications import router as notifications_router
from .routers.predict import router as predict_router
from .routers.retrain import router as retrain_router

http_requests = Counter(
    "pardon_api_http_requests_total",
    "HTTP requests handled by PARDON API",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Inference, retraining, experiments, and drift notifications API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(predict_router)
app.include_router(retrain_router)
app.include_router(experiments_router)
app.include_router(notifications_router)


@app.middleware("http")
async def metrics_middleware(request, call_next):  # type: ignore[no-untyped-def]
    logger.info("request {} {}", request.method, request.url.path)
    response = await call_next(request)
    http_requests.labels(request.method, request.url.path).inc()
    return response


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

