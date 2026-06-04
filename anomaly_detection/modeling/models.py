from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

if hasattr(keras, "saving") and hasattr(
    keras.saving, "register_keras_serializable"
):
    register_keras_serializable = keras.saving.register_keras_serializable
else:
    register_keras_serializable = keras.utils.register_keras_serializable


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


@dataclass
class TCNAEModel:
    model_name: str = "tcn_ae"
    time_steps: int = 60
    filters: int = 64
    kernel_size: int = 3
    dilations: tuple[int, ...] = (1, 2, 4, 8, 16)
    latent_dim: int = 32
    epochs: int = 20
    batch_size: int = 32
    learning_rate: float = 1e-3
    dropout_rate: float = 0.1
    verbose: int = 0

    def __post_init__(self) -> None:
        self.model = None
        self.encoder_model = None
        self.decoder_model = None
        self.n_features_ = None

    def _residual_block(
            self,
            x: keras.layers.Layer,
            filters: int,
            dilation: int,
            dropout_rate: float = 0.1
    ) -> keras.layers.Layer:
        from tensorflow.keras import layers

        shortcut = x

        x = layers.Conv1D(
            filters,
            self.kernel_size,
            padding="causal",
            dilation_rate=dilation,
            activation="relu",
        )(x)
        x = layers.Dropout(dropout_rate)(x)

        x = layers.Conv1D(
            filters,
            self.kernel_size,
            padding="causal",
            dilation_rate=dilation,
            activation="relu",
        )(x)
        x = layers.Dropout(dropout_rate)(x)

        if shortcut.shape[-1] != filters:
            shortcut = layers.Conv1D(filters, 1, padding="same")(shortcut)

        return layers.Add()([x, shortcut])

    def _build_encoder(self, input_shape: tuple[int, int]) -> keras.Model:

        inputs = keras.Input(shape=input_shape)
        x = inputs

        for dilation in self.dilations:
            x = self._residual_block(x, self.filters, dilation, self.dropout_rate)

        x = layers.Conv1D(self.latent_dim, 1, padding="same", activation="relu")(x)

        encoder = keras.Model(inputs, x, name="tcn_encoder")
        return encoder

    def _build_decoder(self, latent_shape: tuple[int, int]) -> keras.Model:

        inputs = keras.Input(shape=latent_shape)
        x = inputs

        x = layers.Conv1D(self.filters, 1, padding="same", activation="relu")(x)

        for dilation in reversed(self.dilations):
            x = self._residual_block(x, self.filters, dilation, self.dropout_rate)

        outputs = layers.Conv1D(self.n_features_, 1, padding="same", activation="linear")(x)

        decoder = keras.Model(inputs, outputs, name="tcn_decoder")
        return decoder

    def _build(self, n_features: int) -> keras.Model:
        input_shape = (self.time_steps, n_features)

        self.encoder = self._build_encoder(input_shape)
        latent_shape = self.encoder.output_shape[1:]
        self.decoder = self._build_decoder(latent_shape)

        inputs = keras.Input(shape=input_shape)
        encoded = self.encoder(inputs)
        decoded = self.decoder(encoded)

        model = keras.Model(inputs, decoded, name="tcn_ae")
        model.compile(
            optimizer=keras.optimizers.Adam(self.learning_rate),
            loss="mae",
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
            "model_type": "tcn_ae",
            "time_steps": self.time_steps,
            "filters": self.filters,
            "dilations": list(self.dilations),
            "latent_dim": self.latent_dim,
            "n_features": self.n_features_,
        }
        (path / "metadata.json").write_text(json.dumps(metadata), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "TCNAEModel":
        metadata = json.loads((path / "metadata.json").read_text("utf-8"))
        instance = cls(
            time_steps=int(metadata["time_steps"]),
            filters=int(metadata["filters"]),
            dilations=tuple(metadata["dilations"]),
            latent_dim=int(metadata["latent_dim"]),
        )
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
        reconstructed = loaded_model.predict(eval_seq, verbose=0)
        window_scores = np.mean(np.abs(reconstructed - eval_seq), axis=(1, 2))
        return window_scores_to_point_scores(
            window_scores, n_points=len(x_data), time_steps=time_steps
        )


@register_keras_serializable(package="Custom")
class VAELossLayer(layers.Layer):
    def __init__(self, beta=1.0, kl_weight=1.0, **kwargs):
        super().__init__(**kwargs)
        self.beta = beta
        self.kl_weight = kl_weight

    def call(self, inputs):
        x, x_recon, z_mean, z_log_var = inputs

        reconstruction_loss = ops.mean(
            ops.mean(ops.abs(x - x_recon), axis=-1)
        )

        kl_loss = -0.5 * ops.mean(
            1 + z_log_var - ops.square(z_mean) - ops.exp(z_log_var),
            axis=-1
        )

        total = reconstruction_loss + self.beta * self.kl_weight * kl_loss
        self.add_loss(total)

        return x_recon


@register_keras_serializable(package="Custom")
class VAESampling(layers.Layer):
    def call(self, inputs, training=None):
        z_mean, z_log_var = inputs
        if training is False:
            return z_mean
        epsilon = tf.random.normal(tf.shape(z_mean))
        return z_mean + tf.exp(0.5 * z_log_var) * epsilon


@dataclass
class VAEModel:
    model_name: str = "vae"
    time_steps: int = 60
    latent_dim: int = 16
    filters: int = 32
    kernel_size: int = 3
    epochs: int = 20
    batch_size: int = 32
    learning_rate: float = 1e-3
    beta: float = 1.0
    kl_weight: float = 1.0
    verbose: int = 0

    def __post_init__(self) -> None:
        self.model = None
        self.encoder = None
        self.decoder = None
        self.n_features_ = None

    def _build_encoder(self, input_shape: tuple[int, int]) -> keras.Model:

        inputs = keras.Input(shape=input_shape, name="encoder_input")

        x = layers.Conv1D(self.filters, self.kernel_size, padding="same", activation="relu")(inputs)
        x = layers.Conv1D(self.filters * 2, self.kernel_size, padding="same", activation="relu")(x)
        x = layers.Conv1D(self.filters * 4, self.kernel_size, padding="same", activation="relu")(x)

        x = layers.GlobalAveragePooling1D()(x)

        x = layers.Dense(64, activation="relu")(x)

        z_mean = layers.Dense(self.latent_dim, name="z_mean")(x)
        z_log_var = layers.Dense(self.latent_dim, name="z_log_var")(x)

        z = VAESampling(name="z")([z_mean, z_log_var])

        encoder = keras.Model(inputs, [z_mean, z_log_var, z], name="encoder")
        return encoder

    def _build_decoder(self, latent_dim: int, output_shape: tuple[int, int]) -> keras.Model:

        latent_inputs = keras.Input(shape=(latent_dim,), name="decoder_input")

        x = layers.Dense(64, activation="relu")(latent_inputs)
        x = layers.Dense(self.time_steps * self.filters, activation="relu")(x)

        x = layers.Reshape((self.time_steps, self.filters))(x)

        x = layers.Conv1DTranspose(self.filters * 4, self.kernel_size, padding="same", activation="relu")(x)
        x = layers.Conv1DTranspose(self.filters * 2, self.kernel_size, padding="same", activation="relu")(x)
        x = layers.Conv1DTranspose(self.filters, self.kernel_size, padding="same", activation="relu")(x)

        outputs = layers.Conv1DTranspose(
            output_shape[-1], self.kernel_size, padding="same", activation="linear", name="decoder_output"
        )(x)

        decoder = keras.Model(latent_inputs, outputs, name="decoder")
        return decoder

    def _build(self, n_features: int) -> keras.Model:

        input_shape = (self.time_steps, n_features)

        self.encoder = self._build_encoder(input_shape)
        self.decoder = self._build_decoder(self.latent_dim, input_shape)

        inputs = keras.Input(shape=input_shape, name="vae_input")

        z_mean, z_log_var, z = self.encoder(inputs)
        reconstructed = self.decoder(z)

        outputs = VAELossLayer(beta=self.beta, kl_weight=self.kl_weight, name="vae_loss_layer")([inputs, reconstructed,
                                                                                                 z_mean, z_log_var])

        vae = keras.Model(inputs, outputs, name="vae")

        vae.compile(optimizer=keras.optimizers.Adam(self.learning_rate))

        return vae

    def fit(self, x_train: np.ndarray) -> None:
        self.n_features_ = x_train.shape[-1]
        self.model = self._build(self.n_features_)

        dummy_target = np.zeros((len(x_train), self.time_steps, self.n_features_))

        self.model.fit(
            x_train,
            dummy_target,
            epochs=self.epochs,
            batch_size=self.batch_size,
            verbose=self.verbose,
        )

    def score_samples(self, x_data: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        reconstructed = self.model.predict(x_data, verbose=0)
        return np.mean(np.abs(reconstructed - x_data), axis=(1, 2))

    def score_with_reconstruction_probability(
            self, x_data: np.ndarray, n_samples: int = 10
    ) -> np.ndarray:
        if self.encoder is None or self.decoder is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        z_mean, z_log_var, _ = self.encoder.predict(x_data, verbose=0)

        samples = []
        for _ in range(n_samples):
            epsilon = np.random.randn(*z_mean.shape)
            z = z_mean + np.exp(z_log_var * 0.5) * epsilon
            reconstructed = self.decoder.predict(z, verbose=0)
            samples.append(reconstructed)

        samples = np.array(samples)
        reconstruction_mean = np.mean(samples, axis=0)

        return np.mean(np.abs(x_data - reconstruction_mean), axis=(1, 2))

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

        if self.encoder:
            self.encoder.save(path / "encoder.keras")
        if self.decoder:
            self.decoder.save(path / "decoder.keras")

        metadata = {
            "model_type": "vae",
            "time_steps": self.time_steps,
            "latent_dim": self.latent_dim,
            "filters": self.filters,
            "kernel_size": self.kernel_size,
            "n_features": self.n_features_,
            "beta": self.beta,
            "kl_weight": self.kl_weight,
        }
        (path / "metadata.json").write_text(json.dumps(metadata), "utf-8")

    @classmethod
    def load(cls, path: Path) -> "VAEModel":
        metadata = json.loads((path / "metadata.json").read_text("utf-8"))
        instance = cls(
            time_steps=int(metadata["time_steps"]),
            latent_dim=int(metadata["latent_dim"]),
            filters=int(metadata["filters"]),
            kernel_size=int(metadata.get("kernel_size", 3)),
            beta=float(metadata.get("beta", 1.0)),
            kl_weight=float(metadata.get("kl_weight", 1.0)),
        )
        instance.n_features_ = int(metadata["n_features"])

        instance.model = keras.models.load_model(path / "model.keras")

        encoder_path = path / "encoder.keras"
        decoder_path = path / "decoder.keras"
        if encoder_path.exists():
            instance.encoder = keras.models.load_model(
                encoder_path
            )
        if decoder_path.exists():
            instance.decoder = keras.models.load_model(decoder_path)

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
        reconstructed = loaded_model.predict(eval_seq, verbose=0)
        window_scores = np.mean(np.abs(reconstructed - eval_seq), axis=(1, 2))
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
    "tcn_ae": ModelStrategy(
        name="tcn_ae",
        model_cls=TCNAEModel,
        builder=lambda kwargs: TCNAEModel(
            time_steps=int(kwargs.get("time_steps", 60)),
            filters=int(kwargs.get("filters", 64)),
            dilations=tuple(kwargs.get("dilations", (1, 2, 4, 8, 16))),
            latent_dim=int(kwargs.get("latent_dim", 32)),
            epochs=int(kwargs.get("epochs", 20)),
            batch_size=int(kwargs.get("batch_size", 32)),
            learning_rate=float(kwargs.get("learning_rate", 1e-3)),
            dropout_rate=float(kwargs.get("dropout_rate", 0.1)),
            verbose=int(kwargs.get("verbose", 0)),
        ),
    ),
    "vae": ModelStrategy(
        name="vae",
        model_cls=VAEModel,
        builder=lambda kwargs: VAEModel(
            time_steps=int(kwargs.get("time_steps", 60)),
            latent_dim=int(kwargs.get("latent_dim", 16)),
            filters=int(kwargs.get("filters", 32)),
            epochs=int(kwargs.get("epochs", 20)),
            batch_size=int(kwargs.get("batch_size", 32)),
            learning_rate=float(kwargs.get("learning_rate", 1e-3)),
            beta=float(kwargs.get("beta", 1.0)),
            kl_weight=float(kwargs.get("kl_weight", 1.0)),
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
