# Serving Platform

## Local stack (FastAPI + Next.js)

Run the app stack:

```bash
make app_up
```

This stack now runs PostgreSQL as the API persistence backend through SQLAlchemy ORM.
Database schema is managed with Alembic migrations.

Security envs (recommended for non-dev):
- `PARDON_RETRAIN_AUTH_ENABLED=true` enables auth on `POST /api/v1/retrain`.
- `PARDON_RETRAIN_BEARER_TOKEN=<strong-secret>` expected as `Authorization: Bearer <token>`.
- `PARDON_CORS_ALLOWED_ORIGINS=http://localhost:3001,https://your-ui-host` (comma-separated).
- `NEXT_PUBLIC_RETRAIN_API_TOKEN=<same-token>` enables UI retrain button to send bearer token.

Endpoints:
- API health: `http://localhost:8000/healthz`
- OpenAPI: `http://localhost:8000/docs`
- UI: `http://localhost:3001`

Stop:

```bash
make app_down
```

Run migrations manually (optional, startup already runs them):

```bash
make db_migrate
```

`db_migrate` uses localhost Postgres by default (`postgresql+psycopg://pardon:pardon@localhost:5433/pardon`).
If you need a different database URL, override `LOCAL_DB_URL`:

```bash
make db_migrate LOCAL_DB_URL="postgresql+psycopg://user:pass@host:5432/dbname"
```

## Split-ready API contract workflow

Export backend OpenAPI schema:

```bash
make openapi_export
```

Generate typed UI schema client:

```bash
make ui_codegen
```

This keeps `services/ui` decoupled from backend internals and makes future repo split easier.
The UI fetch layer is centralized in `services/ui/lib/api-client.ts` and typed from generated OpenAPI schema.

## API endpoints

- `POST /api/v1/predict` - online inference for provided feature vectors.
- `GET /api/v1/predictions/recent` - recent inference table data.
- `POST /api/v1/retrain` - trigger background retraining.
- `GET /api/v1/retrain/{job_id}` - retrain job status.
- `GET /api/v1/experiments` - MLflow experiments/runs list.
- `GET /api/v1/notifications/drift` - drift notifications feed.

## Minikube deployment

1. Build images in local docker daemon:

```bash
docker build -f services/api/Dockerfile -t pardon-api:latest .
docker build -f services/ui/Dockerfile -t pardon-ui:latest .
```

2. Load images to minikube:

```bash
minikube image load pardon-api:latest
minikube image load pardon-ui:latest
```

3. Deploy:

```bash
make k8s_minikube_up
make k8s_deploy
make k8s_status
```

Add `pardon.local` to `/etc/hosts` pointing to minikube IP to use ingress host routing.

