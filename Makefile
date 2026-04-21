#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = itmo-aiii27-mlops
PYTHON_VERSION = 3.10
PYTHON_INTERPRETER = uv run python
UV_HTTP_TIMEOUT ?= 120
UV_HTTP_RETRIES ?= 3
MODEL ?= isolation_forest
DATA_SCENARIO ?= all
MLFLOW_PORT ?= 5000
MONITORING_COMPOSE_FILE ?= docker-compose.monitoring.yml

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	UV_HTTP_TIMEOUT=$(UV_HTTP_TIMEOUT) UV_HTTP_RETRIES=$(UV_HTTP_RETRIES) uv sync --dev
	



## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	uv run ruff format --check
	uv run ruff check

## Format source code with ruff
.PHONY: format
format:
	uv run ruff check --fix
	uv run ruff format



## Run tests
.PHONY: test
test:
	uv run pytest tests
## Configure DVC remote credentials (local config only)
.PHONY: setup_dvc
setup_dvc:
	@set -a; \
	. ./.env; \
	set +a; \
	uv run dvc remote modify --local minio_storage access_key_id "$$MINIO_ACCESS_KEY"; \
	uv run dvc remote modify --local minio_storage secret_access_key "$$MINIO_SECRET_KEY"; \
	echo "DVC configured"

## Download versioned data from DVC remote
.PHONY: data_pull
data_pull:
	dvc pull
	mkdir -p data/raw
	@if [ -d data/valve1 ]; then mv data/valve1 data/raw/; fi

## Upload versioned data to DVC remote
.PHONY: data_push
data_push:
	dvc push
	@if [ -d data/raw/valve1 ]; then mv data/raw/valve1 data/valve1; fi

## Run MLflow UI for current local mlruns
.PHONY: mlflow_ui
mlflow_ui:
	uv run mlflow ui --backend-store-uri "file:./mlruns" --port $(MLFLOW_PORT)

## Run MLflow to Prometheus exporter
.PHONY: mlflow_exporter
mlflow_exporter: requirements
	$(PYTHON_INTERPRETER) -m anomaly_detection.monitoring.mlflow_exporter

## Start local monitoring stack (Prometheus + Grafana + Pushgateway)
.PHONY: monitoring_up
monitoring_up:
	docker compose -f $(MONITORING_COMPOSE_FILE) up -d

## Stop local monitoring stack
.PHONY: monitoring_down
monitoring_down:
	docker compose -f $(MONITORING_COMPOSE_FILE) down

## Tail monitoring stack logs
.PHONY: monitoring_logs
monitoring_logs:
	docker compose -f $(MONITORING_COMPOSE_FILE) logs -f

## Show monitoring stack service status
.PHONY: monitoring_status
monitoring_status:
	docker compose -f $(MONITORING_COMPOSE_FILE) ps




## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	uv venv --python $(PYTHON_VERSION)
	@echo ">>> New uv virtual environment created. Activate with:"
	@echo ">>> Windows: .\\\\.venv\\\\Scripts\\\\activate"
	@echo ">>> Unix/macOS: source ./.venv/bin/activate"
	@echo ">>> Then install deps with: make requirements"
	



#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Make dataset
.PHONY: data
data: requirements
	$(PYTHON_INTERPRETER) anomaly_detection/dataset.py

## Prepare canonical split files from raw data
.PHONY: dataset
dataset: requirements
	$(PYTHON_INTERPRETER) -m anomaly_detection.dataset --scenario $(DATA_SCENARIO)

## Generate scaled features for train/val/test
.PHONY: features
features: requirements dataset
	$(PYTHON_INTERPRETER) -m anomaly_detection.features

## Train selected model pipeline
.PHONY: train
train: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.train --model-name $(MODEL) --dataset-scenario $(DATA_SCENARIO)

## Run inference with selected model pipeline
.PHONY: predict
predict: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.predict --model-name $(MODEL) --dataset-scenario $(DATA_SCENARIO)


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
