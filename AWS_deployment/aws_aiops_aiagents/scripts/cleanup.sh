#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
CLUSTER_NAME="${CLUSTER_NAME:-aiops-eks}"
REPO_NAME="${REPO_NAME:-aiops/ingestor}"
NAMESPACE="${NAMESPACE:-aiops}"

helm -n monitoring uninstall monitoring || true
kubectl delete ns monitoring --ignore-not-found=true || true
kubectl delete ns "$NAMESPACE" --ignore-not-found=true || true
eksctl delete cluster --name "$CLUSTER_NAME" --region "$AWS_REGION"
aws ecr delete-repository --force --repository-name "$REPO_NAME" --region "$AWS_REGION" || true
docker system prune -af || true
docker volume prune -f || true
echo "[✓] Cleanup complete."
