Getting started
===============

## 1) Install dependencies

```bash
make requirements
```

## 2) Prepare a dataset scenario

Choose a scenario from `data/raw` (`valve1`, `valve2`, `other`,
`anomaly-free`, or `all`):

```bash
make dataset DATA_SCENARIO=valve2
make features DATA_SCENARIO=valve2
```

Tip: avoid `all` if any source files are missing required label columns.

## 3) Run training and inference experiments

```bash
make train MODEL=isolation_forest DATA_SCENARIO=valve1 
make predict MODEL=isolation_forest DATA_SCENARIO=valve1 
```

Optional MLflow UI:

```bash
make mlflow_ui
```

## 4) Start Grafana + Prometheus services

```bash
make monitoring_up
```

Service URLs:

- Grafana: `http://localhost:3000` (`admin` / `admin`)
- Prometheus: `http://localhost:9090`
- Pushgateway: `http://localhost:9091`

In Grafana, inspect:

- Recent Train and Predict Runs
- Operational Health
- MLflow Experiment Quality

## Next reading

- Dataset details: `Dataset (SKAB)`
- Model behavior: `Models`
- Tracking and registry: `MLflow`
- Dashboards and metric paths: `Monitoring`

## 5) Stop monitoring services

```bash
make monitoring_down
```
