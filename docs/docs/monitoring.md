# Monitoring

## Summary

Monitoring combines:

- runtime metrics from train/predict jobs
- drift metrics (data, target, concept proxy)
- aggregated MLflow experiment metrics

## Local stack

Start:

```bash
make monitoring_up
```

Stop:

```bash
make monitoring_down
```

Status/logs:

```bash
make monitoring_status
make monitoring_logs
```

## Services

- Grafana: `http://localhost:3000` (`admin` / `admin`)
- Prometheus: `http://localhost:9090`
- Pushgateway: `http://localhost:9091`
- MLflow exporter: `http://localhost:8010/metrics`

## Provisioned dashboards

- `Recent Train and Predict Runs`
- `Operational Health`
- `MLflow Quality: Current vs History`
- `NAB Analysis`
- `MLflow Static Overview`
- `Drift Artifacts`

The MLflow quality dashboard now compares latest run metrics against historical
context from previous runs, including:

- point metrics (`val_precision`, `val_recall`, `val_f1`)
- changepoint metrics (`val_cp_precision`, `val_cp_recall`, `val_cp_f1`)
- NAB metrics (`val_nab_standard`, `val_nab_low_fp`, `val_nab_low_fn`)
- train/inference drift metrics
- labeled aggregations (`latest`, `previous_mean`, `rolling_mean_5`, `all_mean`, `best`)

`MLflow Static Overview` provides non-time-based views for all existing runs and
latest-run comparisons, including Pareto-like proxies:

- `(val_f1 + val_nab_standard) / 2`
- `val_f1 / train_duration_seconds`

`Drift Artifacts` surfaces values from model artifact files:

- `models/<model>/drift_reference.json`
- `models/<model>/drift_report.json`

with labels for `model_name`, `dataset_scenario`, `feature`, and metric names.
It also includes a `Top 10 Drifted Features by PSI` panel (`topk(10, ...)`).

## External monitoring mode

Use external services by setting:

- `MONITORING_ENABLED`
- `PROMETHEUS_PUSHGATEWAY_URL`
- `PROMETHEUS_GROUPING_ENV`
- `PROMETHEUS_GROUPING_SERVICE`

In this mode, local docker compose is optional.

## Troubleshooting empty Grafana panels

If `Recent Train and Predict Runs` or `Operational Health` are empty:

1. Ensure train/predict jobs were run after monitoring was enabled.
2. Verify Pushgateway URL:
   - `PROMETHEUS_PUSHGATEWAY_URL=http://localhost:9091`
3. Check Pushgateway has app metrics:
   - `http://localhost:9091/metrics` should include `anomaly_pipeline_*`.
