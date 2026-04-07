from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from tensorflow import keras
from tensorflow.keras import layers


def create_sequences(values: np.ndarray, time_steps: int) -> np.ndarray:
    if len(values) < time_steps:
        raise ValueError(
            f"Not enough rows ({len(values)}) for time_steps={time_steps}"
        )
    output = []
    for idx in range(len(values) - time_steps + 1):
        output.append(values[idx : idx + time_steps])
    return np.asarray(output)


def window_scores_to_point_scores(
    scores: np.ndarray, n_points: int, time_steps: int
) -> np.ndarray:
    point_scores = np.zeros(n_points, dtype=float)
    counts = np.zeros(n_points, dtype=float)
    for w_idx, score in enumerate(scores):
        start = w_idx
        end = min(w_idx + time_steps, n_points)
        point_scores[start:end] += score
        counts[start:end] += 1.0
    counts[counts == 0.0] = 1.0
    return point_scores / counts


class AnomalyModel(Protocol):
    model_name: str

    def fit(self, x_train: np.ndarray) -> None: ...

    def score_samples(self, x_data: np.ndarray) -> np.ndarray: ...

    def fit_points(self, x_train: np.ndarray) -> None: ...

    def score_points(self, x_data: np.ndarray) -> np.ndarray: ...

    def save(self, path: Path) -> None: ...

    def mlflow_log_model(self, model_artifact_name: str) -> str: ...

    @staticmethod
    def mlflow_load_model(model_uri: str) -> Any: ...

    @staticmethod
    def score_points_with_mlflow_model(
        loaded_model: Any, x_data: np.ndarray, time_steps: int
    ) -> np.ndarray: ...

    @classmethod
    def load(cls, path: Path) -> "AnomalyModel": ...


