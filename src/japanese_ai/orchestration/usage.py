"""Per-model usage and cost counters.

Kept in memory: enough to see what a single instance is doing and what it would have cost.
Counters reset on restart; durable accounting needs a metrics backend.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass


@dataclass
class ModelUsage:
    model_id: str
    requests: int = 0
    failures: int = 0
    audio_seconds: float = 0.0
    processing_ms: int = 0
    estimated_cost_usd: float = 0.0


class UsageLedger:
    def __init__(self) -> None:
        self._by_model: dict[str, ModelUsage] = {}
        self._lock = threading.Lock()

    def record(
        self, model_id: str, *, ok: bool, duration_ms: int, audio_seconds: float = 0.0, cost_usd: float = 0.0
    ) -> None:
        with self._lock:
            usage = self._by_model.setdefault(model_id, ModelUsage(model_id=model_id))
            usage.requests += 1
            usage.processing_ms += duration_ms
            if ok:
                usage.audio_seconds = round(usage.audio_seconds + audio_seconds, 3)
                usage.estimated_cost_usd = round(usage.estimated_cost_usd + cost_usd, 6)
            else:
                usage.failures += 1

    def snapshot(self) -> list[dict[str, object]]:
        with self._lock:
            return [asdict(usage) for usage in self._by_model.values()]
