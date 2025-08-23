#!/usr/bin/env bash
set -euo pipefail

N="${N:-5}"
NAMESPACE="${NAMESPACE:-aiops}"
TARGET_NAMESPACE="${TARGET_NAMESPACE:-default}"
TARGET_DEPLOYMENT="${TARGET_DEPLOYMENT:-your-app}"
AUTH_VAL="${AUTH_VAL:-testtoken-123}"
SLEEP_AFTER_POST="${SLEEP_AFTER_POST:-6}"
PF_PORT="${PF_PORT:-18080}"

echo "[i] Ensuring target app exists: ${TARGET_NAMESPACE}/${TARGET_DEPLOYMENT} (1 replica)"
kubectl -n "${TARGET_NAMESPACE}" get deploy "${TARGET_DEPLOYMENT}" >/dev/null 2>&1 || \
  kubectl -n "${TARGET_NAMESPACE}" create deployment "${TARGET_DEPLOYMENT}" --image=nginx --replicas=1
kubectl -n "${TARGET_NAMESPACE}" rollout status deploy/"${TARGET_DEPLOYMENT}"

echo "[i] Port-forward ${NAMESPACE}/svc/aiops-agents-svc -> localhost:${PF_PORT}"
kubectl -n "${NAMESPACE}" port-forward svc/aiops-agents-svc "${PF_PORT}:80" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill "${PF_PID}" 2>/dev/null || true' EXIT
sleep 2

for i in $(seq 1 "${N}"); do
  echo "===== Iter ${i}/${N} ====="
  TS=$(date +%s)

  payload=$(cat <<JSON
{
  "receiver": "aiops-webhook",
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": { "alertname": "DemoCPUHigh", "metric": "cpu" },
    "annotations": { "summary": "Demo CPU spike run-${i}-${TS}", "value": "90" }
  }]
}
JSON
)
  curl -sS "http://127.0.0.1:${PF_PORT}/ingest/alertmanager" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${AUTH_VAL}" \
    --data "${payload}" | sed -e 's/},{/},\n  {/' -e 's/\\\\n/\n/g' || true

  echo "[i] Wait ${SLEEP_AFTER_POST}s for LLM + remediation..."
  sleep "${SLEEP_AFTER_POST}"

  SPEC=$(kubectl -n "${TARGET_NAMESPACE}" get deploy "${TARGET_DEPLOYMENT}" -o jsonpath='{.spec.replicas}')
  STAT=$(kubectl -n "${TARGET_NAMESPACE}" get deploy "${TARGET_DEPLOYMENT}" -o jsonpath='{.status.replicas}')
  echo "[=] Replicas: spec=${SPEC} status=${STAT}"

  echo "[i] Scale back to 1"
  kubectl -n "${TARGET_NAMESPACE}" scale deploy "${TARGET_DEPLOYMENT}" --replicas=1
  kubectl -n "${TARGET_NAMESPACE}" rollout status deploy/"${TARGET_DEPLOYMENT}"
done

echo "[✓] Done. Watch: kubectl -n ${NAMESPACE} logs deploy/aiops-agents -f | grep -E 'DECISIONS|ACTION'"
