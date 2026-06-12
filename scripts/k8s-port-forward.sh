#!/bin/sh
set -eu

NAMESPACE="${K8S_NAMESPACE:-pardon}"
API_LOCAL_PORT="${API_LOCAL_PORT:-8000}"
UI_LOCAL_PORT="${UI_LOCAL_PORT:-3001}"
GRAFANA_LOCAL_PORT="${GRAFANA_LOCAL_PORT:-3000}"
MLFLOW_LOCAL_PORT="${MLFLOW_LOCAL_PORT:-5000}"
PROMETHEUS_LOCAL_PORT="${PROMETHEUS_LOCAL_PORT:-9090}"
PUSHGATEWAY_LOCAL_PORT="${PUSHGATEWAY_LOCAL_PORT:-9091}"
API_REMOTE_PORT="${API_REMOTE_PORT:-8000}"
UI_REMOTE_PORT="${UI_REMOTE_PORT:-3001}"
GRAFANA_REMOTE_PORT="${GRAFANA_REMOTE_PORT:-3000}"
MLFLOW_REMOTE_PORT="${MLFLOW_REMOTE_PORT:-5000}"
PROMETHEUS_REMOTE_PORT="${PROMETHEUS_REMOTE_PORT:-9090}"
PUSHGATEWAY_REMOTE_PORT="${PUSHGATEWAY_REMOTE_PORT:-9091}"
RETRY_SECONDS="${PORT_FORWARD_RETRY_SECONDS:-2}"

PIDS=""

cleanup() {
  for pid in $PIDS; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}

trap cleanup EXIT INT TERM

wait_for_rollout() {
  deployment="$1"
  kubectl -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout=180s
}

forward_loop() {
  name="$1"
  service="$2"
  local_port="$3"
  remote_port="$4"
  deployment="$5"

  while true; do
    echo "Waiting for deployment/$deployment before forwarding $name..."
    wait_for_rollout "$deployment" || true

    echo "Forwarding $name: http://localhost:$local_port -> service/$service:$remote_port"
    kubectl -n "$NAMESPACE" port-forward "svc/$service" "$local_port:$remote_port" || true

    echo "$name port-forward stopped. Reconnecting in ${RETRY_SECONDS}s..."
    sleep "$RETRY_SECONDS"
  done
}

forward_loop "api" "pardon-api" "$API_LOCAL_PORT" "$API_REMOTE_PORT" "pardon-api" &
PIDS="$PIDS $!"

forward_loop "ui" "pardon-ui" "$UI_LOCAL_PORT" "$UI_REMOTE_PORT" "pardon-ui" &
PIDS="$PIDS $!"

forward_loop "grafana" "pardon-grafana" "$GRAFANA_LOCAL_PORT" "$GRAFANA_REMOTE_PORT" "pardon-grafana" &
PIDS="$PIDS $!"

forward_loop "mlflow" "pardon-mlflow" "$MLFLOW_LOCAL_PORT" "$MLFLOW_REMOTE_PORT" "pardon-mlflow" &
PIDS="$PIDS $!"

forward_loop "prometheus" "pardon-prometheus" "$PROMETHEUS_LOCAL_PORT" "$PROMETHEUS_REMOTE_PORT" "pardon-prometheus" &
PIDS="$PIDS $!"

forward_loop "pushgateway" "pardon-pushgateway" "$PUSHGATEWAY_LOCAL_PORT" "$PUSHGATEWAY_REMOTE_PORT" "pardon-pushgateway" &
PIDS="$PIDS $!"

echo "Port forwards are running. Press Ctrl+C to stop."
wait
