from __future__ import annotations
import time, warnings
from typing import Dict, Any, Tuple
from collections import deque
import numpy as np
from statsmodels.tsa.arima.model import ARIMA

class _ARIMABaseline:
    def __init__(self, order=(1,1,1), window: int = 120, min_points: int = 30, refit_every: int = 10):
        self.order = order
        self.window = window
        self.min_points = min_points
        self.refit_every = refit_every
        self.history = deque(maxlen=self.window)
        self.residuals = deque(maxlen=self.window)
        self._model = None
        self._since_refit = 0

    def _fit(self):
        if len(self.history) < self.min_points:
            self._model = None
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                arr = np.asarray(self.history, dtype=float)
                self._model = ARIMA(arr, order=self.order, enforce_stationarity=False, enforce_invertibility=False).fit()
                self._since_refit = 0
        except Exception:
            self._model = None

    def update_and_z(self, x: float) -> float:
        x = float(x)
        if self._model is None and len(self.history) >= self.min_points:
            self._fit()
        if self._model is not None:
            try:
                yhat = float(self._model.forecast(steps=1)[0])
            except Exception:
                yhat = self.history[-1] if self.history else x
        else:
            yhat = self.history[-1] if self.history else x
        resid = x - yhat
        self.residuals.append(resid)
        resid_std = float(np.std(self.residuals)) if len(self.residuals) > 1 else 0.0
        z = resid / (resid_std if resid_std > 1e-6 else 1.0)
        self.history.append(x)
        self._since_refit += 1
        if self._since_refit >= self.refit_every:
            self._fit()
        return float(z)

class BaselineStore:
    def __init__(self, ttl_sec: int = 3600):
        self.ttl = ttl_sec
        self._store: Dict[str, Tuple[_ARIMABaseline, float]] = {}

    def _now(self) -> float:
        return time.time()

    def score(self, key: str, value: float) -> float:
        b, _ = self._store.get(key, (_ARIMABaseline(), 0.0))
        z = b.update_and_z(value)
        self._store[key] = (b, self._now())
        cutoff = self._now() - self.ttl
        for k in list(self._store):
            if self._store[k][1] < cutoff:
                del self._store[k]
        return z

baseline_store = BaselineStore(ttl_sec=3600)

def baseline_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    metric = state.get("metric","")
    resource = state.get("resource_id","")
    value = float(state.get("value") or 0.0)
    z = baseline_store.score(f"{metric}:{resource}", value)
    state["z"] = round(float(z), 4)
    state.setdefault("decisions", {})["baseline"] = {"z": state["z"], "method": "ARIMA(1,1,1)"}
    return state
