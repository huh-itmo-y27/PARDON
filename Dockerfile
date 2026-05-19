FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock* README.md LICENSE ./
RUN uv sync --dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENV MONITORING_EXPORTER_PORT=8010

EXPOSE 8010

CMD ["python", "-m", "anomaly_detection.monitoring.mlflow_exporter"]
