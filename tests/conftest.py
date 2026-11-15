from __future__ import annotations

import io
import wave
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from japanese_ai.core.config import Settings
from japanese_ai.gateway.app import create_app
from japanese_ai.gateway.container import Container
from japanese_ai.infrastructure.auth import BackendAuthenticator
from japanese_ai.providers.base import (
    ASRProvider,
    AudioClip,
    ProviderError,
    Segment,
    TranscribeOptions,
    Transcription,
)

VALID_TOKEN = "valid-access-token-123"
ADMIN_TOKEN = "admin-access-token-456"


class FakeASR(ASRProvider):
    """Returns a fixed transcript; can be told to fail."""

    def __init__(
        self, spec, text: str = "東京に行きました", fail: ProviderError | None = None, usable: bool = True
    ):
        super().__init__(spec)
        self.text = text
        self.fail = fail
        self.usable = usable
        self.calls = 0

    def availability(self):
        return (True, None) if self.usable else (False, "fake unavailable")

    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return Transcription(
            text=self.text, segments=(Segment(0.0, round(clip.duration, 3), self.text),), language="ja"
        )


def backend_transport() -> httpx.MockTransport:
    """Stands in for the MiraiGo backend's GET /api/v1/users/me."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/users/me"
        auth = request.headers.get("authorization", "")
        if auth == f"Bearer {VALID_TOKEN}":
            return httpx.Response(
                200, json={"status": 200, "data": {"id": 7, "username": "learner", "role": "USER"}}
            )
        if auth == f"Bearer {ADMIN_TOKEN}":
            return httpx.Response(
                200, json={"status": 200, "data": {"id": 1, "username": "admin", "role": "ADMIN"}}
            )
        return httpx.Response(401, json={"status": 401, "errorCode": "1003"})

    return httpx.MockTransport(handler)


def make_settings(**overrides) -> Settings:
    base = dict(
        env="test",
        auth_mode="backend",
        log_format="text",
        log_level="WARNING",
        backend_base_url="http://backend.test",
        service_api_keys="service-key-abc",
        rate_limit_per_minute=1000,
        inference_rate_limit_per_minute=1000,
        models_dir=Path("/nonexistent/japanese-ai-test-models"),
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def make_client(
    settings: Settings | None = None, **asr_overrides: ASRProvider | None
) -> tuple[TestClient, Container]:
    settings = settings or make_settings()
    container = Container.build(
        settings, authenticator=BackendAuthenticator(settings, transport=backend_transport())
    )
    for model_id, provider in asr_overrides.items():
        container.pool._instances[model_id.replace("_", "-")] = provider
    return TestClient(create_app(settings, container)), container


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {VALID_TOKEN}"}


def wav_bytes(seconds: float = 1.0, freq: float = 220.0, amplitude: float = 0.3, rate: int = 16000) -> bytes:
    t = np.arange(int(seconds * rate)) / rate
    pcm = (amplitude * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


MODELS_DIR = Path.home() / ".local" / "share" / "japanese-ai-platform" / "models"
