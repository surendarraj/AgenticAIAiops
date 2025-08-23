#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
CLUSTER_NAME="${CLUSTER_NAME:-aiops-eks}"
REPO_NAME="${REPO_NAME:-aiops/ingestor}"
IMAGE_TAG="${IMAGE_TAG:-v1}"
NAMESPACE="${NAMESPACE:-aiops}"
AUTH_VAL="${AUTH_VAL:-testtoken-123}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"

if [ -z "$OPENAI_API_KEY" ]; then
  echo "[ERROR] OPENAI_API_KEY is REQUIRED for the LLM gate (GPT-3.5 Turbo)."
  exit 1
fi

aws configure set default.region "$AWS_REGION"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMG="${ECR_URL}/${REPO_NAME}:${IMAGE_TAG}"

# Tools
if ! command -v eksctl >/dev/null 2>&1; then
  curl -sSL "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" -o /tmp/eksctl.tgz
  tar -xzf /tmp/eksctl.tgz -C /tmp && sudo mv /tmp/eksctl /usr/local/bin/eksctl
fi
if ! command -v kubectl >/dev/null 2>&1; then
  curl -sSL -o /tmp/kubectl "https://s3.us-west-2.amazonaws.com/amazon-eks/1.30.0/2024-07-05/bin/linux/amd64/kubectl"
  chmod +x /tmp/kubectl && sudo mv /tmp/kubectl /usr/local/bin/kubectl
fi
if ! command -v helm >/dev/null 2>&1; then
  curl -sSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Cluster (idempotent)
STACK="eksctl-${CLUSTER_NAME}-cluster"
if aws cloudformation describe-stacks --stack-name "$STACK" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "[i] Cluster stack $STACK exists; skipping creation"
else
  eksctl create cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" --nodes 2 --node-type t3.medium --managed
fi
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"

# Build & push
aws ecr create-repository --repository-name "$REPO_NAME" 2>/dev/null || true
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_URL"
docker build -t "$IMG" -f Dockerfile .
docker push "$IMG"

# Deploy services
sed "s|REPLACE_IMAGE|$IMG|g" k8s.yaml | kubectl apply -f -

# Inject OPENAI key & auth token
kubectl -n "$NAMESPACE" create secret generic openai --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" set env deploy/aiops-agents --from=secret/openai
kubectl -n "$NAMESPACE" set env deploy/aiops-agents AUTH_TOKEN="$AUTH_VAL" || true
kubectl -n "$NAMESPACE" rollout status deploy/aiops-agents

# kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create ns monitoring 2>/dev/null || true
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.enabled=false

# Wait for alertmanager to be ready
kubectl -n monitoring rollout status statefulset/monitoring-kube-prometheus-alertmanager

# Allow AlertmanagerConfig from any ns
kubectl -n monitoring patch alertmanager monitoring-kube-prometheus-alertmanager \
  --type merge -p '{"spec":{"alertmanagerConfigSelector":{},"alertmanagerConfigNamespaceSelector":{}}}'

# Secret for webhook auth
kubectl -n monitoring create secret generic aiops-auth --from-literal=token="$AUTH_VAL" --dry-run=client -o yaml | kubectl apply -f -

# Apply rules and webhook
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl apply -f monitoring/alertmanager-config.yaml

echo " Deployed with GPT-3.5 Turbo LLM gate."
echo " Trigger demo alerts: kubectl apply -f monitoring/demo-rules.yaml"

