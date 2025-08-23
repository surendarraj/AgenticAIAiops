from __future__ import annotations
import json, os
from typing import Dict, Any

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.0"))
LLM_GATE = os.environ.get("LLM_GATE", "approve_only").lower()

def _ask_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; LLM stage is required and cannot be bypassed.")

    from langchain_openai import ChatOpenAI
    client = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=api_key)

    system = (
        "You are an site reliability assistant. Given an alert context, decide whether to remediate and propose a safe action.\n"
        "Output STRICT JSON with keys: remediate (bool), action (string: scale|noop), "
        "targetReplicas (int, optional), replicasDelta (int, optional), reason (string), runbook (array of strings)."
    )
    user = {
        "metric": state.get("metric"),
        "value": state.get("value"),
        "z_score": state.get("z"),
        "duplicate": state.get("duplicate", False),
        "policy": state.get("decisions",{}).get("policy",{}),
        "target": {
            "namespace": state.get("target_namespace"),
            "deployment": state.get("target_deployment")
        },
        "summary": state.get("summary", ""),
    }
    messages = [{"role":"system","content":system},{"role":"user","content":json.dumps(user)}]
    resp = client.invoke(messages)
    text = getattr(resp, "content", str(resp))

    import json as _json
    try:
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1: text = text[start:end+1]
        data = _json.loads(text)
    except Exception as e:
        raise RuntimeError(f"LLM returned non-JSON response: {text!r}") from e
    return data

def ai_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("should_remediate"):
        state.setdefault("decisions", {})["llm"] = {"skipped": True, "reason": "policy gate not satisfied"}
        return state

    plan = _ask_llm(state)
    state.setdefault("decisions", {})["llm"] = plan

    if LLM_GATE == "approve_only" and not plan.get("remediate", False):
        state["should_remediate"] = False
    else:
        state["llm_plan"] = plan
    return state
