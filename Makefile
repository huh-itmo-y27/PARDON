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
APP_COMPOSE_FILE ?= docker-compose.app.yml
K8S_NAMESPACE ?= pardon
MINIKUBE_PROFILE ?= minikube
LOCAL_DB_URL ?= postgresql+psycopg://pardon:pardon@localhost:5433/pardon

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

## Download versioned data and models from DVC remote
.PHONY: data_pull
data_pull:
	dvc pull data/valve1.dvc models/models.dvc

## Upload versioned data to DVC remote
# TODO: delete move
.PHONY: data_push
data_push:
	dvc push

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
	docker compose -f $(MONITORING_COMPOSE_FILE) --profile monitoring up -d

## Stop local monitoring stack
.PHONY: monitoring_down
monitoring_down:
	docker compose -f $(MONITORING_COMPOSE_FILE) down

## Tail monitoring stack logs
.PHONY: monitoring_logs
monitoring_logs:
	docker compose -f $(MONITORING_COMPOSE_FILE) --profile monitoring logs -f

## Show monitoring stack service status
.PHONY: monitoring_status
monitoring_status:
	docker compose -f $(MONITORING_COMPOSE_FILE) --profile monitoring ps

## Start app stack (FastAPI + Next.js)
.PHONY: app_up
app_up:
	docker compose -f $(APP_COMPOSE_FILE) --profile app up -d --build

## Stop app stack
.PHONY: app_down
app_down:
	docker compose -f $(APP_COMPOSE_FILE) down

## Tail app stack logs
.PHONY: app_logs
app_logs:
	docker compose -f $(APP_COMPOSE_FILE) --profile app logs -f

## Rebuild app stack images
.PHONY: app_rebuild
app_rebuild:
	docker compose -f $(APP_COMPOSE_FILE) build --no-cache

## Smoke test app stack endpoints
.PHONY: app_smoke
app_smoke:
	curl -fsS http://localhost:8000/healthz >/dev/null
	curl -fsS http://localhost:8000/openapi.json >/dev/null
	curl -fsS http://localhost:3001 >/dev/null

## Apply Alembic migrations to current database
.PHONY: db_migrate
db_migrate:
	PARDON_DATABASE_URL=$(LOCAL_DB_URL) uv run alembic upgrade head

## Create a new Alembic migration revision
.PHONY: db_revision
db_revision:
	PARDON_DATABASE_URL=$(LOCAL_DB_URL) uv run alembic revision --autogenerate -m "$(m)"

## Export FastAPI OpenAPI schema to file
.PHONY: openapi_export
openapi_export:
	uv run python -c "import json; from services.api.app.main import app; from pathlib import Path; p=Path('services/api/openapi.json'); p.write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')"

## Generate TypeScript client schema from OpenAPI
.PHONY: ui_codegen
ui_codegen:
	cd services/ui && npm install && npm run generate:client

## CI check: apply migrations against CI database
.PHONY: ci_db_migrate_check
ci_db_migrate_check:
	PARDON_DATABASE_URL=$${PARDON_DATABASE_URL:-postgresql+psycopg://pardon:pardon@localhost:5432/pardon} uv run alembic upgrade head

## CI check: OpenAPI and UI client are up to date
.PHONY: ci_openapi_codegen_check
ci_openapi_codegen_check:
	make openapi_export
	make ui_codegen
	git diff --exit-code -- services/api/openapi.json services/ui/lib/generated/api-schema.ts




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
# DOCKER                                                                        #
#################################################################################

## Build Docker images from docker-compose.yml
.PHONY: docker_build
docker_build:
	docker compose build

## Open interactive bash shell in app container
.PHONY: docker_run
docker_run:
	docker compose run --rm app bash

## Train selected model inside Docker (MODEL=isolation_forest|conv_ae|lstm_ae)
.PHONY: train_docker
train_docker:
	docker compose run --rm app make train

## Run inference inside Docker (MODEL=isolation_forest|conv_ae|lstm_ae)
.PHONY: predict_docker
predict_docker:
	docker compose run --rm app make predict

## Run tests inside Docker
.PHONY: test_docker
test_docker:
	docker compose run --rm app make test

## Run lint checks inside Docker
.PHONY: lint_docker
lint_docker:
	docker compose run --rm app make lint

## Start minikube with ingress enabled
.PHONY: k8s_minikube_up
k8s_minikube_up:
	minikube start -p $(MINIKUBE_PROFILE)
	minikube -p $(MINIKUBE_PROFILE) addons enable ingress

## Deploy Kubernetes manifests to minikube
.PHONY: k8s_deploy
k8s_deploy:
	kubectl apply -f deploy/k8s/minikube/namespace.yaml
	kubectl apply -f deploy/k8s/minikube/configmap.yaml
	kubectl apply -f deploy/k8s/minikube/postgres.yaml
	kubectl apply -f deploy/k8s/minikube/api-deployment.yaml
	kubectl apply -f deploy/k8s/minikube/ui-deployment.yaml
	kubectl apply -f deploy/k8s/minikube/ingress.yaml

## Show Kubernetes resource status
.PHONY: k8s_status
k8s_status:
	kubectl get all -n $(K8S_NAMESPACE)
	kubectl get ingress -n $(K8S_NAMESPACE)

## Tail Kubernetes logs for API deployment
.PHONY: k8s_logs
k8s_logs:
	kubectl logs -n $(K8S_NAMESPACE) deploy/pardon-api -f

## Smoke test Kubernetes service via port-forward
.PHONY: k8s_smoke
k8s_smoke:
	kubectl port-forward -n $(K8S_NAMESPACE) svc/pardon-api 18000:8000 >/tmp/pardon-api-pf.log 2>&1 & \
	pfpid=$$!; \
	sleep 3; \
	curl -fsS http://localhost:18000/healthz >/dev/null; \
	kill $$pfpid


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
