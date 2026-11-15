"""Provider contracts.

Business logic talks to these types only. Each adapter (local engine, commercial API, another
service) lives in its own module and translates to and from them, so swapping a model never
touches pipelines or routes.
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from japanese_ai.model_registry.registry import ModelSpec

SAMPLE_RATE = 16_000


# --- Errors ---------------------------------------------------------------------------------
class ProviderError(Exception):
    """Base class. ``retryable`` tells the router whether the same provider is worth retrying."""

    retryable = False

    def __init__(self, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderUnavailable(ProviderError):
    """Not usable right now: missing model files, missing API key, missing optional dependency."""


class ProviderTransientError(ProviderError):
    """A failure that may pass on its own: network error, HTTP 429/5xx."""

    retryable = True


class ProviderTimeout(ProviderTransientError):
    pass


class ProviderRejected(ProviderError):
    """The provider refused this input (e.g. HTTP 400). Another provider may still accept it."""


# --- Speech recognition ---------------------------------------------------------------------
@dataclass(frozen=True)
class AudioClip:
    """Decoded audio in the one format every speech provider receives: 16 kHz mono float32."""

    samples: np.ndarray
    sample_rate: int = SAMPLE_RATE

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate

    @property
    def rms(self) -> float:
        if len(self.samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(self.samples, dtype=np.float64))))

    def to_wav_bytes(self) -> bytes:
        """16-bit PCM WAV, for providers that take a file upload."""
        pcm = (np.clip(self.samples, -1.0, 1.0) * 32767.0).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(pcm.tobytes())
        return buffer.getvalue()


@dataclass(frozen=True)
class TranscribeOptions:
    language: str | None = "ja"
    word_timestamps: bool = False


@dataclass(frozen=True)
class Word:
    """A timed unit inside a segment. For Japanese engines this is usually one token or character."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = ()


@dataclass(frozen=True)
class Transcription:
    text: str
    segments: tuple[Segment, ...] = ()
    language: str | None = None
    language_probability: float | None = None


class ASRProvider(ABC):
    """Speech-to-text. One instance per registry entry; instances are reused across requests."""

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    @abstractmethod
    def availability(self) -> tuple[bool, str | None]:
        """Cheap check, no model loading: ``(usable, reason_if_not)``."""

    @abstractmethod
    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        """Raise a ``ProviderError`` subclass on failure; never return a partial result silently."""

    async def warm_up(self) -> None:  # noqa: B027 - optional hook, remote providers have nothing to load
        """Load weights ahead of the first request. Optional."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        """Release network clients. Optional."""


@dataclass
class ProviderAttempt:
    """One try against one provider, kept for logs and for the response's ``meta``."""

    model_id: str
    ok: bool
    duration_ms: int
    error: str | None = None


@dataclass
class RoutedResult[T]:
    value: T
    model_id: str
    provider: str
    duration_ms: int
    estimated_cost_usd: float = 0.0
    attempts: list[ProviderAttempt] = field(default_factory=list)
