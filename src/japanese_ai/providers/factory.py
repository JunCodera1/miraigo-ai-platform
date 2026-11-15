"""Builds provider instances from registry entries and keeps them for reuse.

Adapters are imported lazily by name, so a deployment that only uses remote APIs never needs
the local engines installed (and the other way round).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from japanese_ai.providers.base import ASRProvider

if TYPE_CHECKING:
    from japanese_ai.core.config import Settings
    from japanese_ai.model_registry.registry import ModelSpec

# registry ``provider`` key -> (module, class)
ADAPTERS: dict[str, tuple[str, str]] = {
    "sherpa_onnx": ("japanese_ai.providers.asr.sherpa", "SherpaOnnxASR"),
    "faster_whisper": ("japanese_ai.providers.asr.whisper", "FasterWhisperASR"),
    "openai_compatible": ("japanese_ai.providers.asr.remote", "OpenAICompatibleASR"),
    "legacy_voiceai": ("japanese_ai.providers.asr.remote", "LegacyVoiceAIASR"),
}


class ProviderPool:
    def __init__(self, settings: Settings, *, overrides: dict[str, ASRProvider] | None = None) -> None:
        self._settings = settings
        # ``overrides`` lets tests (and embedders) supply ready-made providers by model id.
        self._instances: dict[str, ASRProvider] = dict(overrides or {})

    def get(self, spec: ModelSpec) -> ASRProvider:
        instance = self._instances.get(spec.id)
        if instance is None:
            try:
                module_name, class_name = ADAPTERS[spec.provider]
            except KeyError:
                raise ValueError(f"model '{spec.id}' uses unknown provider '{spec.provider}'") from None
            adapter = getattr(import_module(module_name), class_name)
            instance = adapter(spec, self._settings)
            self._instances[spec.id] = instance
        return instance

    async def aclose(self) -> None:
        for instance in self._instances.values():
            await instance.aclose()
