#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = itmo-aiii27-mlops
PYTHON_VERSION = 3.10
PYTHON_INTERPRETER = uv run python
UV_HTTP_TIMEOUT ?= 120
UV_HTTP_RETRIES ?= 3
MODEL ?= isolation_forest

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
	dvc remote modify --local minio_storage access_key_id "$(AWS_ACCESS_KEY_ID)"
	dvc remote modify --local minio_storage secret_access_key "$(AWS_SECRET_ACCESS_KEY)"

## Download versioned data from DVC remote
.PHONY: data_pull
data_pull:
	dvc pull

## Upload versioned data to DVC remote
.PHONY: data_push
data_push:
	dvc push




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
	$(PYTHON_INTERPRETER) -m anomaly_detection.dataset main

## Generate scaled features for train/val/test
.PHONY: features
features: requirements dataset
	$(PYTHON_INTERPRETER) -m anomaly_detection.features main

## Train selected model pipeline
.PHONY: train
train: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.train main --model-name $(MODEL)

## Run inference with selected model pipeline
.PHONY: predict
predict: requirements features
	$(PYTHON_INTERPRETER) -m anomaly_detection.modeling.predict main --model-name $(MODEL)


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
