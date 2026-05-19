FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock* README.md LICENSE ./
RUN uv sync --dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["/bin/sh", "-c", "uv run alembic upgrade head && uv run uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000"]

