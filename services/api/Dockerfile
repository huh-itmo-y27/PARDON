# syntax=docker/dockerfile:1.7

FROM python:3.10-slim

WORKDIR /app

ENV UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["/bin/sh", "-c", "uv run alembic upgrade head && uv run uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000"]

