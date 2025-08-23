from __future__ import annotations
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from agents.baseline_agent import baseline_agent
from agents.dedup_agent import dedup_agent
from agents.policy_agent import policy_agent
from agents.ai_agent import ai_agent
from agents.remediation_agent import remediation_agent

def build_graph():
    g = StateGraph(dict)
    g.add_node("baseline",    baseline_agent)
    g.add_node("dedup",       dedup_agent)
    g.add_node("policy",      policy_agent)
    g.add_node("llm",         ai_agent)
    g.add_node("remediation", remediation_agent)

    g.set_entry_point("baseline")
    g.add_edge("baseline", "dedup")
    g.add_edge("dedup",    "policy")
    g.add_edge("policy",   "llm")

    def llm_route(state: Dict[str, Any]):
        return "remediation" if state.get("should_remediate") else END

    g.add_conditional_edges("llm", llm_route, {"remediation": "remediation", END: END})
    return g.compile()
