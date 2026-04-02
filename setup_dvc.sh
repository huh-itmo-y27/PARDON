#!/bin/bash

export $(grep -v '^#' .env | xargs)

uv run dvc remote modify --local minio_storage access_key_id "$MINIO_ACCESS_KEY"
uv run dvc remote modify --local minio_storage secret_access_key "$MINIO_SECRET_KEY"

echo "DVC configured"