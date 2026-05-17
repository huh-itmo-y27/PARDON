# Continuous Delivery with Argo CD

This project is deployed to Kubernetes as the MLflow Prometheus exporter.
Argo CD watches the Kubernetes manifests in `deploy/k8s` and keeps the
cluster state synchronized with Git.

## What is deployed

- Docker image: `ghcr.io/huh-itmo-y27/pardon`
- Kubernetes namespace: `pardon`
- Deployment: `pardon-mlflow-exporter`
- Service: `pardon-mlflow-exporter`
- Runtime command: `python -m anomaly_detection.monitoring.mlflow_exporter`
- Metrics port: `8010`

## Repository layout

```text
deploy/
  argocd/
    application.yaml
  k8s/
    namespace.yaml
    configmap.yaml
    deployment.yaml
    service.yaml
    kustomization.yaml
```

## CD flow

1. A change is pushed to `main`.
2. GitHub Actions builds the Docker image.
3. The image is pushed to GHCR with two tags: `latest` and the short commit SHA.
4. The workflow updates `deploy/k8s/kustomization.yaml` with the new image tag.
5. Argo CD detects the Git change and syncs the Kubernetes deployment.

## One-time GitHub setup

In the GitHub repository settings:

1. Enable write permissions for workflows:
   `Settings -> Actions -> General -> Workflow permissions -> Read and write permissions`.
2. After the first image is published to GHCR, make the package public if you do
   not want to configure Kubernetes image pull secrets.

## Start Minikube

```bash
minikube start
kubectl get nodes
```

## Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
```

## Create the Argo CD application

```bash
kubectl apply -f deploy/argocd/application.yaml
```

Check that Argo CD created and synced the application:

```bash
kubectl -n argocd get applications.argoproj.io pardon
kubectl -n pardon get pods,svc
kubectl -n pardon rollout status deployment/pardon-mlflow-exporter
```

## Open Argo CD UI

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Open `https://localhost:8080`.

Get the initial admin password:

```bash
argocd admin initial-password -n argocd
```

If the `argocd` CLI is not installed, use Kubernetes directly:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

## Verify the deployed exporter

Forward the service port:

```bash
kubectl -n pardon port-forward svc/pardon-mlflow-exporter 8010:8010
```

In another terminal:

```bash
curl http://localhost:8010/metrics
```

You should see Prometheus metrics in the response.

## Useful troubleshooting commands

```bash
kubectl -n pardon describe pod -l app.kubernetes.io/name=pardon
kubectl -n pardon logs deployment/pardon-mlflow-exporter
kubectl -n argocd describe applications.argoproj.io pardon
```

If the pod has `ImagePullBackOff`, check that the GHCR package is public or
configure an `imagePullSecret` for `ghcr.io`.
