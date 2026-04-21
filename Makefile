#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = itmo-aiii27-mlops
PYTHON_VERSION = 3.10
PYTHON_INTERPRETER = uv run python
UV_HTTP_TIMEOUT ?= 120
UV_HTTP_RETRIES ?= 3
MODEL ?= isolation_forest
MLFLOW_PORT ?= 5000
AIRFLOW_HOME ?= .airflow
AIRFLOW_DB_URI ?= sqlite:////$(abspath $(AIRFLOW_HOME))/airflow.db
AIRFLOW_DAG_ID ?= anomaly_detection_orchestration
AIRFLOW_API_PORT ?= 8080
AIRFLOW_LOG_SERVER_PORT ?= 8793
AIRFLOW_DAGS_FOLDER ?= $(abspath dags)
# For Postgres/MySQL, Airflow applies these. For SQLite it ignores them—use AIRFLOW_SQL_ENGINE_ARGS.
AIRFLOW_SQL_POOL_SIZE ?= 20
AIRFLOW_SQL_MAX_OVERFLOW ?= 30
# SQLite: Airflow does not apply SQL_ALCHEMY_POOL_* to the engine (see airflow settings.prepare_engine_args);
# pass pool_size via sql_alchemy_engine_args or the UI/API exhausts the default QueuePool (5+10).
# Do not set max_overflow here: db migrations call create_engine(..., pool_class=SingletonThreadPool), which
# rejects max_overflow and breaks `airflow standalone` / `airflow db migrate`.
AIRFLOW_SQL_ENGINE_ARGS ?= {"pool_size":32}
AIRFLOW_ENV = AIRFLOW_HOME=$(AIRFLOW_HOME) AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=$(AIRFLOW_DB_URI) AIRFLOW__DATABASE__SQL_ALCHEMY_POOL_SIZE=$(AIRFLOW_SQL_POOL_SIZE) AIRFLOW__DATABASE__SQL_ALCHEMY_MAX_OVERFLOW=$(AIRFLOW_SQL_MAX_OVERFLOW) AIRFLOW__DATABASE__SQL_ALCHEMY_ENGINE_ARGS='$(AIRFLOW_SQL_ENGINE_ARGS)' AIRFLOW__CORE__DAGS_FOLDER=$(AIRFLOW_DAGS_FOLDER) AIRFLOW__CORE__LOAD_EXAMPLES=False PYTHONPATH=$(abspath .)

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	UV_HTTP_TIMEOUT=$(UV_HTTP_TIMEOUT) UV_HTTP_RETRIES=$(UV_HTTP_RETRIES) uv sync --dev

## Install Python dependencies with Airflow group
.PHONY: airflow_requirements
airflow_requirements:
	UV_HTTP_TIMEOUT=$(UV_HTTP_TIMEOUT) UV_HTTP_RETRIES=$(UV_HTTP_RETRIES) uv sync --dev --group airflow




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
	$(PYTHON_INTERPRETER) -m anomaly_detection.dataset

## Generate scaled features for train/val/test
.PHONY: features
features: requirements dataset
	$(PYTHON_INTERPRETER) -m anomaly_detection.features

## Train selected model pipeline
.PHONY: train
train: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.train --model-name $(MODEL)

## Run inference with selected model pipeline
.PHONY: predict
predict: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.predict --model-name $(MODEL)

## Initialize local Airflow metadata database
.PHONY: airflow_init
airflow_init: airflow_requirements
	$(AIRFLOW_ENV) uv run airflow db migrate

## Create local Airflow admin user
.PHONY: airflow_create_admin
airflow_create_admin: airflow_requirements
	@echo "Airflow 3 removed 'airflow users create'."
	@echo "Use 'make airflow_standalone' once for local bootstrap and generated credentials."

## Start Airflow scheduler
.PHONY: airflow_scheduler
airflow_scheduler: airflow_requirements
	$(AIRFLOW_ENV) AIRFLOW__LOGGING__WORKER_LOG_SERVER_PORT=$(AIRFLOW_LOG_SERVER_PORT) uv run airflow scheduler

## Start scheduler with auto-selected free log server port
.PHONY: airflow_scheduler_auto
airflow_scheduler_auto: airflow_requirements
	@LOG_PORT=$$(python3 -c "import socket;s=socket.socket();s.bind(('',0));print(s.getsockname()[1]);s.close()"); \
	echo "Using AIRFLOW_LOG_SERVER_PORT=$$LOG_PORT"; \
	$(AIRFLOW_ENV) AIRFLOW__LOGGING__WORKER_LOG_SERVER_PORT=$$LOG_PORT uv run airflow scheduler

## Start Airflow API server
.PHONY: airflow_webserver
airflow_webserver: airflow_requirements
	$(AIRFLOW_ENV) uv run airflow api-server --port $(AIRFLOW_API_PORT)

## Start API server with auto-selected free API port
.PHONY: airflow_webserver_auto
airflow_webserver_auto: airflow_requirements
	@API_PORT=$$(python3 -c "import socket;s=socket.socket();s.bind(('',0));print(s.getsockname()[1]);s.close()"); \
	echo "Using AIRFLOW_API_PORT=$$API_PORT"; \
	$(AIRFLOW_ENV) uv run airflow api-server --port $$API_PORT

## Run one-shot standalone bootstrap (prints generated credentials)
.PHONY: airflow_standalone
airflow_standalone: airflow_requirements
	$(AIRFLOW_ENV) uv run airflow standalone

## Parse DAG files and write them to the metadata DB (avoids DagNotFound on trigger
## when the scheduler has not serialized this project yet)
.PHONY: airflow_dags_reserialize
airflow_dags_reserialize: airflow_requirements
	$(AIRFLOW_ENV) uv run airflow dags reserialize

## Trigger anomaly pipeline DAG manually
.PHONY: airflow_trigger
airflow_trigger: airflow_dags_reserialize
	$(AIRFLOW_ENV) uv run airflow dags trigger $(AIRFLOW_DAG_ID) \
		--conf '{"model_name":"$(MODEL)"}'

## Unpause configured DAG id
.PHONY: airflow_unpause
airflow_unpause: airflow_dags_reserialize
	$(AIRFLOW_ENV) uv run airflow dags unpause $(AIRFLOW_DAG_ID)

## List DAG runs for configured DAG id
.PHONY: airflow_list_runs
airflow_list_runs: airflow_requirements
	$(AIRFLOW_ENV) uv run airflow dags list-runs $(AIRFLOW_DAG_ID)


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