@dataclass
class IsolationForestModel:
    model_name: str = "isolation_forest"
    random_state: int = 0
    contamination: float = 0.005
    n_estimators: int = 200
    n_jobs: int = -1

    def __post_init__(self) -> None:
        self.model = IsolationForest(
            random_state=self.random_state,
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            n_jobs=self.n_jobs,
        )

    def fit(self, x_train: np.ndarray) -> None:
        self.model.fit(x_train)

    def score_samples(self, x_data: np.ndarray) -> np.ndarray:
        # sklearn returns larger for more normal points; invert to anomaly score
        return -self.model.score_samples(x_data)

    def fit_points(self, x_train: np.ndarray) -> None:
        self.fit(x_train)

    def score_points(self, x_data: np.ndarray) -> np.ndarray:
        return self.score_samples(x_data)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path / "model.joblib")
        metadata = {"model_type": "isolation_forest"}
        (path / "metadata.json").write_text(json.dumps(metadata), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "IsolationForestModel":
        instance = cls()
        instance.model = joblib.load(path / "model.joblib")
        return instance

    def mlflow_log_model(self, model_artifact_name: str) -> str:
        import mlflow.sklearn

        model_info = mlflow.sklearn.log_model(
            self.model, name=model_artifact_name
        )
        return model_info.model_uri

    @staticmethod
    def mlflow_load_model(model_uri: str) -> Any:
        import mlflow.sklearn

        return mlflow.sklearn.load_model(model_uri)

    @staticmethod
    def score_points_with_mlflow_model(
        loaded_model: Any, x_data: np.ndarray, time_steps: int
    ) -> np.ndarray:
        del time_steps
        return -loaded_model.score_samples(x_data)


@dataclass
class ConvAEModel:
    model_name: str = "conv_ae"
    time_steps: int = 60
    epochs: int = 20
    batch_size: int = 32
    learning_rate: float = 1e-3
    verbose: int = 0

    def _build(self, n_features: int) -> keras.Model:
        inputs = keras.Input(shape=(self.time_steps, n_features))
        x = layers.Conv1D(32, 5, padding="same", activation="relu")(inputs)
        x = layers.MaxPooling1D(2)(x)
        x = layers.Conv1D(16, 3, padding="same", activation="relu")(x)
        x = layers.UpSampling1D(2)(x)
        outputs = layers.Conv1D(
            n_features, 3, padding="same", activation="linear"
        )(x)
        model = keras.Model(inputs, outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(self.learning_rate), loss="mae"
        )
        return model

    def fit(self, x_train: np.ndarray) -> None:
        self.n_features_ = x_train.shape[-1]
        self.model = self._build(self.n_features_)
        self.model.fit(
            x_train,
            x_train,
            epochs=self.epochs,
            batch_size=self.batch_size,
            verbose=self.verbose,
        )

    def score_samples(self, x_data: np.ndarray) -> np.ndarray:
        reconstructed = self.model.predict(x_data, verbose=0)
        return np.mean(np.abs(reconstructed - x_data), axis=(1, 2))

    def fit_points(self, x_train: np.ndarray) -> None:
        train_seq = create_sequences(x_train, time_steps=self.time_steps)
        self.fit(train_seq)

    def score_points(self, x_data: np.ndarray) -> np.ndarray:
        eval_seq = create_sequences(x_data, time_steps=self.time_steps)
        window_scores = self.score_samples(eval_seq)
        return window_scores_to_point_scores(
            window_scores, n_points=len(x_data), time_steps=self.time_steps
        )

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.model.save(path / "model.keras")
        metadata = {
            "model_type": "conv_ae",
            "time_steps": self.time_steps,
            "n_features": self.n_features_,
        }
        (path / "metadata.json").write_text(json.dumps(metadata), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "ConvAEModel":
        metadata = json.loads((path / "metadata.json").read_text("utf-8"))
        instance = cls(time_steps=int(metadata["time_steps"]))
        instance.n_features_ = int(metadata["n_features"])
        instance.model = keras.models.load_model(path / "model.keras")
        return instance

    def mlflow_log_model(self, model_artifact_name: str) -> str:
        import mlflow.tensorflow

        model_info = mlflow.tensorflow.log_model(
            self.model, name=model_artifact_name
        )
        return model_info.model_uri

    @staticmethod
    def mlflow_load_model(model_uri: str) -> Any:
        import mlflow.tensorflow

        return mlflow.tensorflow.load_model(model_uri)

    @staticmethod
    def score_points_with_mlflow_model(
        loaded_model: Any, x_data: np.ndarray, time_steps: int
    ) -> np.ndarray:
        eval_seq = create_sequences(x_data, time_steps=time_steps)
        window_scores = np.mean(
            np.abs(loaded_model.predict(eval_seq, verbose=0) - eval_seq),
            axis=(1, 2),
        )
        return window_scores_to_point_scores(
            window_scores, n_points=len(x_data), time_steps=time_steps
        )


@dataclass
class LSTMAEModel:
    model_name: str = "lstm_ae"
    time_steps: int = 10
    epochs: int = 20
    batch_size: int = 32
    learning_rate: float = 1e-3
    verbose: int = 0

    def _build(self, n_features: int) -> keras.Model:
        inputs = keras.Input(shape=(self.time_steps, n_features))
        encoded = layers.LSTM(64, return_sequences=False)(inputs)
        repeated = layers.RepeatVector(self.time_steps)(encoded)
        decoded = layers.LSTM(64, return_sequences=True)(repeated)
        outputs = layers.TimeDistributed(layers.Dense(n_features))(decoded)
        model = keras.Model(inputs, outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(self.learning_rate), loss="mae"
        )
        return model

    def fit(self, x_train: np.ndarray) -> None:
        self.n_features_ = x_train.shape[-1]
        self.model = self._build(self.n_features_)
        self.model.fit(
            x_train,
            x_train,
            epochs=self.epochs,
            batch_size=self.batch_size,
            verbose=self.verbose,
        )

    def score_samples(self, x_data: np.ndarray) -> np.ndarray:
        reconstructed = self.model.predict(x_data, verbose=0)
        return np.mean(np.abs(reconstructed - x_data), axis=(1, 2))

    def fit_points(self, x_train: np.ndarray) -> None:
        train_seq = create_sequences(x_train, time_steps=self.time_steps)
        self.fit(train_seq)

    def score_points(self, x_data: np.ndarray) -> np.ndarray:
        eval_seq = create_sequences(x_data, time_steps=self.time_steps)
        window_scores = self.score_samples(eval_seq)
        return window_scores_to_point_scores(
            window_scores, n_points=len(x_data), time_steps=self.time_steps
        )

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.model.save(path / "model.keras")
        metadata = {
            "model_type": "lstm_ae",
            "time_steps": self.time_steps,
            "n_features": self.n_features_,
        }
        (path / "metadata.json").write_text(json.dumps(metadata), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "LSTMAEModel":
        metadata = json.loads((path / "metadata.json").read_text("utf-8"))
        instance = cls(time_steps=int(metadata["time_steps"]))
        instance.n_features_ = int(metadata["n_features"])
        instance.model = keras.models.load_model(path / "model.keras")
        return instance

    def mlflow_log_model(self, model_artifact_name: str) -> str:
        import mlflow.tensorflow

        model_info = mlflow.tensorflow.log_model(
            self.model, name=model_artifact_name
        )
        return model_info.model_uri

    @staticmethod
    def mlflow_load_model(model_uri: str) -> Any:
        import mlflow.tensorflow

        return mlflow.tensorflow.load_model(model_uri)

    @staticmethod
    def score_points_with_mlflow_model(
        loaded_model: Any, x_data: np.ndarray, time_steps: int
    ) -> np.ndarray:
        eval_seq = create_sequences(x_data, time_steps=time_steps)
        window_scores = np.mean(
            np.abs(loaded_model.predict(eval_seq, verbose=0) - eval_seq),
            axis=(1, 2),
        )
        return window_scores_to_point_scores(
            window_scores, n_points=len(x_data), time_steps=time_steps
        )


@dataclass(frozen=True)
class ModelStrategy:
    name: str
    model_cls: type
    builder: Any

    def build(self, **kwargs: float | int) -> AnomalyModel:
        return self.builder(kwargs)

    def load(self, path: Path) -> AnomalyModel:
        return self.model_cls.load(path)


MODEL_REGISTRY: dict[str, ModelStrategy] = {
    "isolation_forest": ModelStrategy(
        name="isolation_forest",
        model_cls=IsolationForestModel,
        builder=lambda kwargs: IsolationForestModel(
            random_state=int(kwargs.get("seed", 0)),
            contamination=float(kwargs.get("contamination", 0.005)),
            n_estimators=int(kwargs.get("n_estimators", 200)),
            n_jobs=int(kwargs.get("n_jobs", -1)),
        ),
    ),
    "conv_ae": ModelStrategy(
        name="conv_ae",
        model_cls=ConvAEModel,
        builder=lambda kwargs: ConvAEModel(
            time_steps=int(kwargs.get("time_steps", 60)),
            epochs=int(kwargs.get("epochs", 20)),
            batch_size=int(kwargs.get("batch_size", 32)),
            learning_rate=float(kwargs.get("learning_rate", 1e-3)),
            verbose=int(kwargs.get("verbose", 0)),
        ),
    ),
    "lstm_ae": ModelStrategy(
        name="lstm_ae",
        model_cls=LSTMAEModel,
        builder=lambda kwargs: LSTMAEModel(
            time_steps=int(kwargs.get("time_steps", 10)),
            epochs=int(kwargs.get("epochs", 20)),
            batch_size=int(kwargs.get("batch_size", 32)),
            learning_rate=float(kwargs.get("learning_rate", 1e-3)),
            verbose=int(kwargs.get("verbose", 0)),
        ),
    ),
}


def get_strategy(model_name: str) -> ModelStrategy:
    try:
        return MODEL_REGISTRY[model_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown model_name. Use one of: {list(MODEL_REGISTRY.keys())}"
        ) from exc


def get_model_class(model_name: str):
    return get_strategy(model_name).model_cls


def load_model(model_name: str, path: Path) -> AnomalyModel:
    return get_strategy(model_name).load(path)


def build_model(model_name: str, **kwargs: float | int) -> AnomalyModel:
    return get_strategy(model_name).build(**kwargs)
