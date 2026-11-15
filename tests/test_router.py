import asyncio

import numpy as np
import pytest

from japanese_ai.core.errors import AppError
from japanese_ai.model_registry.registry import ModelRegistry, RegistryFile
from japanese_ai.orchestration.router import CapabilityRouter, InferenceSlots
from japanese_ai.orchestration.usage import UsageLedger
from japanese_ai.providers.base import AudioClip, ProviderRejected, ProviderTransientError, TranscribeOptions
from japanese_ai.providers.factory import ProviderPool
from tests.conftest import FakeASR, make_settings


def spec(model_id, deployment="local", **extra):
    return {
        "id": model_id,
        "capability": "asr",
        "provider": "sherpa_onnx",
        "deployment": deployment,
        "languages": ["ja"],
        "license": "x",
        "source": "x",
        **extra,
    }


def build(providers: dict, *, fallbacks=("b",), max_retries=0, timeout=5.0, slots=4):
    registry = ModelRegistry(
        RegistryFile.model_validate(
            {
                "models": [spec("a"), spec("b", "remote_api", cost={"unit": "audio_minute", "usd": 0.006})],
                "routing": {
                    "asr": {
                        "primary": "a",
                        "fallbacks": list(fallbacks),
                        "max_retries": max_retries,
                        "timeout_seconds": timeout,
                    }
                },
            }
        )
    )
    for model_id, provider in list(providers.items()):
        provider.spec = registry.get(model_id)
    ledger = UsageLedger()
    router = CapabilityRouter(
        registry,
        ProviderPool(make_settings(), overrides=providers),
        ledger,
        InferenceSlots(slots, 0.2),
        expose_failure_details=True,
    )
    return router, ledger


CLIP = AudioClip(samples=np.zeros(16000 * 30, dtype=np.float32))
OPTS = TranscribeOptions()


def run(coro):
    return asyncio.run(coro)


def test_primary_serves_when_healthy():
    a, b = FakeASR(None, "A"), FakeASR(None, "B")
    router, ledger = build({"a": a, "b": b})
    result = run(router.transcribe(CLIP, OPTS))
    assert (result.value.text, result.model_id, len(result.attempts)) == ("A", "a", 1)
    assert b.calls == 0
    assert ledger.snapshot()[0]["requests"] == 1


def test_falls_back_and_estimates_cost():
    a, b = FakeASR(None, fail=ProviderRejected("bad")), FakeASR(None, "B")
    router, ledger = build({"a": a, "b": b})
    result = run(router.transcribe(CLIP, OPTS))
    assert result.model_id == "b"
    assert result.estimated_cost_usd == pytest.approx(0.003)  # 30 s at $0.006/min
    assert [x.ok for x in result.attempts] == [False, True]


def test_unavailable_provider_is_skipped_without_a_call():
    a, b = FakeASR(None, usable=False), FakeASR(None, "B")
    router, _ = build({"a": a, "b": b})
    assert run(router.transcribe(CLIP, OPTS)).model_id == "b"
    assert a.calls == 0


def test_transient_errors_are_retried():
    a = FakeASR(None, fail=ProviderTransientError("503"))
    router, _ = build({"a": a, "b": FakeASR(None)}, fallbacks=(), max_retries=2)
    with pytest.raises(AppError) as info:
        run(router.transcribe(CLIP, OPTS))
    assert a.calls == 3
    assert info.value.status_code == 503 and info.value.code == "AI_PROVIDER_UNAVAILABLE"


def test_non_retryable_errors_are_not_retried():
    a = FakeASR(None, fail=ProviderRejected("400"))
    router, _ = build({"a": a, "b": FakeASR(None)}, fallbacks=(), max_retries=2)
    with pytest.raises(AppError):
        run(router.transcribe(CLIP, OPTS))
    assert a.calls == 1


class SlowASR(FakeASR):
    async def transcribe(self, clip, options):
        await asyncio.sleep(1)
        return await super().transcribe(clip, options)


def test_timeout_gives_504():
    router, _ = build({"a": SlowASR(None), "b": FakeASR(None)}, fallbacks=(), timeout=0.05)
    with pytest.raises(AppError) as info:
        run(router.transcribe(CLIP, OPTS))
    assert info.value.status_code == 504


def test_unknown_preferred_model_is_404():
    router, _ = build({"a": FakeASR(None), "b": FakeASR(None)})
    with pytest.raises(AppError) as info:
        run(router.transcribe(CLIP, OPTS, model="zzz"))
    assert info.value.status_code == 404


def test_busy_when_all_local_slots_are_taken():
    router, _ = build({"a": SlowASR(None), "b": FakeASR(None)}, fallbacks=(), slots=1)

    async def scenario():
        first = asyncio.create_task(router.transcribe(CLIP, OPTS))
        await asyncio.sleep(0.01)
        with pytest.raises(AppError) as info:
            await router.transcribe(CLIP, OPTS)
        await first
        return info.value

    error = run(scenario())
    assert error.status_code == 503 and error.code == "AI_BUSY"
