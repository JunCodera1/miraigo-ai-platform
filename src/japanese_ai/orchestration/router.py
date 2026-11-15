"""Capability router: decides which model serves a request and what happens when it fails.

For each capability the registry names a primary model and ordered fallbacks. The router walks
that chain, skipping providers that are not usable, retrying transient failures, enforcing a
timeout per attempt, and recording usage and estimated cost. Callers get the result plus the
list of attempts, so a response can always say which model produced it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from japanese_ai.core import errors
from japanese_ai.core.errors import AppError
from japanese_ai.core.logging import get_logger
from japanese_ai.providers.base import (
    ASRProvider,
    AudioClip,
    ProviderAttempt,
    ProviderError,
    RoutedResult,
    TranscribeOptions,
    Transcription,
)

if TYPE_CHECKING:
    from japanese_ai.model_registry.registry import ModelRegistry, ModelSpec, Route
    from japanese_ai.orchestration.usage import UsageLedger
    from japanese_ai.providers.factory import ProviderPool

T = TypeVar("T")
log = get_logger("router")


class InferenceSlots:
    """Bounds how many local inferences run at once; extra requests wait, then get 503."""

    def __init__(self, limit: int, queue_timeout: float) -> None:
        self._semaphore = asyncio.Semaphore(limit)
        self._queue_timeout = queue_timeout

    async def acquire(self) -> None:
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._queue_timeout)
        except TimeoutError:
            raise AppError(
                errors.BUSY,
                "The service is busy processing other requests. Try again shortly.",
                503,
                headers={"Retry-After": "5"},
            ) from None

    def release(self) -> None:
        self._semaphore.release()


class CapabilityRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        pool: ProviderPool,
        ledger: UsageLedger,
        slots: InferenceSlots,
        *,
        primary_overrides: dict[str, str | None] | None = None,
        expose_failure_details: bool = False,
    ) -> None:
        self._registry = registry
        self._pool = pool
        self._ledger = ledger
        self._slots = slots
        self._primary_overrides = primary_overrides or {}
        self._expose_failure_details = expose_failure_details

    def chain(self, route: Route, preferred: str | None = None) -> list[ModelSpec]:
        return self._registry.chain(
            route, preferred=preferred, primary_override=self._primary_overrides.get(route)
        )

    async def transcribe(
        self, clip: AudioClip, options: TranscribeOptions, *, model: str | None = None, route: Route = "asr"
    ) -> RoutedResult[Transcription]:
        async def invoke(provider: ASRProvider) -> Transcription:
            return await provider.transcribe(clip, options)

        return await self._route(route, invoke, preferred=model, audio_seconds=clip.duration)

    async def _route(
        self,
        route: Route,
        invoke: Callable[[ASRProvider], Awaitable[T]],
        *,
        preferred: str | None,
        audio_seconds: float = 0.0,
    ) -> RoutedResult[T]:
        chain = self.chain(route, preferred)
        if not chain:
            if preferred is not None:
                raise AppError(
                    errors.MODEL_NOT_FOUND, f"Model '{preferred}' is not available for this task.", 404
                )
            raise AppError(errors.PROVIDER_UNAVAILABLE, "No model is configured for this task.", 503)

        routing = self._registry.routing(route)
        attempts: list[ProviderAttempt] = []

        for spec in chain:
            provider = self._pool.get(spec)
            usable, reason = provider.availability()
            if not usable:
                attempts.append(ProviderAttempt(model_id=spec.id, ok=False, duration_ms=0, error=reason))
                log.warning("provider skipped", extra={"model": spec.id, "reason": reason})
                continue

            for try_index in range(1 + routing.max_retries):
                if spec.deployment == "local":
                    await self._slots.acquire()
                started = time.perf_counter()
                retryable = False
                try:
                    async with asyncio.timeout(routing.timeout_seconds):
                        value = await invoke(provider)
                except TimeoutError:
                    error, retryable = "timeout", True
                except ProviderError as exc:
                    error, retryable = str(exc), exc.retryable
                except Exception:  # an adapter bug must not take the request down with it
                    log.exception("provider crashed", extra={"model": spec.id})
                    error = "unexpected provider error"
                else:
                    duration_ms = _elapsed_ms(started)
                    cost = _estimate_cost(spec, audio_seconds)
                    self._ledger.record(
                        spec.id, ok=True, duration_ms=duration_ms, audio_seconds=audio_seconds, cost_usd=cost
                    )
                    attempts.append(ProviderAttempt(model_id=spec.id, ok=True, duration_ms=duration_ms))
                    return RoutedResult(
                        value=value,
                        model_id=spec.id,
                        provider=spec.provider,
                        duration_ms=duration_ms,
                        estimated_cost_usd=cost,
                        attempts=attempts,
                    )
                finally:
                    if spec.deployment == "local":
                        self._slots.release()

                duration_ms = _elapsed_ms(started)
                self._ledger.record(spec.id, ok=False, duration_ms=duration_ms)
                attempts.append(
                    ProviderAttempt(model_id=spec.id, ok=False, duration_ms=duration_ms, error=error)
                )
                log.warning(
                    "provider attempt failed",
                    extra={
                        "model": spec.id,
                        "error": error,
                        "attempt": try_index + 1,
                        "duration_ms": duration_ms,
                    },
                )
                if not retryable:
                    break
                if try_index < routing.max_retries:
                    await asyncio.sleep(min(0.25 * 2**try_index, 2.0))

        timed_out = all(attempt.error == "timeout" for attempt in attempts)
        details = (
            [{"model": attempt.model_id, "error": attempt.error} for attempt in attempts]
            if self._expose_failure_details
            else None
        )
        if timed_out:
            raise AppError(
                errors.PROVIDER_TIMEOUT, "The model took too long to respond.", 504, errors=details
            )
        raise AppError(
            errors.PROVIDER_UNAVAILABLE, "No model could process this request right now.", 503, errors=details
        )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _estimate_cost(spec: ModelSpec, audio_seconds: float) -> float:
    if spec.cost.unit == "audio_minute":
        return round(spec.cost.usd * audio_seconds / 60.0, 6)
    return 0.0
