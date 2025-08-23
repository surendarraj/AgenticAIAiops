from __future__ import annotations
import os, re, logging, json
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Header, HTTPException
from agents.graph import build_graph

LOG = logging.getLogger("aiops-service")
if not LOG.handlers:
    import sys
    h = logging.StreamHandler(sys.stdout)
    # Correct: use %(asctime)s with datefmt
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    LOG.addHandler(h)
LOG.setLevel(logging.INFO)

AUTH_TOKEN = os.environ.get("AUTH_TOKEN")  # optional

def _norm_metric(s: str) -> str:
    s = (s or "").lower()
    if "cpu" in s: return "cpu"
    if "mem" in s: return "memory"
    if "disk" in s: return "disk"
    return s

def _check_auth(x_auth_token: Optional[str], authorization: Optional[str]):
    if not AUTH_TOKEN:
        return
    if x_auth_token == AUTH_TOKEN:
        return
    if authorization and authorization.strip().lower().startswith("bearer "):
        if authorization.split(None, 1)[1].strip() == AUTH_TOKEN:
            return
    raise HTTPException(status_code=401, detail="Unauthorized")

app = FastAPI(title="AWS AIOps — Prometheus + GPT‑3.5 Turbo gate")

@app.get("/healthz")
def healthz(): return {"ok": True}

@app.post("/ingest/alertmanager")
async def ingest_alertmanager(
    req: Request,
    x_auth_token: Optional[str] = Header(default=None, convert_underscores=False),
    authorization: Optional[str] = Header(default=None),
):
    _check_auth(x_auth_token, authorization)

    payload: Dict[str, Any] = await req.json()
    alerts = payload.get("alerts", []) or []

    graph = build_graph()
    results = []
    for a in alerts:
        labels = a.get("labels", {}) or {}
        ann    = a.get("annotations", {}) or {}

        metric = _norm_metric(labels.get("metric") or labels.get("alertname") or "")
        summary = ann.get("summary") or ann.get("description") or labels.get("alertname") or ""

        raw_val = ann.get("value") or ""
        try:
            value = float(str(raw_val).strip())
        except Exception:
            m = re.search(r"(-?\d+(\.\d+)?)", summary or "")
            value = float(m.group(1)) if m else 0.0

        state = {
            "metric": metric,
            "value": float(value or 0.0),
            "summary": summary,
            "target_namespace": os.environ.get("TARGET_NAMESPACE","default"),
            "target_deployment": os.environ.get("TARGET_DEPLOYMENT","your-app"),
        }
        state["resource_id"] = f'{state["target_namespace"]}/{state["target_deployment"]}'

        res = graph.invoke(state)
        try:
            LOG.info("DECISIONS %s", json.dumps(res.get("decisions", {}), sort_keys=True))
            LOG.info("ACTION %s", json.dumps(res.get("action", {}), sort_keys=True))
        except Exception:
            pass

        results.append(res)

    return {"count": len(results), "results": results}
