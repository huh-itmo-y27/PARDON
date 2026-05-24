# Continuous Delivery with Argo CD

This project is deployed to Kubernetes as the PARDON WebUI application.
Argo CD watches the `deploy/k8s/overlays/argocd` Kustomize overlay and keeps
the cluster state synchronized with Git.

## What is deployed

- API Docker image: `ghcr.io/huh-itmo-y27/pardon/api`
- UI Docker image: `ghcr.io/huh-itmo-y27/pardon/ui`
- Kubernetes namespace: `pardon`
- Deployments: `pardon-api`, `pardon-ui`, `pardon-postgres`
- Services: `pardon-api`, `pardon-ui`, `pardon-postgres`
- Ingress host: `pardon.local`

## Repository layout

```text
deploy/
  argocd/
    application.yaml
  k8s/
    base/
      namespace.yaml
      configmap.yaml
      deployment.yaml
      ingress.yaml
      service.yaml
      kustomization.yaml
    overlays/
      argocd/
        kustomization.yaml
      minikube/
        kustomization.yaml
```

## CD flow

1. A change is pushed to `main`.
2. GitHub Actions builds the API and UI Docker images.
3. Both images are pushed to GHCR with two tags: `latest` and the short commit SHA.
4. The workflow updates `deploy/k8s/overlays/argocd/kustomization.yaml` with the new image tags.
5. Argo CD detects the Git change and syncs the Kubernetes deployments.

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

If you use the `pardon.local` ingress locally, point it to Minikube:

```bash
echo "$(minikube ip) pardon.local" | sudo tee -a /etc/hosts
```

## Create the Argo CD application

```bash
kubectl apply -f deploy/argocd/application.yaml
```

Check that Argo CD created and synced the application:

```bash
kubectl -n argocd get applications.argoproj.io pardon
kubectl -n pardon get pods,svc
kubectl -n pardon rollout status deployment/pardon-api
kubectl -n pardon rollout status deployment/pardon-ui
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

## Verify the deployed WebUI

Open the application through ingress:

```bash
curl http://pardon.local
```

Or forward the UI service locally:

```bash
kubectl -n pardon port-forward svc/pardon-ui 3001:3001
```

Open `http://localhost:3001`.

## Useful troubleshooting commands

```bash
kubectl -n pardon describe pod -l app.kubernetes.io/name=pardon
kubectl -n pardon logs deployment/pardon-api
kubectl -n pardon logs deployment/pardon-ui
kubectl -n argocd describe applications.argoproj.io pardon
```

If the pod has `ImagePullBackOff`, check that the GHCR package is public or
configure an `imagePullSecret` for `ghcr.io`.
