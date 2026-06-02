# PARDON Documentation

Use this page as a task-based map to the right guide.

## Choose your scenario

- First local run (data -> train -> predict): `Getting Started`
- Local API + Web UI serving and troubleshooting: `Serving Platform`
- Kubernetes delivery and GitOps with Argo CD: `CD with Argo CD`
- Dataset schema and scenario prep: `Dataset (SKAB)`
- Model families and training behavior: `Models`
- Experiment tracking and registry behavior: `MLflow`
- Dashboards and metrics operations: `Monitoring`
- Docs publishing workflow: `Publish Docs`

## Suggested reading paths

### Path A: ML workflow only

1. `Getting Started`
2. `Dataset (SKAB)`
3. `Models`
4. `MLflow`
5. `Monitoring`

### Path B: Serving + product workflow

1. `Getting Started`
2. `Serving Platform`
3. `Monitoring`

### Path C: Kubernetes + GitOps delivery

1. `Serving Platform`
2. `CD with Argo CD`
3. `Monitoring`

## Quick command reference

- `make requirements`
- `make dataset DATA_SCENARIO=valve1`
- `make features DATA_SCENARIO=valve1`
- `make train MODEL=isolation_forest DATA_SCENARIO=valve1`
- `make predict MODEL=isolation_forest DATA_SCENARIO=valve1`
- `make app_up` / `make app_down`
- `make k8s_minikube_up` / `make k8s_deploy`


