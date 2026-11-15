import asyncio

import httpx
import numpy as np
import pytest

from japanese_ai.model_registry.registry import ModelSpec
from japanese_ai.providers.asr.remote import LegacyVoiceAIASR, OpenAICompatibleASR
from japanese_ai.providers.base import (
    AudioClip,
    ProviderRejected,
    ProviderTransientError,
    ProviderUnavailable,
    TranscribeOptions,
)
from tests.conftest import make_settings

CLIP = AudioClip(samples=np.zeros(16000, dtype=np.float32))


def spec(provider, **config):
    return ModelSpec(
        id="r",
        capability="asr",
        provider=provider,
        deployment="remote_api",
        languages=["ja"],
        license="x",
        source="x",
        config=config,
    )


def run(coro):
    return asyncio.run(coro)


def test_openai_compatible_contract(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-test")
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        body = request.content
        seen["has_file"] = b'name="file"' in body and b"RIFF" in body
        seen["model"] = b"gpt-x" in body and b'name="language"' in body
        return httpx.Response(200, json={"text": "こんにちは", "language": "ja"})

    provider = OpenAICompatibleASR(
        spec("openai_compatible", base_url="https://api.test/v1", model="gpt-x", api_key_env="TEST_KEY"),
        make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = run(provider.transcribe(CLIP, TranscribeOptions()))
    assert result.text == "こんにちは" and result.segments[0].end == 1.0
    assert seen == {
        "url": "https://api.test/v1/audio/transcriptions",
        "auth": "Bearer sk-test",
        "has_file": True,
        "model": True,
    }


def test_openai_compatible_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    provider = OpenAICompatibleASR(
        spec("openai_compatible", base_url="https://x", model="m", api_key_env="TEST_KEY"), make_settings()
    )
    assert provider.availability()[0] is False
    with pytest.raises(ProviderUnavailable):
        run(provider.transcribe(CLIP, TranscribeOptions()))


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (429, ProviderTransientError),
        (502, ProviderTransientError),
        (400, ProviderRejected),
        (401, ProviderUnavailable),
    ],
)
def test_http_status_mapping(status, error):
    provider = LegacyVoiceAIASR(
        spec("legacy_voiceai", base_url="http://legacy"),
        make_settings(),
        transport=httpx.MockTransport(lambda r: httpx.Response(status)),
    )
    with pytest.raises(error):
        run(provider.transcribe(CLIP, TranscribeOptions()))


def test_legacy_prototype_contract():
    def handler(request: httpx.Request):
        assert request.url.path == "/predict" and b'name="audio"' in request.content
        return httpx.Response(200, json={"language": "ja", "confidence": 0.98761, "transcript": " 東京 "})

    provider = LegacyVoiceAIASR(
        spec("legacy_voiceai", base_url="http://legacy"),
        make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = run(provider.transcribe(CLIP, TranscribeOptions()))
    assert (result.text, result.language, result.language_probability) == ("東京", "ja", 0.9876)


def test_network_error_is_transient():
    def handler(request):
        raise httpx.ConnectError("down")

    provider = LegacyVoiceAIASR(
        spec("legacy_voiceai", base_url="http://legacy"),
        make_settings(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderTransientError):
        run(provider.transcribe(CLIP, TranscribeOptions()))
