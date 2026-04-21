import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# Data contract defaults
TIMESTAMP_COL = "datetime"
LABEL_COL = "anomaly"
CHANGEPOINT_COL = "changepoint"
CSV_SEPARATOR = ";"
TRAIN_SIZE = 400
VAL_SIZE = 100
RANDOM_SEED = 0

# Model defaults
DEFAULT_MODEL_NAME = "isolation_forest"
DEFAULT_TIME_STEPS = 60
DEFAULT_THRESHOLD_QUANTILE = 0.99

# MLflow defaults
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
MLFLOW_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_EXPERIMENT_NAME", "anomaly_detection"
)
MLFLOW_INFERENCE_EXPERIMENT_NAME = os.getenv(
    "MLFLOW_INFERENCE_EXPERIMENT_NAME", "anomaly_detection_inference"
)
MLFLOW_REGISTERED_MODEL_PREFIX = os.getenv(
    "MLFLOW_REGISTERED_MODEL_PREFIX", "anomaly_detection"
)

# Monitoring defaults
MONITORING_ENABLED = os.getenv("MONITORING_ENABLED", "true").lower() == "true"
PROMETHEUS_PUSHGATEWAY_URL = os.getenv("PROMETHEUS_PUSHGATEWAY_URL", "")
PROMETHEUS_GROUPING_ENV = os.getenv("PROMETHEUS_GROUPING_ENV", "local")
PROMETHEUS_GROUPING_SERVICE = os.getenv(
    "PROMETHEUS_GROUPING_SERVICE", "anomaly_detection"
)
MONITORING_EXPORTER_PORT = int(os.getenv("MONITORING_EXPORTER_PORT", "8010"))

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
