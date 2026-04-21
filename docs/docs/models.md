# Models

## Summary

The pipeline supports three anomaly detection model families behind the same
train/predict CLI interface.

## Available models

- `isolation_forest` - fast baseline using scikit-learn
- `conv_ae` - convolutional autoencoder (TensorFlow/Keras)
- `lstm_ae` - sequence autoencoder (TensorFlow/Keras)

## Train and predict

```bash
make train MODEL=isolation_forest DATA_SCENARIO=valve1
make predict MODEL=isolation_forest DATA_SCENARIO=valve1
```

Swap `MODEL=` to test other model families.

## Evaluation and logged metrics

Training computes:

- point metrics (`val_precision`, `val_recall`, `val_f1`)
- changepoint metrics (`val_cp_precision`, `val_cp_recall`, `val_cp_f1`)
- optional NAB metrics when valid changepoints exist
- threshold and drift-related metrics

## Model artifacts

Each run writes to `models/<model_name>/`:

- serialized model files
- `train_metadata.json`
- `drift_reference.json`
- `drift_report.json`

## Model selection tips

- Start with `isolation_forest` for quick baselines and debugging
- Use autoencoders when nonlinear temporal behavior is important
- Compare by `val_f1`, `val_cp_f1`, NAB, and drift stability, not only one score
