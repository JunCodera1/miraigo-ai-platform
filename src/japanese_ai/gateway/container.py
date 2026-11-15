"""Long-lived objects shared by all requests, built once per process."""

from __future__ import annotations

from dataclasses import dataclass, field

from japanese_ai.core.config import Settings
from japanese_ai.infrastructure.auth import BackendAuthenticator
from japanese_ai.infrastructure.rate_limit import RateLimiter
from japanese_ai.model_registry.registry import ModelRegistry
from japanese_ai.orchestration.router import CapabilityRouter, InferenceSlots
from japanese_ai.orchestration.usage import UsageLedger
from japanese_ai.providers.base import ASRProvider
from japanese_ai.providers.factory import ProviderPool
from japanese_ai.services.language.analyzer import JapaneseAnalyzer


@dataclass
class Container:
    settings: Settings
    registry: ModelRegistry
    pool: ProviderPool
    router: CapabilityRouter
    ledger: UsageLedger
    analyzer: JapaneseAnalyzer
    authenticator: BackendAuthenticator
    limiter: RateLimiter = field(default_factory=RateLimiter)

    @classmethod
    def build(
        cls,
        settings: Settings,
        *,
        provider_overrides: dict[str, ASRProvider] | None = None,
        authenticator: BackendAuthenticator | None = None,
    ) -> Container:
        registry = ModelRegistry.load(settings.models_file)
        pool = ProviderPool(settings, overrides=provider_overrides)
        ledger = UsageLedger()
        router = CapabilityRouter(
            registry,
            pool,
            ledger,
            InferenceSlots(settings.max_concurrent_inference, settings.inference_queue_timeout_seconds),
            primary_overrides={"asr": settings.asr_model, "pronunciation": settings.pronunciation_model},
            expose_failure_details=settings.env != "production",
        )
        return cls(
            settings=settings,
            registry=registry,
            pool=pool,
            router=router,
            ledger=ledger,
            analyzer=JapaneseAnalyzer(),
            authenticator=authenticator or BackendAuthenticator(settings),
        )

    async def aclose(self) -> None:
        await self.pool.aclose()
        await self.authenticator.aclose()
