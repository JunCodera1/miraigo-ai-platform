from __future__ import annotations

from japanese_ai.gateway.schemas import ExecutionMeta
from japanese_ai.providers.base import RoutedResult


def meta_of(routed: RoutedResult) -> ExecutionMeta:
    return ExecutionMeta(
        model=routed.model_id,
        provider=routed.provider,
        processing_ms=routed.duration_ms,
        estimated_cost_usd=routed.estimated_cost_usd,
        fallback_used=len(routed.attempts) > 1,
    )
