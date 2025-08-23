from __future__ import annotations
import os
from typing import Dict, Any

DEFAULT_THRESH = {
    "cpu":    float(os.environ.get("CPU_THRESHOLD",  "85")),
    "memory": float(os.environ.get("MEM_THRESHOLD",  "85")),
    "disk":   float(os.environ.get("DISK_THRESHOLD", "85")),
}
Z_THRESHOLD = float(os.environ.get("Z_THRESHOLD", "2.5"))

def policy_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    metric = state.get("metric","")
    val    = float(state.get("value") or 0.0)
    z      = float(state.get("z") or 0.0)
    dup    = bool(state.get("duplicate", False))
    th     = DEFAULT_THRESH.get(metric, 85.0)

    should = (not dup) and (val > th) and (z >= Z_THRESHOLD)
    state.setdefault("decisions", {})["policy"] = {
        "threshold": th, "z_threshold": Z_THRESHOLD,
        "value": val, "z": z, "should_remediate": should,
        "reason": None if should else f"dup={dup}, value<=th={val<=th}, z<th={z<Z_THRESHOLD}"
    }
    state["should_remediate"] = should
    return state
