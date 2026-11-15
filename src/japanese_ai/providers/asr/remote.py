"""Speech recognition served by another process over HTTP.

``OpenAICompatibleASR`` speaks the ``POST /audio/transcriptions`` contract that OpenAI defined
and that Groq, self-hosted Whisper servers and others also implement.

``LegacyVoiceAIASR`` talks to the original MiraiGo prototype ("VoiceAI": language ID + Whisper),
which keeps it usable as a baseline and as an emergency fallback without re-hosting its code.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx

from japanese_ai.providers.base import (
    ASRProvider,
    AudioClip,
    ProviderRejected,
    ProviderTimeout,
    ProviderTransientError,
    ProviderUnavailable,
    Segment,
    TranscribeOptions,
    Transcription,
)

if TYPE_CHECKING:
    from japanese_ai.core.config import Settings
    from japanese_ai.model_registry.registry import ModelSpec


class _HttpASR(ASRProvider):
    def __init__(
        self, spec: ModelSpec, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        super().__init__(spec)
        self._base_url: str = spec.config["base_url"].rstrip("/")
        timeout = float(spec.config.get("timeout_seconds", 60.0))
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.post(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("request timed out", provider=self.spec.id) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransientError(
                f"network error: {type(exc).__name__}", provider=self.spec.id
            ) from exc

        status = response.status_code
        if status in (401, 403):
            raise ProviderUnavailable("credentials were rejected", provider=self.spec.id)
        if status == 429 or status >= 500:
            raise ProviderTransientError(f"HTTP {status}", provider=self.spec.id)
        if status >= 400:
            raise ProviderRejected(f"HTTP {status}", provider=self.spec.id)
        return response

    def _json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderTransientError("response was not JSON", provider=self.spec.id) from exc
        if not isinstance(body, dict):
            raise ProviderTransientError("unexpected response shape", provider=self.spec.id)
        return body


class OpenAICompatibleASR(_HttpASR):
    def __init__(
        self, spec: ModelSpec, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        super().__init__(spec, settings, transport=transport)
        self._remote_model: str = spec.config["model"]
        self._api_key_env: str | None = spec.config.get("api_key_env")
        self._response_format: str = spec.config.get("response_format", "json")

    def _api_key(self) -> str | None:
        return os.environ.get(self._api_key_env) if self._api_key_env else None

    def availability(self) -> tuple[bool, str | None]:
        if self._api_key_env and not self._api_key():
            return False, f"environment variable {self._api_key_env} is not set"
        return True, None

    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        usable, reason = self.availability()
        if not usable:
            raise ProviderUnavailable(reason or "unavailable", provider=self.spec.id)

        data = {"model": self._remote_model, "response_format": self._response_format}
        if options.language:
            data["language"] = options.language
        headers = {"Authorization": f"Bearer {self._api_key()}"} if self._api_key() else {}
        response = await self._post(
            f"{self._base_url}/audio/transcriptions",
            headers=headers,
            data=data,
            files={"file": ("audio.wav", clip.to_wav_bytes(), "audio/wav")},
        )
        body = self._json(response)
        text = str(body.get("text", "")).strip()
        segments = tuple(
            Segment(start=float(raw["start"]), end=float(raw["end"]), text=str(raw.get("text", "")).strip())
            for raw in body.get("segments") or []
            if isinstance(raw, dict) and "start" in raw and "end" in raw
        )
        if not segments and text:
            segments = (Segment(start=0.0, end=round(clip.duration, 3), text=text),)
        return Transcription(text=text, segments=segments, language=body.get("language") or options.language)


class LegacyVoiceAIASR(_HttpASR):
    """``POST /predict`` with form field ``audio`` -> ``{language, confidence, transcript}``.

    The prototype detects the language itself, so ``options.language`` is ignored, and it returns
    no timestamps.
    """

    def availability(self) -> tuple[bool, str | None]:
        return True, None

    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        response = await self._post(
            f"{self._base_url}/predict",
            files={"audio": ("audio.wav", clip.to_wav_bytes(), "audio/wav")},
        )
        body = self._json(response)
        text = str(body.get("transcript", "")).strip()
        confidence = body.get("confidence")
        segments = (Segment(start=0.0, end=round(clip.duration, 3), text=text),) if text else ()
        return Transcription(
            text=text,
            segments=segments,
            language=body.get("language"),
            language_probability=round(float(confidence), 4) if isinstance(confidence, int | float) else None,
        )
