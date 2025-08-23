from __future__ import annotations
import time
from collections import deque
from typing import Dict, Any, List

def _norm(text: str) -> List[str]:
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in (text or "")).split() if t]

def _jacc(a: List[str], b: List[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B: return 1.0
    return len(A & B) / max(1, len(A | B))

class Deduper:
    def __init__(self, window_sec=600, threshold=0.85):
        self.win, self.th = window_sec, threshold
        self.buf: deque = deque()
    def seen(self, key: str, text: str) -> bool:
        now, toks = time.time(), _norm(text or "")
        while self.buf and now - self.buf[0][0] > self.win:
            self.buf.popleft()
        for _, k, t in list(self.buf):
            if k == key and _jacc(t, toks) >= self.th:
                return True
        self.buf.append((now, key, toks))
        return False

deduper = Deduper(window_sec=600, threshold=0.85)

def dedup_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    metric = state.get("metric","")
    resource = state.get("resource_id","")
    summary = state.get("summary","")
    key = f"{metric}:{resource}"
    dup = deduper.seen(key, summary)
    state.setdefault("decisions", {})["dedup"] = {"duplicate": bool(dup)}
    state["duplicate"] = bool(dup)
    return state
