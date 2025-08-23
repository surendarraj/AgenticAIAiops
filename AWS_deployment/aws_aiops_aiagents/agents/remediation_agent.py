from __future__ import annotations
import os
from typing import Dict, Any
from kubernetes import client, config as k8s_config

MAX_REPLICAS = int(os.environ.get("MAX_REPLICAS", "10"))
DRY_RUN = os.environ.get("DRY_RUN","false").lower() == "true"

def _k8s():
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()
    return client.AppsV1Api()

def _current(ns: str, dep: str) -> int:
    api = _k8s()
    sc = api.read_namespaced_deployment_scale(dep, ns)
    return int(getattr(sc.status, "replicas", 0) or 0)

def _scale(ns: str, dep: str, replicas: int):
    api = _k8s()
    body = {"spec": {"replicas": int(replicas)}}
    if DRY_RUN:
        return {"dry_run": True, "namespace": ns, "deployment": dep, "replicas": replicas}
    out = api.patch_namespaced_deployment_scale(name=dep, namespace=ns, body=body)
    return {"dry_run": False, "namespace": ns, "deployment": dep, "replicas": replicas,
            "status": getattr(getattr(out, "status", None), "replicas", None)}

def remediation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    ns  = state.get("target_namespace") or os.environ.get("TARGET_NAMESPACE","default")
    dep = state.get("target_deployment") or os.environ.get("TARGET_DEPLOYMENT","your-app")

    if not state.get("should_remediate"):
        state["action"] = {"skipped": True, "reason": "policy/llm gate not satisfied", "namespace": ns, "deployment": dep}
        return state

    cur = _current(ns, dep)
    desired = cur + 1
    plan = state.get("llm_plan") or {}
    if plan.get("action") == "scale":
        if plan.get("targetReplicas") is not None:
            desired = int(plan["targetReplicas"])
        elif plan.get("replicasDelta") is not None:
            desired = cur + int(plan["replicasDelta"])

    desired = min(desired, MAX_REPLICAS)
    state["action"] = _scale(ns, dep, desired)
    state["action"]["llm_plan"] = plan
    state["action"]["current"] = cur
    return state
