# Serving Platform

This guide explains how to run and validate the FastAPI + Next.js serving stack
in local Docker, local UI development mode, and Kubernetes.

## Components

- API: `services/api` (FastAPI, SQLAlchemy, Alembic, PostgreSQL backend)
- UI: `services/ui` (Next.js)
- Database: PostgreSQL (`pardon_postgres` in Docker Compose)

## Local Docker stack (recommended default)

Start:

```bash
make app_up
```

Validate:

Security envs (recommended for non-dev):
- `PARDON_RETRAIN_AUTH_ENABLED=true` enables auth on `POST /api/v1/retrain`.
- `PARDON_RETRAIN_BEARER_TOKEN=<strong-secret>` expected as `Authorization: Bearer <token>`.
- `PARDON_CORS_ALLOWED_ORIGINS=http://localhost:3001,https://your-ui-host` (comma-separated).
- `API_BASE_URL=http://api:8000` is used by Next.js server-side rendering.
- `NEXT_PUBLIC_RETRAIN_API_TOKEN=<same-token>` enables UI retrain button to send bearer token.

```bash
make app_smoke
```

Endpoints:
- API health: `http://localhost:8000/healthz`
- API docs: `http://localhost:8000/docs`
- UI: `http://localhost:3001`

Stop:

```bash
make app_down
```

Inspect logs:

```bash
make app_logs
```

## Environment variables

### API security and CORS

- `PARDON_RETRAIN_AUTH_ENABLED=true`: enables auth for `POST /api/v1/retrain`
- `PARDON_RETRAIN_BEARER_TOKEN=<strong-secret>`: expected token value
- `PARDON_CORS_ALLOWED_ORIGINS=http://localhost:3001,https://your-ui-host`:
  comma-separated allowlist for browser origins

### UI API wiring

- `API_BASE_URL=http://api:8000`: server-side API URL used by UI inside Docker/K8s
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`: browser-side API URL for local UI dev
- `NEXT_PUBLIC_RETRAIN_API_TOKEN=<token>`: UI sends bearer token for retrain action

## Two UI usage modes

### Mode A: UI inside Docker Compose

- Start with `make app_up`
- Open `http://localhost:3001`
- Works well for stack-level checks and smoke validation

### Mode B: UI local dev server (best for browser API debugging)

Use this mode when browser client components must call local API directly:

```bash
make app_up
cd services/ui
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open `http://localhost:3001`.

## API operations covered by UI

- `POST /api/v1/predict`: online inference
- `GET /api/v1/predictions/runs`: run-level prediction summaries
- `GET /api/v1/predictions/runs/{request_id}`: prediction run details
- `POST /api/v1/retrain`: start background retraining
- `GET /api/v1/retrain/{job_id}`: retrain job progress
- `GET /api/v1/experiments` and `GET /api/v1/experiments/{run_id}`: runs and details
- `GET /api/v1/notifications/drift`: drift notifications feed

## Database migrations

Migrations run automatically on API container startup.

Manual migration (optional):

```bash
make db_migrate
```

Default DB URL for manual migration:
`postgresql+psycopg://pardon:pardon@localhost:5433/pardon`

Override:

```bash
make db_migrate LOCAL_DB_URL="postgresql+psycopg://user:pass@host:5432/dbname"
```

## OpenAPI and typed UI client sync

Refresh API schema and generated UI types:

```bash
make openapi_export
make ui_codegen
```

CI validates this contract sync via `make ci_openapi_codegen_check`.

## Troubleshooting

### API container exits immediately

Check API logs:

```bash
docker compose -f docker-compose.app.yml --profile app logs api
```

If startup fails with missing CLI tools (`alembic` not found), ensure compose
command uses `uv run ...` and `.venv` is not shadowed by bind mounts.

### Minikube starts but Kubernetes is not ready

If `minikube start` prints addon validation errors like
`failed to download openapi ... connection refused`, check cluster status:

```bash
minikube status
```

If you see `host: Running` but `kubelet/apiserver: Stopped`, recreate profile:

```bash
minikube stop
minikube delete --purge
minikube start --driver=docker --cpus=2 --memory=4600
```

Then enable addons explicitly after API server is up:

```bash
minikube addons enable default-storageclass
minikube addons enable storage-provisioner
minikube addons enable ingress
```

### UI shows "Failed to fetch"

- Confirm API health endpoint responds on `http://localhost:8000/healthz`
- For browser-mode UI, run local UI dev with:
  `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Check `PARDON_CORS_ALLOWED_ORIGINS` includes your UI origin

### Predictions table is empty

Run at least one prediction request (`POST /api/v1/predict`); retraining alone
does not create prediction rows.

### `rollout status` fails with `progress deadline exceeded`

This usually means new pods failed to become ready (often image pull issues).
Inspect the failing pod directly:

```bash
kubectl -n pardon get pods
kubectl -n pardon describe pod <failing-pod-name>
```

If reason is `ImagePullBackOff` for GHCR (`unauthorized`), either:
- make GHCR package public, or
- create/fix `ghcr-secret` and attach it as imagePullSecret in namespace.

